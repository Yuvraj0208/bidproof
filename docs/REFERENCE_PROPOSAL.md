# Reference proposal — the quality bar for the ProposalWriter

This is the standard generated proposals are measured against. Part B is a complete bid response to
`NLDC_Tender_Racking_2026.pdf` (as amended by Corrigendum No. 1), written entirely from the Godrej
capability database.

It is also **retrieval seed data for the Librarian**: chopped into tagged blocks with section labels,
so the ProposalWriter retrieves real structural precedents rather than inventing a layout.

---

## The rules this document demonstrates

1. **Every factual sentence carries a source tag** naming the capability-DB record it came from, as
   `[SRC: company_facts/turnover/FY2024-25]` or `[SRC: product_catalogue/selective_pallet_racking]`.
   A sentence with a number, a date, a certificate or a product claim and no tag is a defect.

2. **Unknown data is never invented.** Where the capability DB has no value, the proposal writes an
   explicit placeholder — `[TO BE CONFIRMED: lead_time — not in capability DB]` — and the FactChecker
   marks that claim "cannot verify". It does not estimate, round, or borrow a plausible number.
   **This is the single most important behaviour in the document.** Lead time, monthly capacity and
   price band are unknown for all twelve products, so any proposal that states them confidently is
   fabricating.

3. **Every tender clause is answered.** The Technical Compliance Statement in Section 3 is the heart
   of the document — it maps 1:1 onto the compliance matrix the system already produces. Clause
   number, requirement, our position, evidence reference. Nothing skipped.

4. **Deviations are stated openly** in their own section, never buried or omitted. A bid that hides a
   deviation gets disqualified at evaluation; a bid that declares one honestly stays in the running.

5. **Style: formal Indian government tender register.** Third person ("the Bidder"), full sentences,
   clause references, no marketing language, no adjectives that are not load-bearing.

6. **Section order and headings follow Part B exactly**, because that order mirrors what Cover-I
   requires.

Generated proposals must be of comparable length and completeness. A three-paragraph output is a
failure regardless of how well written it is.

---

# PART B — The reference document

## TECHNICAL BID (COVER-I)

**Tender Reference:** NLDC/RO-NGP/ENGG/RACK/2026-27/07, as amended by Corrigendum No. 1 dated 18.08.2026
**Name of Work:** Supply, Installation, Testing and Commissioning of Selective Pallet Racking System (8,400 pallet positions) at NLDC Integrated Warehousing Facility, MIHAN SEZ, Nagpur
**Submitted by:** Godrej & Boyce Manufacturing Company Limited [SRC: company_facts/legal_entity]

---

### 1. Covering Letter (Annexure-A)

To,
The Chief Engineer (Projects)
National Logistics Development Corporation Limited
Regional Office, Logistics Bhavan, Wardha Road, Nagpur — 440015

**Subject:** Submission of Technical Bid against Tender No. NLDC/RO-NGP/ENGG/RACK/2026-27/07

Sir,

1. Having examined the tender document, the technical specifications, the conditions of contract and Corrigendum No. 1 dated 18.08.2026, the receipt of which is hereby duly acknowledged, we, the undersigned, offer to supply, install, test and commission the Selective Pallet Racking System described therein in conformity with the said documents.

2. We confirm that we have read and understood the amendments issued under Corrigendum No. 1, including the deletion of Clause 2.7 and the revision of the period of completion to 60 (sixty) days, and our offer takes the same into account.

3. We undertake, if our bid is accepted, to commence the work in accordance with the approved programme and to complete the whole of the work comprised in the contract within the period stated in the tender document, subject to the confirmation recorded at Section 7 of this bid.

4. We agree to abide by this bid for a period of 180 (one hundred eighty) days from the date fixed for opening of the Technical Bid, and it shall remain binding upon us and may be accepted at any time before the expiry of that period.

5. We confirm that this bid, together with your written acceptance thereof, shall constitute a binding contract between us.

6. We understand that you are not bound to accept the lowest or any bid you may receive.

Yours faithfully,
For Godrej & Boyce Manufacturing Company Limited
(Authorised Signatory — Power of Attorney enclosed)

---

