# Requirement extraction eval: keyword

Run 2026-11-12 18:54 UTC · 11 cases · 266 labelled requirements · 0s

| Metric | Value |
| --- | --- |
| **Recall** (requirements found) | **71.8%** (191/266) |
| Mandatory recall | 77.1% |
| Kind accuracy (of found) | 18.9% |
| Page accuracy (of found) | 99.5% |
| Traps extracted (owner obligations taken as bidder requirements) | 3 of 32 |
| Extracted items not in the answer key | 98 of 289 |

## Recall by requirement kind

| Kind | Found | Recall |
| --- | --- | --- |
| deadline | 17/22 | 77% |
| evaluation | 0/24 | 0% |
| form | 59/75 | 79% |
| format | 33/35 | 94% |
| page_limit | 6/13 | 46% |
| qualification | 34/36 | 94% |
| question | 6/15 | 40% |
| submission | 36/46 | 78% |

## By source

| Source | Cases | Recall |
| --- | --- | --- |
| real | 6 | 80.5% (132/164) |
| synthetic | 5 | 57.8% (59/102) |

## By case

| Case | Source | Recall | Mandatory | Extracted | Traps hit |
| --- | --- | --- | --- | --- | --- |
| county_cmar_rfp | synthetic | 29% (7/24) | 6/17 | 10 | 1 |
| doe_nnsa_rfp_section_l | real | 86% (48/56) | 32/39 | 66 | 1 |
| doe_nnsa_rfp_section_m | real | 23% (3/13) | 3/6 | 7 | 1 |
| federal_design_build | synthetic | 60% (15/25) | 14/19 | 16 | 0 |
| in_esic_hyderabad_cpwd_2023 | real | 92% (23/25) | 21/23 | 37 | 0 |
| in_nhai_makhu_epc_2024 | real | 94% (30/32) | 25/26 | 56 | 0 |
| in_sai_bhopal_cladding_2020 | real | 77% (17/22) | 15/18 | 26 | 0 |
| k12_school_ifb | synthetic | 80% (16/20) | 15/19 | 19 | 0 |
| university_ae_rfq | synthetic | 47% (9/19) | 9/13 | 9 | 0 |
| usace_1985_ifb_ocr | real | 69% (11/16) | 4/8 | 30 | 0 |
| water_main_srf_ifb | synthetic | 86% (12/14) | 11/13 | 13 | 0 |

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
- `doe_nnsa_rfp_section_l` R07 (submission): "Only potential Offerors that submit an intent to bid in accordance with L-29 below will be granted access to this reading room information"
- `doe_nnsa_rfp_section_l` R25 (format, mandatory): "Material may not be incorporated by reference in Volume II (including any information in Volume I or III) as a means to circumvent the page limitations"
- `doe_nnsa_rfp_section_l` R26 (page_limit, mandatory): "Resumes of Key Personnel, which are limited to five (5) pages each"
- `doe_nnsa_rfp_section_l` R27 (page_limit, mandatory): "except for the CEO or President’s resume, which is limited to seven (7) pages"
- `doe_nnsa_rfp_section_l` R28 (page_limit, mandatory): "UPF Interface Management Approach, limited to ten (10) pages"
- `doe_nnsa_rfp_section_l` R29 (page_limit, mandatory): "limited to eight (8) pages per PPIF"
- `doe_nnsa_rfp_section_l` R44 (submission, mandatory): "Any exceptions or deviations by the Offeror to the terms and conditions stated in this solicitation"
- `doe_nnsa_rfp_section_l` R56 (submission, mandatory): "Offerors are prohibited from submitting multiple offers/proposals as a prime contractor or parent company"
- `doe_nnsa_rfp_section_m` R01 (submission, mandatory): "Any exceptions or deviations by the Offeror to the terms and conditions stated in this solicitation for inclusion in the resulting contract may make the offer unacceptable for award"
- `doe_nnsa_rfp_section_m` R04 (form, mandatory): "A Performance Guarantee Agreement in accordance with the requirements of the Solicitation’s Section L provision L-6"
- `doe_nnsa_rfp_section_m` R05 (evaluation): "The Government intends to award one contract to the responsible Offeror whose proposal is responsive to the solicitation and is determined to be the best value to the Government"
- `doe_nnsa_rfp_section_m` R06 (evaluation): "the Technical and Management Criteria, when combined, are significantly more important than the Cost Criterion"
- `doe_nnsa_rfp_section_m` R07 (evaluation): "The Government will evaluate the Offeror's recent, relevant past performance"
- `doe_nnsa_rfp_section_m` R08 (evaluation): "The Government will evaluate the Offeror’s Sites Organization, Key Personnel resumes, and information provided by Key Personnel references"
- `doe_nnsa_rfp_section_m` R10 (qualification, mandatory): "Proposed Key Personnel who are under a service commitment for the performance of another NNSA M&O contract at the projected time of contract award"
- `doe_nnsa_rfp_section_m` R11 (evaluation): "The Government will evaluate the Offeror’s proposed UPF Interface Management Approach"
- `doe_nnsa_rfp_section_m` R12 (evaluation): "The Government will evaluate the effectiveness of the Offeror's approach in using small businesses"
- `doe_nnsa_rfp_section_m` R13 (evaluation): "The total evaluated price will not be rated, but will be used in determining the best value to the Government"
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
- `in_esic_hyderabad_cpwd_2023` R03 (deadline, mandatory): "Period for submission of original EMD/ Eligibility documents by the Lowest Bidder Within one week from the date of opening the financial bid"
- `in_esic_hyderabad_cpwd_2023` R22 (submission, mandatory): "The bidder does not upload all the documents (including GST Registration) as stipulated in the bid document"
- `in_nhai_makhu_epc_2024` R09 (deadline, mandatory): "on or before 28.08.2024 (upto 1100 hours IST)"
- `in_nhai_makhu_epc_2024` R26 (form): "Self- certification by the Bidder that its Bid meets the Local Content requirement"
- `in_sai_bhopal_cladding_2020` R02 (form, mandatory): "Hard copy of the same must be sent to the Office of Director Incharge, Sports Authority of India, Central Regional Centre, Bhopalon or before Bid Submission Date & Time"
- `in_sai_bhopal_cladding_2020` R12 (form, mandatory): "Statutory Auditor’s Certificate is mandatory"
- `in_sai_bhopal_cladding_2020` R19 (qualification, mandatory): "CPWD/PWD Registration"
- `in_sai_bhopal_cladding_2020` R21 (evaluation): "Technical bids will be evaluated as per qualification criteria given in Section III"
- `in_sai_bhopal_cladding_2020` R22 (evaluation): "The successful bidder will be the one who emerges overall L-1 out of responsive bids"
- `k12_school_ifb` R10 (form, mandatory): "Designation of Subcontractors"
- `k12_school_ifb` R11 (form, mandatory): "Non-Collusion Declaration"
- `k12_school_ifb` R12 (form, mandatory): "Bidder's Certificate Regarding Workers' Compensation"
- `k12_school_ifb` R13 (form, mandatory): "Iran Contracting Act Certification"
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
- `usace_1985_ifb_ocr` R02 (submission, mandatory): "procecute the work diligently"
- `usace_1985_ifb_ocr` R03 (submission, mandatory): "complete the entire work ready for use not later than 3k!l days after the contractor receives the notice to proceed"
- `usace_1985_ifb_ocr` R05 (deadline, mandatory): "allow n~ days for acceptance of its bid"
- `usace_1985_ifb_ocr` R06 (form, mandatory): "give bond within 1~ detys after receipt of the forms by the bidder"
- `usace_1985_ifb_ocr` R14 (submission): "agrees to use its best efforts to place subcontractors in accorda~ce with this policy"
- `water_main_srf_ifb` R06 (form, mandatory): "shall submit EPA Forms 6100-3 and 6100-4 with the bid"
- `water_main_srf_ifb` R08 (form, mandatory): "shall submit the Certification Regarding Debarment (Attachment E)"
