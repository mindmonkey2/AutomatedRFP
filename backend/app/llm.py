"""All Claude calls live here. Each returns a validated Pydantic object.

The pipeline depends on the `LLM` protocol, so tests swap in a fake without touching
the network.
"""

import threading
from typing import Literal, Protocol

import anthropic
from pydantic import BaseModel, Field

from .config import settings

RequirementKind = Literal[
    "submission", "form", "page_limit", "format", "deadline", "evaluation", "qualification", "question"
]
REQUIREMENT_KINDS = list(RequirementKind.__args__)


# ---------- structured output schemas ----------


class ExtractedRequirement(BaseModel):
    text: str = Field(description="The requirement restated as one clear, self-contained sentence.")
    kind: RequirementKind
    section: str | None = Field(description="Solicitation section number/title it appears in, if any.")
    page: int | None = Field(description="Page number from the nearest preceding [Page N] marker, if any.")
    source_quote: str = Field(description="Verbatim text from the solicitation that states it.")
    mandatory: bool = Field(description="True if failing it could make the bid non-responsive.")
    needs_response: bool = Field(
        description="True if the proposal must contain written content addressing it."
    )
    page_limit: int | None = Field(description="Page limit in pages, only for page_limit items.")


class ExtractionResult(BaseModel):
    summary: str = Field(description="2-4 sentence summary of this part of the solicitation.")
    requirements: list[ExtractedRequirement]


class DraftCitation(BaseModel):
    marker: int = Field(description="The [n] marker used in the answer text.")
    source_number: int = Field(description="Number of the source passage that supports the claim.")
    quote: str = Field(description="Short verbatim quote from that source that supports the claim.")


class DraftResult(BaseModel):
    answer: str
    citations: list[DraftCitation]
    unsupported_claims: list[str] = Field(
        description="Things the requirement asks for that the sources do not support."
    )
    confidence: float = Field(description="0 to 1: how fully the sources support a complete answer.")


class AddendumChange(BaseModel):
    change_type: Literal["added", "modified", "removed"]
    requirement_id: int | None = Field(description="Id of the existing requirement, for modified/removed.")
    requirement: ExtractedRequirement | None = Field(description="New or updated requirement; null for removed.")
    explanation: str


class AddendumResult(BaseModel):
    summary: str = Field(description="Plain-language summary of what this addendum changes.")
    changes: list[AddendumChange]


# ---------- prompts ----------

EXTRACT_SYSTEM = """You are a senior proposal compliance analyst for construction firms and government \
contractors. You read solicitations (RFPs, RFQs, IFBs, RFQuals) and build the compliance matrix a bid \
team works from. A missed requirement can get a bid rejected as non-responsive, so be exhaustive.

Extract every distinct requirement in the text you are given:
- submission: something the bidder must do or include (shall / must / required)
- form: a required form, certification, affidavit, bond, insurance certificate or attachment
- page_limit: a page or length limit (set page_limit)
- format: font, margins, file type, ordering, labeling, number of copies, delivery method
- deadline: proposal due date, question deadline, pre-bid meeting, validity period
- evaluation: an evaluation criterion or scoring factor, with its weight if given
- qualification: a minimum qualification (license, years of experience, bonding capacity, insurance limits)
- question: a question or narrative item the proposal must answer

Rules:
- One requirement per distinct obligation. Do not merge separate obligations; do not split one obligation.
- source_quote must be copied verbatim from the text.
- page comes from the nearest preceding [Page N] marker; null if there is none.
- needs_response is true when the proposal must contain written content that addresses the item \
(narratives, questions, qualifications to demonstrate, evaluation criteria to address). It is false for \
pure logistics such as deadlines, copy counts and font rules.
- Skip boilerplate that places no obligation on the bidder. Never invent requirements."""

GAP_SYSTEM = EXTRACT_SYSTEM + """

You are now doing a second, gap-filling pass. You will receive sentences that contain obligation \
words but were not matched to any extracted requirement. Return requirements only for sentences that \
state a real obligation on the bidder; ignore the rest. Return an empty list if none qualify."""

DRAFT_SYSTEM = """You are an expert proposal writer for a construction / government contracting firm. \
You draft one response section at a time, using only the firm's own source material.

Rules:
- Use ONLY facts found in the numbered sources. Never invent project names, numbers, dates, people, \
license numbers, dollar values or certifications.
- After every factual claim, add a citation marker like [1], [2] (numbered in order of first use). \
For each marker, give the source_number and a short verbatim quote from that source.
- If the requirement asks for something the sources do not support, write a clear placeholder such as \
[[TBD: current EMR rating]] and list it in unsupported_claims.
- Address the requirement and any related evaluation criteria directly, reusing the solicitation's \
own terms so evaluators can score it easily. Lead with the answer.
- Plain, specific, professional prose. No marketing filler. Respect any page limit given.
- confidence: 0 to 1, how completely the sources support a strong, accurate answer."""