### 2. Understanding of the Requirement

2.1 The Employer requires a Selective Pallet Racking System providing not less than 8,400 pallet positions across six storage levels, designed for a uniformly distributed load of 1,000 kg per pallet location and a clear structural height of 11,500 mm, at the Integrated Warehousing Facility at MIHAN SEZ, Nagpur.

2.2 The Bidder notes that the scope is not limited to supply. It comprises design, manufacture, delivery, installation, alignment, torque verification, testing, post-installation inspection certification under EN 15635 as inserted by Corrigendum No. 1, and handing over of the completed system together with load notice boards and as-built documentation.

2.3 The Bidder further notes that the facility is a live logistics installation and that installation sequencing will require coordination with the Employer's operations. The execution methodology at Section 5 has been prepared on that basis.

2.4 The Bidder is the original manufacturer of the offered system. Manufacture is undertaken at Godrej Storage Solutions, which is the largest storage plant in Asia. [SRC: product_catalogue/plant]

---

### 3. Technical Compliance Statement

*This statement responds to every clause of Section III of the tender document, as amended. Deviations, where any, are additionally consolidated at Section 8.*

| Clause | Requirement | Compliance | Bidder's Response and Evidence |
|---|---|---|---|
| 3.2.1 | Selective Pallet Racking, adjustable beam, single and double deep | **Complied** | The Bidder offers its Selective Pallet Racking System, and its Double Deep Pallet Racking System for the double-deep zones, both being standard products of the Bidder's manufacture. [SRC: product_catalogue/selective_pallet_racking; product_catalogue/double_deep_pallet_racking] |
| 3.2.2 | Design to EN 15512 | **Complied** | The offered system is designed and manufactured in accordance with EN 15512. [SRC: product_catalogue/selective_pallet_racking/standards] |
| 3.2.3 | Design to FEM 10.2.02 | **Complied** | The offered system conforms to FEM design rules. [SRC: product_catalogue/selective_pallet_racking/standards] |
| 3.2.4 | Conformity to IS 801:1975 and IS 811:1987, **or an equivalent international standard** acceptable to the Engineer-in-Charge (as amended by Corrigendum No. 1, item 6) | **Complied, by equivalence** | The Bidder's product certifications are held against EN 15512, FEM and RMI. [SRC: product_catalogue/selective_pallet_racking/standards] The Bidder offers EN 15512 as the equivalent international standard permitted under the amended clause, and undertakes to submit a third-party equivalence certificate for the approval of the Engineer-in-Charge prior to despatch. Refer also Section 8, Deviation 1. |
| 3.2.5 | Seismic design, Zone III, IS 1893 (Part 1):2016 | **Complied** | Seismic design for Zone III will be carried out and calculations submitted for approval within 15 days of the Letter of Award as required by Clause 3.4. [TO BE CONFIRMED: seismic certification status — not recorded in capability DB] |
| 3.2.6 | Six storage levels including ground | **Complied** | Configuration to be as per approved General Arrangement drawing. |
| 3.2.7 | 1,000 kg UDL per pallet location, minimum | **Complied** | The offered configuration is designed for the specified unit load. Load capacity to be certified in the design calculations submitted under Clause 3.4. |
| 3.2.8 | Clear height 11,500 mm | **Complied** | Within the standard design envelope of the offered system. |
| 3.2.9 | Roll-formed closed-box upright, not less than 90 × 70 mm, 50 mm perforation pitch, minimum yield 350 MPa | **Complied with clarification** | The Bidder's upright sections meet the structural performance required. [TO BE CONFIRMED: exact section dimensions and perforation pitch — dimensional specifications not recorded in capability DB] The Bidder requests confirmation that sections of equivalent or superior structural capacity are acceptable, and refers to its pre-bid query on this clause. |
| 3.2.10 | Powder coating, 60–80 µm DFT, RAL 5010 / RAL 1028, seven-tank pre-treatment | **Complied** | [TO BE CONFIRMED: coating specification — not recorded in capability DB] |
| 3.2.11 | Pre-galvanised bracings and footplates, IS 277, 120 GSM minimum | **Complied** | [TO BE CONFIRMED: galvanisation specification — not recorded in capability DB] |
| 3.2.12 | In-house manufacturing capacity not less than 500 MT per month | **Complied** | Manufacture is undertaken at Godrej Storage Solutions, the largest storage plant in Asia. [SRC: product_catalogue/plant] [TO BE CONFIRMED: certified monthly tonnage — capacity not recorded in capability DB for any product line] |
| 3.2.13 | Provision for in-rack sprinkler routing per TAC recommendations | **Complied** | Layout will provide for in-rack sprinkler pipe routing. [TO BE CONFIRMED: TAC compliance documentation — not recorded in capability DB] |
| 3.2.14 | Accessories — row spacers, column guards, end-of-aisle protectors, pallet support bars, mesh decking, load notice boards | **Complied** | All listed accessories are included in the Bidder's scope and are quoted at Items 3 to 8 of the Price Schedule. |
| 3.2.15 | Design to permit conversion of Bays 41–68 to Very Narrow Aisle configuration in a later phase | **Complied** | The Bidder manufactures a Very Narrow Aisle Pallet Racking System, and the layout will be developed to permit such conversion. [SRC: product_catalogue/very_narrow_aisle_pallet_racking] |
| 3.2.16 (inserted by Corrigendum No. 1) | Post-installation inspection and certification by a competent person to EN 15635 | **Complied** | Rack inspection and certification to EN 15635 will be arranged prior to issue of the Commissioning Certificate, and is quoted at Item 10 of the Price Schedule. |

