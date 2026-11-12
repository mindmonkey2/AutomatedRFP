"""Fact check of drafted answers: labelled cases with planted errors (synthetic; written for these
tests). Every planted error must be caught, and correctly sourced facts must never be flagged."""

import pytest

from app.factcheck import check_answer, extract_facts

RIVERSIDE = ("Past Proposal - Riverside Elementary\nOur firm built Riverside Elementary School, a 60,000 sq ft "
             "K-12 facility for Riverside Unified, completed on schedule on March 12, 2023. Contract value: "
             "$18,500,000. Project manager: Pat Lee, PE. Three similar schools were delivered for the district.")
LICENSE = ("General: Contractor license\nNumber: CA-1043221\nIssued by: California CSLB\nExpires: 2027-06-30\n"
           "Our experience modification rate (EMR) is 0.78 and our 3-year average is 0.81.")
OAKHILL = ("Project record: Oak Hill Middle School\nClient/owner: Oak Hill ISD\nContract value: $24,300,000\n"
           "Dates: 2019-08-01 to 2021-12-15\nScope: New 3-story middle school, 92,000 square feet.")
ESIC = ("Completion certificate. M/s Deccan Builders completed Annual Repairs and Maintenance of ESIC Staff Quarters, "
        "Hyderabad, value Rs. 17,97,043-00, completed on 31.03.2022. Average annual turnover for the last three "
        "years: Rs. 46.29 lakh. Solvency certificate from State Bank of India for Rs. 11,98,028.")
CONTEXT_US = ("<solicitation title=\"Maple Elementary Replacement\" agency=\"Maple USD\"> Describe your experience "
              "with K-12 projects over $10 million in the last 5 years. Limit: 10 pages. Provide 3 references.")
CONTEXT_IN = ("Eligibility: three similar completed works each costing not less than Rs. 11,98,028 (40% of the "
              "estimated cost). EMD Rs. 59,901. Last date 07.06.2023.")

# (case id, cited sources by marker, other retrieved sources, context, answer, expected issues)
CASES = [
    ("us_correct_restatement", {1: RIVERSIDE, 2: LICENSE}, [OAKHILL], CONTEXT_US,
     "## Relevant Experience\n"
     "We built Riverside Elementary School for Riverside Unified, a $18.5 million, 60,000-square-foot K-12 "
     "school completed in March 2023 [1]. Pat Lee, PE managed the project [1]. Our license CA-1043221 "
     "is current and our EMR is 0.78 [2]. As required, this section stays within 10 pages and we provide "
     "3 references.",
     set()),
    ("us_wrong_contract_value", {1: RIVERSIDE}, [], CONTEXT_US,
     "Riverside Elementary School was a $21.5 million project for Riverside Unified [1].",
     {("not_in_sources", "$21.5 million")}),
    ("us_invented_project", {1: RIVERSIDE}, [], CONTEXT_US,
     "We delivered Riverside Elementary School [1] and Lakeside Middle School, completed in 2018 [1].",
     {("not_in_sources", "Lakeside Middle School"), ("not_in_sources", "2018")}),
    ("us_license_digits_swapped", {1: LICENSE}, [], CONTEXT_US,
     "Our California license CA-1043212 is active through June 2027 [1].",
     {("not_in_sources", "CA-1043212")}),
    ("us_wrong_emr", {1: LICENSE}, [], CONTEXT_US,
     "Our EMR is 0.68, well below the industry average [1].",
     {("not_in_sources", "0.68")}),
    ("us_invented_person", {1: RIVERSIDE}, [], CONTEXT_US,
     "John Ramirez, PE served as project manager on Riverside Elementary School [1].",
     {("not_in_sources", "John Ramirez")}),
    ("us_fact_from_the_wrong_source", {1: RIVERSIDE}, [OAKHILL], CONTEXT_US,
     "Oak Hill Middle School, a $24.3 million project, was completed in December 2021 [1].",
     {("wrong_citation", "Oak Hill Middle School"), ("wrong_citation", "$24.3 million"),
      ("wrong_citation", "December 2021")}),
    ("us_wrong_completion_month", {1: OAKHILL}, [], CONTEXT_US,
     "Oak Hill Middle School for Oak Hill ISD was completed in June 2021 [1].",
     {("not_in_sources", "June 2021")}),
    ("us_wrong_area", {1: OAKHILL}, [], CONTEXT_US,
     "The 3-story school covers 95,000 square feet [1].",
     {("not_in_sources", "95,000")}),
    ("us_placeholders_and_uncited_sentences", {1: RIVERSIDE}, [], CONTEXT_US,
     "Our current EMR is [[TBD: current EMR rating]]. Riverside Elementary School was completed in 2023. "
     "We have also completed 14 hospitals.",
     {("not_in_sources", "14")}),
    ("in_correct_restatement", {1: ESIC}, [], CONTEXT_IN,
     "M/s Deccan Builders completed Annual Repairs and Maintenance of ESIC Staff Quarters, Hyderabad, worth "
     "Rs. 17.97 lakh, on 31/03/2022 [1]. Our average annual turnover over the last 3 years is ₹4,629,000 [1], "
     "and our solvency of Rs. 11,98,028 meets the requirement of 40% of the estimated cost [1]. We will deposit "
     "the EMD of Rs. 59,901 before 07.06.2023.",
     {("not_in_sources", "Rs. 17.97 lakh")}),  # rounded: 17,97,043 is not exactly 17.97 lakh; a reviewer should see it
    ("in_wrong_turnover", {1: ESIC}, [], CONTEXT_IN,
     "Our average annual turnover is Rs. 64.29 lakh [1].",
     {("not_in_sources", "Rs. 64.29 lakh")}),
    ("in_wrong_date", {1: ESIC}, [], CONTEXT_IN,
     "The work was completed on 31.03.2021 [1].",
     {("not_in_sources", "31.03.2021")}),
    ("in_number_words", {1: RIVERSIDE}, [], CONTEXT_IN,
     "We delivered 3 similar schools for the district [1], and 5 similar works elsewhere [1].",
     {("not_in_sources", "5")}),
    ("in_wrong_bank", {1: ESIC}, [], CONTEXT_IN,
     "Our solvency certificate is from Punjab National Bank [1].",
     {("not_in_sources", "Punjab National Bank")}),
]