ADDENDUM_SYSTEM = """You are a proposal compliance analyst. An addendum to a solicitation has been \
issued. Compare it with the current list of requirements and report every change that affects what \
the bidder must do or submit:
- added: a new requirement (give it in full)
- modified: an existing requirement whose text, deadline, limit or form changed (give the requirement \
id and the full updated requirement)
- removed: an existing requirement that was deleted or waived (give the requirement id)
Answers to bidder questions that clarify without changing an obligation are not changes. Use the same \
requirement fields and kind definitions as the original extraction: """ + ", ".join(REQUIREMENT_KINDS) + "."


# ---------- client ----------


class LLMError(RuntimeError):
    pass


class LLM(Protocol):
    def extract_requirements(self, text: str) -> ExtractionResult: ...
    def fill_gaps(self, sentences: list[tuple[int | None, str]]) -> ExtractionResult: ...
    def draft_answer(self, context: str, sources: str) -> DraftResult: ...
    def diff_addendum(self, requirements: str, addendum_text: str) -> AddendumResult: ...


class ClaudeLLM:
    def __init__(self, client: anthropic.Anthropic | None = None):
        self.client = client or anthropic.Anthropic(api_key=settings.anthropic_api_key)
        # Running token totals (used by the evaluation harness to report cost).
        self.usage = {"calls": 0, "input_tokens": 0, "output_tokens": 0,
                      "cache_read_input_tokens": 0, "cache_creation_input_tokens": 0}
        self._usage_lock = threading.Lock()

    def _record_usage(self, resp) -> None:
        u = resp.usage
        with self._usage_lock:
            self.usage["calls"] += 1
            for k in ("input_tokens", "output_tokens", "cache_read_input_tokens", "cache_creation_input_tokens"):
                self.usage[k] += getattr(u, k, None) or 0

    def _parse(self, system: str, user: str, schema: type[BaseModel], max_tokens: int = 16000):
        kwargs = dict(
            model=settings.model,
            max_tokens=max_tokens,
            # Stable system prompt first so it is cached across the many calls per bid.
            system=[{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}],
            messages=[{"role": "user", "content": user}],
            output_format=schema,
            output_config={"effort": settings.effort},
        )
        if settings.use_fallbacks:
            kwargs.update(betas=["server-side-fallback-2026-07-01"], fallbacks="default")
        try:
            resp = self.client.beta.messages.parse(**kwargs)
        except anthropic.AuthenticationError as e:
            raise LLMError("Claude API key was rejected. Check ANTHROPIC_API_KEY in backend/.env.") from e
        except anthropic.APIStatusError as e:
            raise LLMError(f"Claude API error {e.status_code}: {e.message}") from e
        except anthropic.APIConnectionError as e:
            raise LLMError(f"Could not reach the Claude API: {e}") from e
        except TypeError as e:
            if "authentication" in str(e).lower():
                raise LLMError("No Claude API key configured. Set ANTHROPIC_API_KEY in backend/.env.") from e
            raise
        self._record_usage(resp)
        if resp.stop_reason == "refusal":
            raise LLMError("The model declined this request.")
        if resp.stop_reason == "max_tokens":
            raise LLMError("Response was cut off (max_tokens). Try a smaller section.")
        if resp.parsed_output is None:
            raise LLMError("The model returned no structured output.")
        return resp.parsed_output

    def extract_requirements(self, text: str) -> ExtractionResult:
        return self._parse(EXTRACT_SYSTEM, f"<solicitation_text>\n{text}\n</solicitation_text>", ExtractionResult)

    def fill_gaps(self, sentences):
        lines = "\n".join(f"- (page {p if p else '?'}) {s}" for p, s in sentences)
        return self._parse(GAP_SYSTEM, f"<unmatched_sentences>\n{lines}\n</unmatched_sentences>", ExtractionResult)

    def draft_answer(self, context: str, sources: str) -> DraftResult:
        return self._parse(DRAFT_SYSTEM, f"{context}\n\n<sources>\n{sources}\n</sources>", DraftResult)

    def diff_addendum(self, requirements: str, addendum_text: str) -> AddendumResult:
        user = (
            f"<current_requirements>\n{requirements}\n</current_requirements>\n\n"
            f"<addendum>\n{addendum_text}\n</addendum>"
        )
        return self._parse(ADDENDUM_SYSTEM, user, AddendumResult)


_llm: LLM | None = None


def get_llm() -> LLM:
    global _llm
    if _llm is None:
        _llm = ClaudeLLM()
    return _llm


def set_llm(llm: LLM | None) -> None:
    """Used by tests to install a fake."""
    global _llm
    _llm = llm