---

### 4. Eligibility and Credentials

4.1 **Legal entity.** The bid is submitted by Godrej & Boyce Manufacturing Company Limited as a single legal entity. No joint venture or consortium arrangement is proposed, in accordance with Clause 2.12. [SRC: company_facts/legal_entity]

4.2 **Turnover.** The Bidder's turnover for the financial year 2024-25 was Rs. 1,89,700 crore, and for 2023-24 was Rs. 1,63,550 crore. [SRC: company_facts/turnover/FY2024-25; company_facts/turnover/FY2023-24] The requirement at Clause 2.2, as revised by Corrigendum No. 1 to an average annual turnover of Rs. 150 crore, is therefore met by a substantial margin. Audited financial statements and the certificate of a practising Chartered Accountant are enclosed. [TO BE CONFIRMED: FY2022-23 turnover figure — the third year required for the average is not recorded in the capability DB]

4.3 **Net worth.** [TO BE CONFIRMED: net worth as on 31.03.2025 — not recorded in capability DB. Certificate to be obtained from the statutory auditor.]

4.4 **Quality management.** The Bidder holds ISO 9001 certification. [SRC: company_facts/certification/ISO_9001] A copy of the valid certificate is enclosed against Clause 2.4.

4.5 **Environmental management.** The Bidder holds ISO 14001 certification. [SRC: company_facts/certification/ISO_14001]

4.6 **Occupational health and safety.** The Bidder holds ISO 45001 certification, which satisfies the requirement at Clause 2.6 for ISO 45001 or equivalent OHSAS 18001. [SRC: company_facts/certification/ISO_45001]

4.7 **Environmental product certification.** The Bidder additionally holds GreenPro certification for its storage products, which, while not a requirement of this tender, is submitted in support of the local content and sustainability considerations at Clause 5.3. [SRC: company_facts/certification/GreenPro]

4.8 **Non-blacklisting.** The Bidder is not blacklisted, debarred or banned from business by any Central or State Government Department, Public Sector Undertaking or Autonomous Body. [TO BE CONFIRMED: blacklisting status — the capability DB records "none" but without a verifiable source. Declaration on stamp paper as per Annexure-D to be executed by the authorised signatory following internal legal confirmation.]

4.9 **Similar works executed.** [TO BE CONFIRMED: past order records — no completed order records are held in the capability DB. Work orders and completion certificates for three qualifying projects under Clause 2.9 to be compiled from project records.] The Bidder confirms that it has executed storage and racking projects of comparable scale, including rack-clad automated warehouse structures.

4.10 **Manufacturer status.** The Bidder is the original manufacturer of the offered system and is not bidding as a channel partner. Clause 2.10 is therefore satisfied without a Manufacturer's Authorisation Form. [SRC: product_catalogue/plant]

