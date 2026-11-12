"""Deterministic fact check for drafted answers: no AI involved.

The most damaging error in a proposal is a wrong specific: a contract value, a date, a license
number, a project or person that does not exist. The drafting prompt forbids inventing them and
the quote check confirms each citation's quote, but neither proves that the *numbers and names in
the prose* came from the sources. This module does:

1. extract the checkable facts from the answer: money amounts, percentages, dates, years,
   other numbers, identifiers (license / contract / form numbers) and proper names;
2. normalise formats so "$18.5 million" = "$18,500,000", "Rs. 46.29 lakh" = "4,629,000",
   "March 12, 2026" = "12.03.2026", "3 projects" = "three projects";
3. look for each fact in the source(s) the sentence cites, then in the other retrieved sources,
   then in the solicitation itself (restating the RFP's own numbers is fine).

A fact found nowhere is reported as `not_in_sources`; one found only in a source the sentence does
not cite is `wrong_citation`. Both send the answer to review with the exact items to check.
"""

import re
from dataclasses import asdict, dataclass
from datetime import date

# ---------------------------------------------------------------- facts


@dataclass(frozen=True)
class Fact:
    kind: str  # amount | percent | date | year | number | id | name
    text: str  # as written in the answer
    keys: frozenset[str]  # normalised forms; a fact matches a source sharing any key


@dataclass
class FactIssue:
    kind: str
    text: str
    problem: str  # not_in_sources | wrong_citation
    detail: str

    def as_dict(self) -> dict:
        return asdict(self)