@pytest.mark.parametrize("case_id,cited,others,context,answer,expected", CASES, ids=[c[0] for c in CASES])
def test_fact_check_case(case_id, cited, others, context, answer, expected):
    issues = check_answer(answer, cited, [*cited.values(), *others], context)
    assert {(i.problem, i.text) for i in issues} == expected


def test_detection_summary():
    """Across the cases: every planted error is caught and no correct fact is flagged."""
    planted = sum(len(c[5]) for c in CASES)
    caught = false_alarms = checked = 0
    for _, cited, others, context, answer, expected in CASES:
        found = {(i.problem, i.text) for i in check_answer(answer, cited, [*cited.values(), *others], context)}
        caught += len(found & expected)
        false_alarms += len(found - expected)
        checked += len(extract_facts(answer))
    assert caught == planted and false_alarms == 0
    assert planted == 17 and checked == 48  # update these when adding cases


def test_formats_that_must_match():
    pairs = [
        ("$18.5 million", "Contract value: $18,500,000"),
        ("Rs. 46.29 lakh", "turnover 4,629,000 rupees"),
        ("₹1.2 crore", "Rs. 1,20,00,000/-"),
        ("Rs. 59,901", "EMD Rs. 59,901-00"),
        ("March 12, 2026", "due 12.03.2026"),
        ("12 March 2026", "2026-03-12"),
        ("March 2026", "on 03/12/2026"),
        ("2023", "completed on March 12, 2023"),
        ("40%", "40 percent of the estimated cost"),
        ("3 projects", "three projects"),
        ("CA-1043221", "License CA 1043221"),
    ]
    for claim, source in pairs:
        assert check_answer(f"Claim: {claim} [1].", {1: source}, [source], "") == [], (claim, source)


# ---------------------------------------------------------------- in the drafting flow


def test_draft_with_an_invented_figure_goes_to_review_and_edits_are_rechecked(client, fake_llm, monkeypatch):
    from app.llm import DraftCitation, DraftResult

    client.post("/library/documents", files={"file": ("riverside.txt", RIVERSIDE.encode(), "text/plain")})
    bid = client.post("/bids", json={"title": "Maple Elementary Replacement", "agency": "Maple USD"}).json()

    def draft(context, sources):
        quote = "Contract value: $18,500,000"
        return DraftResult(
            answer="We built Riverside Elementary School, a $21.5 million K-12 school, completed in 2023 [1].",
            citations=[DraftCitation(marker=1, source_number=1, quote=quote)], unsupported_claims=[], confidence=0.9)

    monkeypatch.setattr(fake_llm, "draft_answer", draft)
    client.post(f"/bids/{bid['id']}/files", data={"kind": "base"},
                files={"file": ("rfp.txt", b"[Page 1]\nThe bidder shall describe its K-12 experience.\n", "text/plain")})
    client.post(f"/bids/{bid['id']}/draft", json={})
    ans = client.get(f"/bids/{bid['id']}/requirements").json()[0]["answer"]

    assert ans["status"] == "needs_review"
    assert [(f["problem"], f["text"]) for f in ans["fact_issues"]] == [("not_in_sources", "$21.5 million")]
    assert ans["citations"][0]["verified"] is True  # the quote itself is real: only the prose is wrong
    assert any("$21.5 million" in r for r in ans["confidence_reasons"])
    ready = client.get(f"/bids/{bid['id']}/readiness").json()
    assert ready["unverified_fact_ids"] and "not in any cited source" in ready["warnings"][0]

    # The reviewer corrects the figure: the warning clears.
    fixed = "We built Riverside Elementary School, an $18.5 million K-12 school, completed in 2023 [1]."
    ans = client.patch(f"/answers/{ans['id']}", json={"final_text": fixed}).json()
    assert ans["fact_issues"] == []
    assert client.get(f"/bids/{bid['id']}/readiness").json()["warnings"] == []

    # A new unsupported figure typed by a person is flagged too (a warning; approval is still allowed).
    ans = client.patch(f"/answers/{ans['id']}", json={"final_text": fixed + " We employ 450 people."}).json()
    assert [f["text"] for f in ans["fact_issues"]] == ["450"]
    assert client.post(f"/answers/{ans['id']}/approve").status_code == 200