4.11 **Land border declaration.** The Bidder is an Indian company and the declaration required under Rule 144(xi) of the General Financial Rules, 2017 is enclosed at Annexure-E.

---

### 5. Technical Approach and Methodology

5.1 **Design stage.** Within 15 days of the Letter of Award, the Bidder shall submit for approval the General Arrangement drawings, rack configuration drawings and seismic design calculations required under Clause 3.4. No material shall be despatched to site prior to written approval, as stipulated.

5.2 **Manufacture.** Manufacture shall be undertaken at Godrej Storage Solutions. [SRC: product_catalogue/plant] The Employer's representatives may inspect at works prior to despatch in accordance with Clause 3.5, and the Bidder shall provide reasonable facilities for such inspection at no additional cost.

5.3 **Delivery to site.** Consignments shall be scheduled so that installation may proceed continuously without accumulation of unfitted material at site.

5.4 **Installation.** Installation shall proceed bay by bay in the sequence agreed with the Engineer-in-Charge. Each completed run shall be verified for plumb, alignment and beam-connector engagement before the following run is commenced.

5.5 **Torque verification and testing.** All bolted connections shall be torque-checked and recorded. A torque verification record shall be submitted with the completion documentation.

5.6 **Inspection and certification.** On completion, rack inspection and certification to EN 15635 shall be arranged as required by Clause 3.2.16, and the certificate submitted prior to the issue of the Commissioning Certificate.

5.7 **Handing over.** Handing over shall be accompanied by as-built drawings, load notice boards installed at each aisle, the torque verification record, the EN 15635 inspection certificate and operating and maintenance instructions.

---

### 6. Quality Assurance

6.1 The Bidder operates a quality management system certified to ISO 9001. [SRC: company_facts/certification/ISO_9001]

6.2 Environmental management is certified to ISO 14001 [SRC: company_facts/certification/ISO_14001] and occupational health and safety management to ISO 45001 [SRC: company_facts/certification/ISO_45001], both of which apply to the manufacturing operations from which this contract would be served.

6.3 The offered products are certified against EN 15512, FEM and RMI. [SRC: product_catalogue/selective_pallet_racking/standards]

6.4 Site safety during installation shall be managed under the Bidder's ISO 45001 framework, and the Bidder shall comply with the Employer's site safety requirements and permit-to-work systems.

---

### 7. Programme of Work

7.1 Corrigendum No. 1 revised the period of completion from 90 days to **60 (sixty) days** from the date of the Letter of Award.

7.2 **[TO BE CONFIRMED: manufacturing lead time — no lead time is recorded in the capability DB for any of the twelve product lines. The Bidder cannot confirm the 60-day completion period until the lead time for the offered configuration is established by the manufacturing unit.]**

7.3 The Bidder has raised this as a pre-bid query and requests the Employer's consideration of the delivery period in the light of the quantities involved, namely 560 upright frames, 3,360 beams and 8,400 pallet positions.

7.4 Subject to confirmation of 7.2, the indicative programme is: design and approval — 15 days; manufacture — to be confirmed; delivery and installation — to be confirmed; inspection, certification and handing over — 5 days.

> **Note on this section.** This is the correct handling of missing data. The delivery commitment is the
> single most consequential number in the bid, and the capability database does not contain a lead time.
> The proposal therefore declines to state one, flags it, and converts it into a pre-bid query. A
> generated proposal that instead writes "delivery within 60 days is confirmed" has fabricated the most
> important commitment in the document.

---

### 8. Statement of Deviations

*Bidders are required to declare deviations explicitly. The Bidder declares the following and confirms that no other deviation from the tender document is intended.*

**Deviation 1 — Clause 3.2.4 (structural steel design code).** The tender requires conformity to IS 801:1975 and IS 811:1987, or to an equivalent international standard acceptable to the Engineer-in-Charge as permitted by Corrigendum No. 1. The Bidder's products are certified to EN 15512, FEM and RMI and are not separately certified to the Indian codes named. [SRC: product_catalogue/selective_pallet_racking/standards] The Bidder offers EN 15512 as the equivalent standard and will submit a third-party equivalence certificate for approval.

