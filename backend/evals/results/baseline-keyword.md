# Requirement extraction eval: keyword

Run 2026-11-12 14:46 UTC · 5 cases · 102 labelled requirements

| Metric | Value |
| --- | --- |
| **Recall** (requirements found) | **53.9%** (55/102) |
| Mandatory recall | 63.0% |
| Kind accuracy (of found) | 14.5% |
| Page accuracy (of found) | 100.0% |
| Traps extracted (owner obligations taken as bidder requirements) | 1 of 10 |
| Extracted items not in the answer key | 7 of 62 |

## Recall by requirement kind

| Kind | Found | Recall |
| --- | --- | --- |
| deadline | 5/11 | 45% |
| evaluation | 0/15 | 0% |
| form | 11/22 | 50% |
| format | 7/8 | 88% |
| page_limit | 3/6 | 50% |
| qualification | 15/15 | 100% |
| question | 6/15 | 40% |
| submission | 8/10 | 80% |

## By case

| Case | Recall | Mandatory | Extracted | Traps hit |
| --- | --- | --- | --- | --- |
| county_cmar_rfp | 29% (7/24) | 6/17 | 9 | 1 |
| federal_design_build | 56% (14/25) | 13/19 | 16 | 0 |
| k12_school_ifb | 75% (15/20) | 14/19 | 18 | 0 |
| university_ae_rfq | 42% (8/19) | 8/13 | 8 | 0 |
| water_main_srf_ifb | 79% (11/14) | 10/13 | 11 | 0 |

## Missed requirements

- `county_cmar_rfp` R01 (deadline): "Deadline for written questions: April 17, 2026, 4:00 p.m."
- `county_cmar_rfp` R02 (deadline, mandatory): "Proposals due: May 1, 2026, 2:00 p.m."
- `county_cmar_rfp` R07 (submission, mandatory): "Provide a cover letter signed by an officer authorized to bind the firm"
- `county_cmar_rfp` R09 (question, mandatory): "Describe your firm's experience as CMAR on at least three public safety, justice, or comparable civic facilities completed in the last ten years"
- `county_cmar_rfp` R10 (question, mandatory): "Identify the proposed project executive, project manager, superintendent, and preconstruction manager"
- `county_cmar_rfp` R11 (submission, mandatory): "Include a one-page resume for each"
- `county_cmar_rfp` R12 (question, mandatory): "Describe your approach to estimating, value engineering, constructability review, and developing the Guaranteed Maximum Price (GMP)"
- `county_cmar_rfp` R13 (question, mandatory): "Provide your firm's Experience Modification Rate (EMR) for each of the last three years"
- `county_cmar_rfp` R14 (question, mandatory): "Describe your site safety program, including subcontractor safety oversight"
- `county_cmar_rfp` R15 (form, mandatory): "using Attachment B, Fee Proposal Form, uploaded as a separate file"
- `county_cmar_rfp` R16 (form, mandatory): "signed Conflict of Interest Disclosure (Attachment C)"
- `county_cmar_rfp` R17 (form, mandatory): "Vendor Registration Certificate (Attachment D)"
- `county_cmar_rfp` R20 (evaluation): "Firm qualifications and relevant experience — 30 points"
- `county_cmar_rfp` R21 (evaluation): "Key personnel — 25 points"
- `county_cmar_rfp` R22 (evaluation): "Preconstruction approach — 20 points"
- `county_cmar_rfp` R23 (evaluation): "Safety record — 10 points"
- `county_cmar_rfp` R24 (evaluation): "Fee proposal — 15 points"
- `federal_design_build` R04 (deadline, mandatory): "Proposals are due no later than 1:00 p.m. Eastern Time on June 9, 2026"
- `federal_design_build` R08 (form, mandatory): "Volume I — Price, including the completed SF 1442 and Bid Schedule"
- `federal_design_build` R09 (page_limit, mandatory): "Volume II — Technical Approach, not to exceed 30 pages"
- `federal_design_build` R10 (page_limit, mandatory): "Volume III — Past Performance, not to exceed 15 pages"
- `federal_design_build` R11 (page_limit, mandatory): "Volume IV — Small Business Participation Plan, not to exceed 5 pages"
- `federal_design_build` R18 (question, mandatory): "Submit up to five (5) recent and relevant projects completed within the past six (6) years"
- `federal_design_build` R21 (evaluation): "Award will be made to the offeror whose proposal represents the best value to the Government"
- `federal_design_build` R22 (evaluation): "Factor 1, Technical Approach, is more important than Factor 2, Past Performance"
- `federal_design_build` R23 (evaluation): "Past performance will be evaluated for recency, relevancy, and quality"
- `federal_design_build` R24 (evaluation): "Factor 3, Small Business Participation"
- `federal_design_build` R25 (evaluation): "Price will be evaluated for reasonableness"
- `k12_school_ifb` R01 (deadline, mandatory): "no later than 2:00 p.m. local time on Thursday, March 12, 2026"
- `k12_school_ifb` R10 (form, mandatory): "Designation of Subcontractors"
- `k12_school_ifb` R11 (form, mandatory): "Non-Collusion Declaration"
- `k12_school_ifb` R12 (form, mandatory): "Bidder's Certificate Regarding Workers' Compensation"
- `k12_school_ifb` R13 (form, mandatory): "Iran Contracting Act Certification"
- `university_ae_rfq` R02 (deadline, mandatory): "Statements of Qualifications are due by 3:00 p.m. Central Time on September 3, 2026"
- `university_ae_rfq` R03 (format, mandatory): "Submit one (1) original and five (5) copies, plus one electronic copy on a USB drive"
- `university_ae_rfq` R09 (question, mandatory): "Provide resumes of key personnel, including the principal-in-charge, project architect, and lead mechanical, electrical, and plumbing engineers"
- `university_ae_rfq` R11 (question, mandatory): "Describe your approach to phasing construction in an occupied building"
- `university_ae_rfq` R12 (question, mandatory): "describe your quality control process for construction documents"
- `university_ae_rfq` R14 (form): "Include a completed Disclosure of Lobbying Activities form (SF-LLL), if applicable"
- `university_ae_rfq` R15 (evaluation): "Specialized experience in laboratory renovations (35%)"
- `university_ae_rfq` R16 (evaluation): "Qualifications of key personnel (25%)"
- `university_ae_rfq` R17 (evaluation): "Approach to occupied-building phasing (20%)"
- `university_ae_rfq` R18 (evaluation): "Past performance on schedule and budget (15%)"
- `university_ae_rfq` R19 (evaluation): "Familiarity with the University's design standards (5%)"
- `water_main_srf_ifb` R01 (deadline, mandatory): "Sealed bids are due at 11:00 a.m. on July 15, 2026"
- `water_main_srf_ifb` R06 (form, mandatory): "shall submit EPA Forms 6100-3 and 6100-4 with the bid"
- `water_main_srf_ifb` R08 (form, mandatory): "shall submit the Certification Regarding Debarment (Attachment E)"
