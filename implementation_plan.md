# Recommended Implementation Plan: Correspond (eOffice Transformation)

> **Context & Scope Note:**  
> In accordance with project steering decisions, **DSC Token and Aadhaar eSign integrations are placed on hold for future phases**. This plan focuses on core Secretariat operations, file referencing, workflow agility, smart diarization, records management, and executive analytics using native Frappe Framework capabilities.

---

## 1. Plan Overview & Sizing

The implementation is structured into **4 focused sprints / phases**, prioritizing the high-impact operational gaps that users experience daily in eOffice workflows:

```mermaid
flowchart TD
    subgraph Sprint 1 [Sprint 1: Workflow Agility & Referencing (Weeks 1-4)]
        S1_1[Pull Back Unread Files]
        S1_2[Park File & Hold Management]
        S1_3[Referencing Slips / Flagging 'Flag A-Z']
        S1_4[Security Watermarking & Dynamic Previews]
    end

    subgraph Sprint 2 [Sprint 2: Standard Government Drafting - DFA (Weeks 5-8)]
        S2_1[DFA Template Engine: OM, DO, Circular]
        S2_2[Multi-level Approval & Dispatch Register]
        S2_3[Outward Dispatch Numbering & Registry]
        S2_4[Unified Bi-Directional Linking]
    end

    subgraph Sprint 3 [Sprint 3: Officer Delegation & Smart Diarization (Weeks 9-12)]
        S3_1[Link Officer & Delegation Engine]
        S3_2[Receipt Barcode & QR Label Generator]
        S3_3[Duplicate Receipt Detection & OCR Ingestion]
        S3_4[VIP & Parliamentary Reference Tracker]
    end

    subgraph Sprint 4 [Sprint 4: Records Management & Executive Dashboards (Weeks 13-16)]
        S4_1[CSMOP Records Retention Schedules A/B/C]
        S4_2[Electronic Record Room & Weeding Out]
        S4_3[Desk Turnaround Time - TAT & Pendency Heatmaps]
        S4_4[eExchange Inter-Instance Export/Import]
    end

    Sprint 1 --> Sprint 2 --> Sprint 3 --> Sprint 4
```

---

## 2. Detailed Sprint Breakdown

### Sprint 1: Workflow Agility & Flagging/Referencing (Weeks 1 – 4)
*Goal: Provide essential day-to-day clerical and officer convenience matching eOffice navigation.*

#### 1.1 Pull Back Functionality
- **Objective:** Allow an officer/clerk who accidentally routed a file or forgot an attachment to recall it immediately.
- **Rules:**
  - Eligible only if the recipient has **not opened** the file, or no subsequent notings/forwarding have taken place.
  - Action creates a designated movement log entry: `Action: "Pulled Back"`.
  - Recipient's inbox removes the notification / item automatically.
- **Artifacts:**
  - `correspond_file.py`: `@frappe.whitelist() def pull_back_file(file_name, reason)`.
  - `file_movement_log`: Track `is_opened` timestamp on recipient's initial view.

#### 1.2 Park File & Hold Management
- **Objective:** Temporarily park a file awaiting external inputs (e.g., audit response, third-party report, court hearing).
- **Rules:**
  - Desk holder can set status to `Parked` with a mandatory reason category, detailed remarks, and a `park_until` target date.
  - Parked files are separated from the active Inbox into a dedicated **Parked Files** list to reduce clutter while preserving SLA clocks.
  - Daily scheduler automatically alerts custodian when `park_until` date arrives or expires.

#### 1.3 Flagging & Electronic Referencing (Flag 'A' to 'Z')
- **Objective:** Replicate physical tag slips ("Please see Flag A, page 12 of Flag B").
- **Rules:**
  - Attachments on `Inward Dak`, `Outward Dak`, or linked sub-files can be tagged with alphanumeric flags (`Flag A`, `Flag B`, etc.).
  - Rich-text editor toolbar in `Correspond Noting` gains a custom button: `Insert Reference Flag`.
  - In the green sheet, clicking `@Flag A` opens the target document split-view side pane directly scrolled to that attachment.

#### 1.4 Dynamic Security Watermarking
- **Objective:** Deter document leakage or unauthorized screenshots without requiring cryptographic hardware.
- **Rules:**
  - Server-side watermark overlay on PDF generation/view (using `PyPDF2` / `reportlab`).
  - Embeds: `Downloaded/Viewed by [Full Name] | [Desk Title] | [IP Address] | [Date & Time]`.

---

### Sprint 2: Government Drafting (DFA) & Outward Registry (Weeks 5 – 8)
*Goal: Transition draft letters into formal government office formats with full approval tracking.*