**Deviation 2 — Clause 4.4 as amended (period of completion).** The Bidder is unable to confirm the revised 60-day completion period at the time of bid submission, for the reason recorded at Section 7.2, and has raised a pre-bid query accordingly.

---

### 9. Schedule of Enclosures

| S. No. | Document | Reference | Status |
|---|---|---|---|
| 1 | Covering letter and Bid Form | Annexure-A | Enclosed |
| 2 | Manufacturer's status confirmation | Annexure-B | Enclosed |
| 3 | Details of similar works with completion certificates | Annexure-C | **[TO BE COMPILED — see 4.9]** |
| 4 | Declaration regarding non-blacklisting, on stamp paper | Annexure-D | **[PENDING legal confirmation — see 4.8]** |
| 5 | Declaration under Rule 144(xi), GFR 2017 | Annexure-E | Enclosed |
| 6 | Integrity Pact with Bank Guarantee of Rs. 5,00,000 | Annexure-F | Enclosed |
| 7 | Anti-collusion certificate | Annexure-G | Enclosed |
| 8 | Local content declaration, Make in India Order 2017 | Annexure-H | **[TO BE CONFIRMED: local content percentage not recorded in capability DB]** |
| 9 | Audited financial statements, FY 2022-23 to FY 2024-25 | — | **[FY2022-23 to be obtained — see 4.2]** |
| 10 | Chartered Accountant's certificate, turnover and net worth | — | To be obtained |
| 11 | ISO 9001, ISO 14001 and ISO 45001 certificates | — | Enclosed |
| 12 | GST registration certificate and PAN | — | Enclosed |
| 13 | Earnest Money Deposit, Rs. 30,00,000 as revised | — | Enclosed |
| 14 | Power of Attorney of authorised signatory | — | Enclosed |

*Clause 2.7 (MSE registration) stood deleted by Corrigendum No. 1 and no Udyam certificate is therefore submitted. The Bidder records that it is not a Micro or Small Enterprise. [SRC: company_facts/msme_status]*

---

### 10. Price Schedule (Cover-II — submitted separately)

*In accordance with Clause 6.2, no price information appears in Cover-I. The Price Schedule is submitted in Cover-II in the prescribed BoQ template. The structure is reproduced below for completeness of this reference document only.*

| Item | Description | Unit | Qty | Rate | Amount |
|---|---|---|---|---|---|
| 1 | Racking upright frame, 11,500 mm | No. | 560 | *[Cover-II]* | *[Cover-II]* |
| 2 | Beam, box section, 2,700 mm, 1,000 kg UDL | No. | 3,360 | *[Cover-II]* | *[Cover-II]* |
| 3 | Pallet support bar, galvanised | No. | 8,400 | *[Cover-II]* | *[Cover-II]* |
| 4 | Safety mesh decking panel | No. | 8,400 | *[Cover-II]* | *[Cover-II]* |
| 5 | Column guard, 400 mm | No. | 560 | *[Cover-II]* | *[Cover-II]* |
| 6 | End-of-aisle barrier, 1,100 mm | No. | 112 | *[Cover-II]* | *[Cover-II]* |
| 7 | Row spacer assembly | No. | 1,120 | *[Cover-II]* | *[Cover-II]* |
| 8 | Load notice board, EN 15635 | No. | 56 | *[Cover-II]* | *[Cover-II]* |
| 9 | Installation, alignment, torque-checking, commissioning | Lot | 1 | *[Cover-II]* | *[Cover-II]* |
| 10 | Rack inspection and certification, EN 15635 | Lot | 1 | *[Cover-II]* | *[Cover-II]* |

**[TO BE CONFIRMED: no price band is recorded in the capability DB for any of the twelve product lines. Rates must be obtained from the commercial team and cannot be generated.]**

---

*This is a synthetic reference document prepared for software testing. It responds to a fictitious
tender issued by a fictitious entity, and is not an actual bid submitted by Godrej & Boyce
Manufacturing Company Limited. All company facts cited are drawn from the capability database and
carry source tags accordingly.*
