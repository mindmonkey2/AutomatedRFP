# Requirement extraction eval: keyword

Run 2026-11-12 15:05 UTC · 11 cases · 266 labelled requirements · 0s

| Metric | Value |
| --- | --- |
| **Recall** (requirements found) | **49.2%** (131/266) |
| Mandatory recall | 52.7% |
| Kind accuracy (of found) | 20.6% |
| Page accuracy (of found) | 100.0% |
| Traps extracted (owner obligations taken as bidder requirements) | 8 of 32 |
| Extracted items not in the answer key | 88 of 219 |

## Recall by requirement kind

| Kind | Found | Recall |
| --- | --- | --- |
| deadline | 7/22 | 32% |
| evaluation | 0/24 | 0% |
| form | 31/75 | 41% |
| format | 31/35 | 89% |
| page_limit | 6/13 | 46% |
| qualification | 23/36 | 64% |
| question | 6/15 | 40% |
| submission | 27/46 | 59% |

## By source

| Source | Cases | Recall |
| --- | --- | --- |
| real | 6 | 46.3% (76/164) |
| synthetic | 5 | 53.9% (55/102) |

## By case

| Case | Source | Recall | Mandatory | Extracted | Traps hit |
| --- | --- | --- | --- | --- | --- |
| county_cmar_rfp | synthetic | 29% (7/24) | 6/17 | 9 | 1 |
| doe_nnsa_rfp_section_l | real | 75% (42/56) | 29/39 | 58 | 1 |
| doe_nnsa_rfp_section_m | real | 15% (2/13) | 2/6 | 6 | 1 |
| federal_design_build | synthetic | 56% (14/25) | 13/19 | 16 | 0 |
| in_esic_hyderabad_cpwd_2023 | real | 24% (6/25) | 5/23 | 21 | 3 |
| in_nhai_makhu_epc_2024 | real | 31% (10/32) | 10/26 | 31 | 1 |
| in_sai_bhopal_cladding_2020 | real | 23% (5/22) | 5/18 | 11 | 0 |
| k12_school_ifb | synthetic | 75% (15/20) | 14/19 | 18 | 0 |
| university_ae_rfq | synthetic | 42% (8/19) | 8/13 | 8 | 0 |
| usace_1985_ifb_ocr | real | 69% (11/16) | 4/8 | 30 | 1 |
| water_main_srf_ifb | synthetic | 79% (11/14) | 10/13 | 11 | 0 |

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
- `doe_nnsa_rfp_section_l` R02 (submission): "The Offeror shall not submit the information required at Sections L-9(c), L-9(d), and L-10 (a), Criterion 1, Past Performance, for team members with a proposed work scope less than $10 million"
- `doe_nnsa_rfp_section_l` R05 (deadline): "no later than 2:00pm EST November 23, 2020"
- `doe_nnsa_rfp_section_l` R07 (submission): "Only potential Offerors that submit an intent to bid in accordance with L-29 below will be granted access to this reading room information"
- `doe_nnsa_rfp_section_l` R10 (format): "The following edit feature settings shall be applied: inserted text--red and underlined; deleted text--struck through in black"
- `doe_nnsa_rfp_section_l` R15 (submission, mandatory): "Volume I – The Offer - One (1) signed original"
- `doe_nnsa_rfp_section_l` R16 (submission, mandatory): "Volume II – Technical and Management Information – One (1) original"
- `doe_nnsa_rfp_section_l` R17 (submission, mandatory): "Volume III – Cost Information – One (1) original"
- `doe_nnsa_rfp_section_l` R25 (format, mandatory): "Material may not be incorporated by reference in Volume II (including any information in Volume I or III) as a means to circumvent the page limitations"
- `doe_nnsa_rfp_section_l` R26 (page_limit, mandatory): "Resumes of Key Personnel, which are limited to five (5) pages each"
- `doe_nnsa_rfp_section_l` R27 (page_limit, mandatory): "except for the CEO or President’s resume, which is limited to seven (7) pages"
- `doe_nnsa_rfp_section_l` R28 (page_limit, mandatory): "UPF Interface Management Approach, limited to ten (10) pages"
- `doe_nnsa_rfp_section_l` R29 (page_limit, mandatory): "limited to eight (8) pages per PPIF"
- `doe_nnsa_rfp_section_l` R44 (submission, mandatory): "Any exceptions or deviations by the Offeror to the terms and conditions stated in this solicitation"
- `doe_nnsa_rfp_section_l` R56 (submission, mandatory): "Offerors are prohibited from submitting multiple offers/proposals as a prime contractor or parent company"
- `doe_nnsa_rfp_section_m` R01 (submission, mandatory): "Any exceptions or deviations by the Offeror to the terms and conditions stated in this solicitation for inclusion in the resulting contract may make the offer unacceptable for award"
- `doe_nnsa_rfp_section_m` R02 (submission, mandatory): "requires that the Offeror provide enough information in its statement to allow a meaningful evaluation by the Government"
- `doe_nnsa_rfp_section_m` R04 (form, mandatory): "A Performance Guarantee Agreement in accordance with the requirements of the Solicitation’s Section L provision L-6"
- `doe_nnsa_rfp_section_m` R05 (evaluation): "The Government intends to award one contract to the responsible Offeror whose proposal is responsive to the solicitation and is determined to be the best value to the Government"
- `doe_nnsa_rfp_section_m` R06 (evaluation): "the Technical and Management Criteria, when combined, are significantly more important than the Cost Criterion"
- `doe_nnsa_rfp_section_m` R07 (evaluation): "The Government will evaluate the Offeror's recent, relevant past performance"
- `doe_nnsa_rfp_section_m` R08 (evaluation): "The Government will evaluate the Offeror’s Sites Organization, Key Personnel resumes, and information provided by Key Personnel references"
- `doe_nnsa_rfp_section_m` R10 (qualification, mandatory): "Proposed Key Personnel who are under a service commitment for the performance of another NNSA M&O contract at the projected time of contract award"
- `doe_nnsa_rfp_section_m` R11 (evaluation): "The Government will evaluate the Offeror’s proposed UPF Interface Management Approach"
- `doe_nnsa_rfp_section_m` R12 (evaluation): "The Government will evaluate the effectiveness of the Offeror's approach in using small businesses"
- `doe_nnsa_rfp_section_m` R13 (evaluation): "The total evaluated price will not be rated, but will be used in determining the best value to the Government"
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
- `in_esic_hyderabad_cpwd_2023` R01 (deadline, mandatory): "Last Date & Time of Bid submission. 07.06.2023, 11.00 AM"
- `in_esic_hyderabad_cpwd_2023` R02 (form, mandatory): "The original EMD should be submitted in the office of Construction Branch"
- `in_esic_hyderabad_cpwd_2023` R03 (deadline, mandatory): "Period for submission of original EMD/ Eligibility documents by the Lowest Bidder Within one week from the date of opening the financial bid"
- `in_esic_hyderabad_cpwd_2023` R04 (submission, mandatory): "Period of Completion 12 Months"
- `in_esic_hyderabad_cpwd_2023` R05 (qualification, mandatory): "The bidder should have registration with CPWD/State PWD /MES/Railways/BSNL"
- `in_esic_hyderabad_cpwd_2023` R06 (qualification, mandatory): "The Bidder should have satisfactorily completed similar works during the last Seven years"
- `in_esic_hyderabad_cpwd_2023` R07 (form, mandatory): "This should be certified by an officer not below the rank of Executive Engineer/Project Manager"
- `in_esic_hyderabad_cpwd_2023` R09 (qualification, mandatory): "Average Annual Financial Turn over of Rs.14,97,536-00"
- `in_esic_hyderabad_cpwd_2023` R10 (qualification, mandatory): "The bidder should not have incurred any loss (profit after tax should be positive) in more than two years"
- `in_esic_hyderabad_cpwd_2023` R11 (qualification, mandatory): "The solvency of Rs bidder should have Rs11,98,028-00"
- `in_esic_hyderabad_cpwd_2023` R12 (form, mandatory): "The past experience in similar nature of work should be supported by certificates issued by the client’s organisation"
- `in_esic_hyderabad_cpwd_2023` R13 (qualification, mandatory): "The tenderer must be registered with following statutory authorities and must also furnish self attested copies ESI, EPF, GST along with last six months payment receipts"
- `in_esic_hyderabad_cpwd_2023` R14 (form): "an affidavit in this matter to be enclosed / uploaded that firm has never been employed"
- `in_esic_hyderabad_cpwd_2023` R15 (form, mandatory): "The Earnest Money Deposit (EMD) for Rs.59,901-00(Rupees Fifty nine thousand nine hundred and one only) Which shall be in the form of Insurance Surety Bonds"
- `in_esic_hyderabad_cpwd_2023` R18 (submission, mandatory): "Conditional bid will not to be accepted"
- `in_esic_hyderabad_cpwd_2023` R22 (submission, mandatory): "The bidder does not upload all the documents (including GST Registration) as stipulated in the bid document"
- `in_esic_hyderabad_cpwd_2023` R23 (form, mandatory): "Copy of EMD."
- `in_esic_hyderabad_cpwd_2023` R24 (form, mandatory): "Letter of Transmittal."
- `in_esic_hyderabad_cpwd_2023` R25 (form, mandatory): "Certificate of Work Experience as per Form – A"
- `in_nhai_makhu_epc_2024` R02 (qualification, mandatory): "DSC should be in the name of the authorized signatory as authorized in Appendix III"
- `in_nhai_makhu_epc_2024` R06 (qualification, mandatory): "Registration should be valid at least up to the date of submission of BID"
- `in_nhai_makhu_epc_2024` R07 (form, mandatory): "bidders have to pay a sum of Rs. 10,000/- (Rupees ten thousand only) as a cost of the RFP process (non-refundable)"
- `in_nhai_makhu_epc_2024` R09 (deadline, mandatory): "on or before 28.08.2024 (upto 1100 hours IST)"
- `in_nhai_makhu_epc_2024` R10 (format, mandatory): "scanned in different files (in PDF or RAR format such that file size is not more than 30 MB)"
- `in_nhai_makhu_epc_2024` R11 (form, mandatory): "Appendix IA (Letter comprising the Technical Bid) including Annexure-I to VI and supporting certificates / documents"
- `in_nhai_makhu_epc_2024` R12 (form, mandatory): "Power of Attorney for signing the BID as per the format at Appendix-III"
- `in_nhai_makhu_epc_2024` R13 (form): "Power of Attorney for Lead Member of Joint Venture as per the format at Appendix-IV"
- `in_nhai_makhu_epc_2024` R14 (form): "Joint Bidding Agreement for Joint Venture as per the format at"
- `in_nhai_makhu_epc_2024` R15 (form, mandatory): "BID Security of Rs. 46.29 lakh (Rupees forty six lakh twenty nine thousand only) in the form of Insurance Surety Bond"
- `in_nhai_makhu_epc_2024` R16 (form, mandatory): "Proof of online payment towards the cost of Bid document of Rs. 10,000/-"
- `in_nhai_makhu_epc_2024` R18 (form, mandatory): "An undertaking from the person having PoA referred to in Sub. Clause-(b) above that they agree and abide by the Bid documents"
- `in_nhai_makhu_epc_2024` R19 (form, mandatory): "Annexure-VIII of Appendix – IA showing details of all ongoing project works"
- `in_nhai_makhu_epc_2024` R20 (form, mandatory): "Copy of Memorandum and Articles of Association of the Bidder or of each Member"
- `in_nhai_makhu_epc_2024` R21 (form, mandatory): "Copies of duly audited complete annual accounts of the Bidder or of each member (in case of Joint Venture) for preceding 5 years"
- `in_nhai_makhu_epc_2024` R22 (form): "Copy of originals of experience certificates apostile at foreign origin, if any"
- `in_nhai_makhu_epc_2024` R23 (form, mandatory): "Certificate regarding Compliance with Restrictions under Rule 144 (xi) of the General Financial Rules (GFRs)"
- `in_nhai_makhu_epc_2024` R24 (form): "Copy of Registration from the Competent Authority as defined in Public Procurement Order No. F. No. 6/18/2019-PPD"
- `in_nhai_makhu_epc_2024` R26 (form): "Self- certification by the Bidder that its Bid meets the Local Content requirement"
- `in_nhai_makhu_epc_2024` R27 (form): "shall have to provide a Certificate from the Statutory Auditor or Cost Auditor of the Company"
- `in_nhai_makhu_epc_2024` R28 (submission, mandatory): "Original (in Envelope) by the Lowest Bidder before issuance of Letter of Acceptance (LOA)"
- `in_nhai_makhu_epc_2024` R29 (deadline, mandatory): "Account Payee demand draft or Banker’s Cheque are submitted physically latest within 5 working days of the Bid Due Date"
- `in_sai_bhopal_cladding_2020` R02 (form, mandatory): "Hard copy of the same must be sent to the Office of Director Incharge, Sports Authority of India, Central Regional Centre, Bhopalon or before Bid Submission Date & Time"
- `in_sai_bhopal_cladding_2020` R03 (deadline, mandatory): "Bid Submission End Date 20.02.2020 (04:00 PM)"
- `in_sai_bhopal_cladding_2020` R04 (deadline): "Date and time of pre bid conference* 14.02.2020 (11:00 AM)"
- `in_sai_bhopal_cladding_2020` R05 (deadline): "Last date for submission of queries/ clarification made during the pre bid conference in writing ** 14.02.2020 (11:00 AM)"
- `in_sai_bhopal_cladding_2020` R06 (submission, mandatory): "Bidders shall ensure that their Bids, complete in all respect should be uploaded online before the closing date and time"
- `in_sai_bhopal_cladding_2020` R10 (form, mandatory): "Enclose copy of certificate incorporation/registration"
- `in_sai_bhopal_cladding_2020` R12 (form, mandatory): "Statutory Auditor’s Certificate is mandatory"
- `in_sai_bhopal_cladding_2020` R13 (qualification, mandatory): "Copies of Completion certificates of Civil works executed successfully during the last five years"
- `in_sai_bhopal_cladding_2020` R14 (form, mandatory): "Satisfactory completion certificates issued by relevant authority not less than the rank of Section Officer be enclosed"
- `in_sai_bhopal_cladding_2020` R15 (qualification, mandatory): "The bidders should not have been debarred/blacklisted by any state/central government/PSUs"
- `in_sai_bhopal_cladding_2020` R16 (form, mandatory): "Enclose blacklisting declaration in the format given in Section IV (I)"
- `in_sai_bhopal_cladding_2020` R17 (qualification, mandatory): "The bidder should have a valid GST No. or should have registered under GST"
- `in_sai_bhopal_cladding_2020` R18 (form, mandatory): "copy of GST Registration certificate"
- `in_sai_bhopal_cladding_2020` R19 (qualification, mandatory): "CPWD/PWD Registration"
- `in_sai_bhopal_cladding_2020` R20 (form, mandatory): "Enclose copy of Registration certificate"
- `in_sai_bhopal_cladding_2020` R21 (evaluation): "Technical bids will be evaluated as per qualification criteria given in Section III"
- `in_sai_bhopal_cladding_2020` R22 (evaluation): "The successful bidder will be the one who emerges overall L-1 out of responsive bids"
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
- `usace_1985_ifb_ocr` R02 (submission, mandatory): "procecute the work diligently"
- `usace_1985_ifb_ocr` R03 (submission, mandatory): "complete the entire work ready for use not later than 3k!l days after the contractor receives the notice to proceed"
- `usace_1985_ifb_ocr` R05 (deadline, mandatory): "allow n~ days for acceptance of its bid"
- `usace_1985_ifb_ocr` R06 (form, mandatory): "give bond within 1~ detys after receipt of the forms by the bidder"
- `usace_1985_ifb_ocr` R14 (submission): "agrees to use its best efforts to place subcontractors in accorda~ce with this policy"
- `water_main_srf_ifb` R01 (deadline, mandatory): "Sealed bids are due at 11:00 a.m. on July 15, 2026"
- `water_main_srf_ifb` R06 (form, mandatory): "shall submit EPA Forms 6100-3 and 6100-4 with the bid"
- `water_main_srf_ifb` R08 (form, mandatory): "shall submit the Certification Regarding Debarment (Attachment E)"