#### 2.1 Standard Government DFA Templates
- **Objective:** Standardize government correspondence into pre-formatted, print-ready templates.
- **Formats to Support:**
  - **Office Memorandum (OM):** For inter-departmental communications without salutation.
  - **Demi-Official (D.O.) Letter:** For personal officer-to-officer communications featuring official crest/letterhead.
  - **Office Order / Sanction Order:** For administrative sanctions with financial/budgetary head mappings.
  - **Circular / Notification:** For broad institutional distribution.
- **Implementation:**
  - Add `dfa_type` to `Outward Dak` with template-driven sections (Header, Subject, Paragraph Body, Endorsements/Copies To).

#### 2.2 Formal Draft Approval Lifecycle
- **Objective:** Review cycle for fair drafts before dispatch.
- **States:** `Drafting` -> `Submitted for Approval` -> `Approved` -> `Marked for Dispatch` -> `Dispatched`.
- **Workflow:**
  - Subordinate drafts the DFA on the right pane of the file.
  - Superior officer can approve, amend directly in red-line mode, or return for revision.
  - Once approved, the document freezes and transitions to the dispatch registry.

#### 2.3 Central Dispatch Register (Outward Register)
- **Objective:** Replace manual outward dispatch logbooks with an automated serial register.
- **Features:**
  - Auto-generated Dispatch Register No. per Office / Section: `<Section>/OUT/<YYYY>/<Sequence>`.
  - Dispatch Mode logging (Speed Post, Registered Post, Peon Book/Hand, Email, Portal).
  - Tracking/Consignment number capturing for physical dispatches.

---

### Sprint 3: Delegation & Smart Diarization (Weeks 9 – 12)
*Goal: Streamline receipt entry, scanning, duplicate handling, and prevent bottlenecks during officer leaves.*

#### 3.1 Link Officer / Delegation Engine
- **Objective:** Prevent file paralysis when an officer is on leave, training, or tour.
- **Mechanism:**
  - New DocType: `Correspond Delegation Rule` (`desk`, `delegate_desk`, `from_date`, `to_date`, `delegation_scope`, `approval_authority_limit`).
  - When active, incoming files and daks routed to the primary desk automatically appear in the delegate desk's inbox marked with a `[Delegated from <Officer>]` badge.
  - Action logs explicitly differentiate: *"Approved by Jane Doe on behalf of John Smith (Delegated)"*.

#### 3.2 Diarization Barcode & QR Label Printing
- **Objective:** Seamless physical-to-digital indexing.
- **Features:**
  - Upon saving an `Inward Dak`, generate a 2"x1" printable thermal/standard label containing:
    - Diarization Number (e.g., `DAK/GENL/2026/00142`)
    - Receipt Date & Originating Organization
    - Scannable QR code linking directly to the electronic receipt record.

#### 3.3 Duplicate Detection & OCR Pipeline
- **Objective:** Avoid duplicate diarization of the same letter received via email and post.
- **Features:**
  - Real-time check on `(sender_organization + external_reference_number + external_reference_date)`.
  - Asynchronous background task running Tesseract OCR on incoming PDF/image scans, populating searchable text for global Frappe search.

#### 3.4 VIP & Parliamentary Reference Dashboard
- **Objective:** Zero-delay tracking of high-priority correspondence.
- **Features:**
  - Flagging categories: *PMO Reference, MP/MLA Reference, Cabinet Note, RTI, Court Matter*.
  - Configurable SLA threshold timers (e.g., 3 days for PMO, 7 days for Parliamentary Questions).
  - Escalation notifications sent to Supervisory Desks as deadlines approach.

---

### Sprint 4: Records Lifecycle, Archival & Analytics (Weeks 13 – 16)
*Goal: Comply with statutory archival procedures and provide leadership with operational intelligence.*

#### 4.1 CSMOP Records Retention & Archival Classification
- **Objective:** Enforce structured life cycle on files after disposal.
- **Classification Categories:**
  - **Category A (Permanent):** High historical/legal value (to be microfilmed/permanently archived in Record Room).
  - **Category B (25 Years):** Policy decisions, department establishments.
  - **Category C (3, 5, or 10 Years):** Routine operational matters, auto-flagged for weeding upon expiry.
- **Workflow:**
  - Record Officer assigns Category and Retention Period upon closing a file.
  - File moves from Active Custody to the **Electronic Record Room**.

#### 4.2 Weeding & Destruction Register
- **Objective:** Systematic destruction of expired temporary records.
- **Features:**
  - Scheduled batch generation of "Files Due for Review / Destruction".
  - Two-stage approval (Reviewing Officer -> Record Room In-charge) generating a permanent, non-deletable `Certificate of Record Destruction`.