_NUM = r"\d{1,3}(?:,\d{2,3})+(?:\.\d+)?|\d+(?:\.\d+)?"  # 18,500,000  14,97,536  0.78  2023
_SCALE = {
    "thousand": 1e3, "k": 1e3, "lakh": 1e5, "lakhs": 1e5, "lac": 1e5, "lacs": 1e5,
    "million": 1e6, "mn": 1e6, "m": 1e6, "crore": 1e7, "crores": 1e7, "cr": 1e7,
    "billion": 1e9, "bn": 1e9, "b": 1e9,
}
_CURRENCY = r"(?:\bUS\s?\$|\$|\bUSD\s?|\bRs\.?\s?|\bINR\s?|₹\s?)"
_AMOUNT = re.compile(
    rf"{_CURRENCY}(?P<n>{_NUM})(?:\s?(?:-|/-)?\s?00\b|/-)?"
    rf"(?:\s?(?P<scale>thousand|lakhs?|lacs?|million|crores?|billion|mn|bn|cr|[kmb])\b)?",
    re.I,
)
# "18.5 million dollars", "46.29 lakh rupees" without a currency sign
_AMOUNT_WORDS = re.compile(
    rf"\b(?P<n>{_NUM})\s?(?P<scale>thousand|lakhs?|lacs?|million|crores?|billion)\b(?:\s(?:dollars|rupees))?",
    re.I,
)
_PERCENT = re.compile(rf"\b(?P<n>{_NUM})\s?(?:%|percent\b|per cent\b)", re.I)
_MONTHS = {m: i for i, m in enumerate(
    ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"], start=1)}
_MONTH = r"(?:jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)[a-z]*\.?"
_DATE_MDY = re.compile(rf"\b(?P<m>{_MONTH})\s+(?P<d>\d{{1,2}})(?:st|nd|rd|th)?,?\s+(?P<y>\d{{4}})\b", re.I)
_DATE_DMY = re.compile(rf"\b(?P<d>\d{{1,2}})(?:st|nd|rd|th)?\s+(?P<m>{_MONTH}),?\s+(?P<y>\d{{4}})\b", re.I)
_DATE_NUM = re.compile(r"\b(?P<a>\d{1,2})[./-](?P<b>\d{1,2})[./-](?P<y>\d{4})\b")
_DATE_ISO = re.compile(r"\b(?P<y>\d{4})-(?P<m>\d{2})-(?P<d>\d{2})\b")
_MONTH_YEAR = re.compile(rf"\b(?P<m>{_MONTH})\s+(?P<y>\d{{4}})\b", re.I)
_YEAR = re.compile(r"\b(?P<y>19\d{2}|20\d{2})\b")
# Identifiers: letters and digits together (GL-123, W912DY-26-R-0001, ISO-9001, B1234567).
_ID = re.compile(r"\b(?=[A-Za-z0-9/-]*\d)(?=[A-Za-z0-9/-]*[A-Z])[A-Z0-9][A-Za-z0-9]*(?:[-/][A-Za-z0-9]+)+\b"
                 r"|\b(?=[A-Z]*\d)(?=\d*[A-Z])[A-Z0-9]{4,}\b")
_NUMBER = re.compile(rf"(?<![\w.]){_NUM}(?![\w])")
_LIST_MARKER = re.compile(r"^\s*\(?\d{1,2}[.)]\s", re.M)  # "1. " or "2) " starting a line
_NUMBER_WORDS = {
    "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9,
    "ten": 10, "eleven": 11, "twelve": 12, "thirteen": 13, "fourteen": 14, "fifteen": 15, "sixteen": 16,
    "seventeen": 17, "eighteen": 18, "nineteen": 19, "twenty": 20, "thirty": 30, "forty": 40,
    "fifty": 50, "sixty": 60, "seventy": 70, "eighty": 80, "ninety": 90, "hundred": 100,
}
_NUMBER_WORD = re.compile(r"\b(" + "|".join(_NUMBER_WORDS) + r")\b", re.I)

# Proper names: runs of capitalised words, e.g. "Riverside Elementary School", "Pat Lee".
_NAME = re.compile(r"\b[A-Z][\w'’&.-]*(?:[ \t]+(?:of|the|&|for|de|la)?[ \t]*[A-Z][\w'’&.-]*)+")
# Capitalised words that do not make a name on their own (titles, roles, document words).
GENERIC = set("""
a an the our we us this that these those their its his her in on at for by of and or to with as from
all each any every other such project projects program programs plan plans manager management team
teams quality control safety schedule scheduling cost costs budget construction contractor contractors
subcontractor owner owners client clients agency department district county city state federal
national public school schools elementary middle high university college building buildings facility
facilities office offices services service section sections proposal proposals response experience
approach company firm inc llc ltd pvt corporation corp group partners associates design build
engineering engineer engineers architect architects general superintendent director president vice
chief officer senior principal lead assistant coordinator executive key personnel staff resume
resumes certificate certification certified license licensed insurance bond bonding form forms
attachment appendix annexure volume part tab exhibit table figure page pages request rfp rfq ifb
bid bids bidder bidders tender tenders contract contracts agreement work works new existing phase
renovation renovations addition additions replacement center centre hall street road avenue north
south east west upper lower main
yes no not only also however overall total including rs no nos mr ms mrs dr sl viz etc
understanding performance past relevant technical record summary overview introduction qualifications
capabilities commitment methodology organization organizational chart implementation transition risk
mitigation communication communications coordination sustainability value preconstruction closeout
warranty commissioning leed green small business disadvantaged minority women owned veteran local
hiring workforce training equipment materials site logistics traffic environmental health emergency
protection inspection testing submittal submittals procurement delivery method methods scope
statement letter cover transmittal financial capacity references reference award awards
recognition similar completed ongoing current annual average turnover solvency registration
january february march april may june july august september october november december
monday tuesday wednesday thursday friday saturday sunday
""".split())

_MARKERS = re.compile(r"\s?\[\d+(?:,\s*\d+)*\]")
_PLACEHOLDER = re.compile(r"\[\[.*?\]\]", re.S)


def _distinctive(word: str) -> bool:
    """Could this capitalised word identify a specific project, client or person?"""
    w = word.strip(".’'")
    if w.lower() in GENERIC or any(c.isdigit() for c in w):
        return False
    return not (w.isupper() and len(w) <= 5)  # acronyms like EMD, GST, ISD: too short to be checked alone


def _prose(text: str) -> str:
    """Blank out headings (markdown "#" lines and short lines without end punctuation), whose
    capitalised words are titles, not names."""
    out = []
    for line in text.split("\n"):
        s = line.strip()
        heading = s.startswith("#") or (s and len(s) < 60 and not s.endswith((".", ":", ";", "?", "!", ")")))
        out.append("" if heading else line)
    return "\n".join(out)


def _num(s: str) -> float:
    return float(s.replace(",", ""))


def _fmt(v: float) -> str:
    return f"{v:.2f}".rstrip("0").rstrip(".")


def _month(token: str) -> int:
    return _MONTHS[token[:3].lower()]


def _date_keys(y: int, m: int, d: int | None, coarse: bool) -> set[str]:
    """The date's key; with coarse=True (source text) also its month and year, so an answer may
    say "March 2023" or "2023" for a source's "March 12, 2023", but not the other way round."""
    if not 1 <= m <= 12:
        return set()
    if d is not None:
        try:
            date(y, m, d)
        except ValueError:
            return set()
    precise = f"date:{y:04d}-{m:02d}-{d:02d}" if d is not None else f"month:{y:04d}-{m:02d}"
    return {precise, f"month:{y:04d}-{m:02d}", f"year:{y}"} if coarse else {precise}


def extract_facts(text: str, *, source: bool = False) -> list[Fact]:
    """Facts in `text`. With source=True, also derive coarser keys (a full date also counts as its
    month and year; "three" also counts as 3), so an answer may state a fact less precisely."""
    text = _PLACEHOLDER.sub(" ", text)
    text = _MARKERS.sub(" ;", text).replace("–", "-").replace("—", "-")  # a marker ends a name
    text = _LIST_MARKER.sub(lambda m: " " * len(m.group(0)), text)  # list numbering is not a fact
    facts: list[Fact] = []
    taken: list[tuple[int, int]] = []

    def free(m: re.Match) -> bool:
        return not any(m.start() < e and s < m.end() for s, e in taken)

    def add(kind: str, m: re.Match, keys: set[str]) -> None:
        if keys:
            facts.append(Fact(kind, m.group(0).strip(), frozenset(keys)))
        taken.append((m.start(), m.end()))

    for rx in (_AMOUNT, _AMOUNT_WORDS):
        for m in rx.finditer(text):
            if free(m):
                v = _num(m.group("n")) * _SCALE.get((m.group("scale") or "").lower(), 1)
                # Sources often give the figure without a currency ("Contract value 18,500,000").
                add("amount", m, {f"amount:{_fmt(v)}", f"number:{_fmt(v)}"})
    for m in _PERCENT.finditer(text):
        if free(m):
            add("percent", m, {f"percent:{_fmt(_num(m.group('n')))}"})
    for rx in (_DATE_MDY, _DATE_DMY):
        for m in rx.finditer(text):
            if free(m):
                add("date", m, _date_keys(int(m.group("y")), _month(m.group("m")), int(m.group("d")), source))
    for m in _DATE_ISO.finditer(text):
        if free(m):
            add("date", m, _date_keys(int(m.group("y")), int(m.group("m")), int(m.group("d")), source))
    for m in _DATE_NUM.finditer(text):
        if free(m):
            a, b, y = int(m.group("a")), int(m.group("b")), int(m.group("y"))
            # 03.04.2026 could be 3 April (India, Europe) or March 4 (US): accept either reading.
            add("date", m, _date_keys(y, b, a, source) | _date_keys(y, a, b, source))
    for m in _MONTH_YEAR.finditer(text):
        if free(m):
            add("date", m, _date_keys(int(m.group("y")), _month(m.group("m")), None, source))
    for m in _ID.finditer(text):
        if free(m):
            add("id", m, {"id:" + re.sub(r"[^A-Za-z0-9]", "", m.group(0)).upper()})
    for m in _YEAR.finditer(text):
        if free(m):
            add("year", m, {f"year:{m.group('y')}"})
    for m in _NUMBER.finditer(text):
        if free(m):
            add("number", m, {f"number:{_fmt(_num(m.group(0)))}"})
    if source:
        for m in _NUMBER_WORD.finditer(text):
            if free(m):
                add("number", m, {f"number:{_NUMBER_WORDS[m.group(1).lower()]}"})
        # Every derived key also stands alone: "$18,500,000" contains the number 18500000, and a
        # date contains its year, so an answer that states them differently still matches.
        derived = []
        for f in facts:
            for k in f.keys:
                if k.startswith("amount:"):
                    derived.append(Fact("number", f.text, frozenset({"number:" + k.split(":", 1)[1]})))
        facts.extend(derived)

    for m in _NAME.finditer(_prose(text)):
        words = re.findall(r"[A-Za-z][\w'’&.-]*", m.group(0))
        distinctive = [w for w in words if _distinctive(w)]
        if len(words) >= 2 and distinctive:
            facts.append(Fact("name", m.group(0).strip(), frozenset("word:" + w.lower().strip(".’'")
                                                                   for w in distinctive)))
    return facts


# ---------------------------------------------------------------- checking


class _Index:
    """The keys and words of one text, for quick membership tests."""

    def __init__(self, text: str):
        self.keys: set[str] = set()
        for f in extract_facts(text, source=True):
            if f.kind != "name":
                self.keys |= f.keys
        self.words = {"word:" + w.lower().strip(".’'") for w in re.findall(r"[A-Za-z][\w'’&.-]*", text)}
        self.compact = re.sub(r"[^A-Za-z0-9]", "", text).upper()  # "CA 1043221" and "CA-1043221" alike

    def has(self, fact: Fact) -> bool:
        if fact.kind == "name":
            return fact.keys <= self.words  # every distinctive word of the name appears in this text
        if fact.kind == "id":
            return any(k.split(":", 1)[1] in self.compact for k in fact.keys)
        return bool(fact.keys & self.keys)


_SENTENCE = re.compile(r"(?<=[.!?])\s+(?=[A-Z\[(])|\n+")


def check_answer(answer: str, cited: dict[int, str], sources: list[str], context: str) -> list[FactIssue]:
    """Check each fact of `answer` against the source text its sentence cites.

    cited: citation marker -> text of the source passage it points to.
    sources: every passage that was available to the writer (to tell a wrong citation from an invention).
    context: the solicitation's own text for this item (title, agency, summary, requirement, criteria).
    """
    cited_idx = {m: _Index(t) for m, t in cited.items()}
    source_idx = [_Index(t) for t in sources]
    context_idx = _Index(context)
    issues: list[FactIssue] = []
    seen: set[tuple[str, str]] = set()
    for sentence in _SENTENCE.split(answer):
        markers = {int(n) for group in re.findall(r"\[(\d+(?:,\s*\d+)*)\]", sentence) for n in group.split(",")}
        for fact in extract_facts(sentence):
            if (fact.kind, fact.text) in seen:
                continue
            seen.add((fact.kind, fact.text))
            if any(cited_idx[m].has(fact) for m in markers if m in cited_idx) or context_idx.has(fact):
                continue
            if not markers and any(ix.has(fact) for ix in [*cited_idx.values(), *source_idx]):
                continue  # uncited sentence, but the fact is in the material: fine for this check
            if markers and any(ix.has(fact) for ix in [*cited_idx.values(), *source_idx]):
                cites = ", ".join(f"[{m}]" for m in sorted(markers))
                issues.append(FactIssue(fact.kind, fact.text, "wrong_citation",
                                        f"Found in the library, but not in the source this sentence cites ({cites})."))
                continue
            issues.append(FactIssue(fact.kind, fact.text, "not_in_sources",
                                    "Not found in any source or in the solicitation. Verify it or remove it."))
    return issues