#### 4.3 Executive Turnaround Time (TAT) & Pendency Analytics
- **Objective:** Visibility into institutional delays.
- **Metrics & Dashboards:**
  - **Desk Pendency Index:** Aging breakdown (<3 days, 3-7 days, >15 days) per desk.
  - **File Turnaround Velocity:** Average duration a file remains at each desk profile.
  - **Section Disposal Ratio:** Ratio of files opened vs. files closed in a reporting month.

#### 4.4 eExchange Data Export/Import (Inter-Instance Federation)
- **Objective:** Enable sharing files between distinct sovereign organizations running Correspond.
- **Features:**
  - Secure JSON/ZIP export package containing complete metadata, green sheet notings history, movement audit trails, and attached documents.
  - Ingestion endpoint on the receiving instance to reconstruct the file with integrity validation.

---

## 3. Architecture & Data Model Additions

The table below summarizes the DocTypes and Schema changes introduced across Sprints 1 to 4:

| Sprint | DocType / Component | Type | Key Fields / Methods |
| :--- | :--- | :--- | :--- |
| **Sprint 1** | `Correspond File` (Modified) | Core DocType | `status` (`Active`, `Parked`, `Closed`, `Archived`), `park_reason`, `park_until`, `pull_back_file()` |
| **Sprint 1** | `File Movement Log` (Modified) | Child Table | `is_opened` (Check), `opened_on` (Datetime), `action` (`Pulled Back`, `Parked`, `Unparked`) |
| **Sprint 1** | `Correspond Noting Reference` | Child Table | `flag_label` (Data, e.g. "Flag A"), `reference_type` (`Inward Dak`, `Outward Dak`, `File`), `page_number` |
| **Sprint 2** | `Correspond DFA Template` | Master DocType | `template_name`, `dfa_type` (Select: OM, DO, Sanction, Circular), `content_format` |
| **Sprint 2** | `Outward Dak` (Modified) | Core DocType | `dfa_type`, `dispatch_register_no`, `dispatch_mode`, `tracking_number`, `approval_status` |
| **Sprint 3** | `Correspond Delegation Rule` | Master DocType | `desk`, `delegate_desk`, `from_date`, `to_date`, `is_active`, `delegation_reason` |
| **Sprint 3** | `Inward Dak` (Modified) | Core DocType | `barcode_image`, `ocr_extracted_text`, `is_vip_reference`, `vip_type`, `sla_due_date` |
| **Sprint 4** | `Correspond Record Classification`| Master DocType | `classification_code` (Cat A/B/C), `retention_years`, `custody_protocol` |
| **Sprint 4** | `Correspond Weeding Certificate` | Transaction | `review_date`, `approved_by`, `files_weeded` (Table), `certificate_hash` |

---

## 4. Resource Allocation & Delivery Schedule

```
+---------------------------------------------------------------------------------------+
| SPRINT / WEEKS   | PRIMARY DELIVERABLES                  | KEY TECHNICAL FOCUS        |
+------------------+---------------------------------------+----------------------------+
| Sprint 1 (W 1-4) | - Pull Back & Park File               | Client/Server validation,  |
|                  | - Alphanumeric Flagging ('Flag A-Z')  | Desk UI Split-View script, |
|                  | - View/Download Watermarking          | PyPDF2 watermark pipeline  |
+------------------+---------------------------------------+----------------------------+
| Sprint 2 (W 5-8) | - Government DFA Templates            | Jinja Print Formats,       |
|                  | - DFA Approval Workflow               | State machine transitions, |
|                  | - Central Dispatch Register           | Autonaming series per Dept |
+------------------+---------------------------------------+----------------------------+
| Sprint 3 (W 9-12)| - Link Officer Delegation             | Session permission hooks,  |
|                  | - Diarization Barcode/QR Labels       | Barcode generation,        |
|                  | - Duplicate Detection & OCR Pipeline  | Celery/Background worker,  |
|                  | - VIP & Parliament SLA Tracking       | Scheduled escalation jobs  |
+------------------+---------------------------------------+----------------------------+
| Sprint 4 (W13-16)| - CSMOP Retention Schedules           | Electronic Record Room,    |
|                  | - Weeding Out Register                | Disposal verification,     |
|                  | - Executive TAT & Pendency Dashboards | Frappe Dashboard charts,   |
|                  | - eExchange JSON Inter-Instance Sync  | REST API data serializer   |
+------------------+---------------------------------------+----------------------------+
```

---

## 5. Next Steps

1. **Review & Baseline:** Confirm Sprint 1 targets (Pull Back, Park File, Flag Slips, Watermarking).
2. **Branching & Setup:** Create release branch `feature/sprint-1-agility` in the repository.
3. **Sprint 1 Execution:** Begin development of the Pull Back API and Green Sheet Flagging references.
