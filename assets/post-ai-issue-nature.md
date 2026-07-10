# Nature of Issues — Post-AI (May–Jun 2026)

**Period:** May – Jun 2026 (post-AI, from 1 May 2026)  
**Bugs created:** 123 (of 430 total tickets)  
**Still open:** 48

## Executive summary

- Largest engineering-fix cluster: "Invoice Number Not Generated" (18 bugs) — Number / sequence / auto-ID generation.
- Dominant symptom themes from ticket text: UI (35), Other (23), Performance (21).
- Most affected product areas: Reports (20), Multiple Modules (17), Job Card (11).
- 91 of 123 bugs were high or critical priority.

## Root cause themes (from ticket title + description)

| Theme | Bug count |
|-------|-----------|
| UI | 35 |
| Other | 23 |
| Performance | 21 |
| Integration | 11 |
| Database | 8 |
| Invoice | 7 |
| Business Logic | 6 |
| Configuration | 4 |
| Workflow | 3 |
| API | 3 |
| Validation | 2 |

## Engineering-fix clusters (same code change would fix)

| Recurring issue | Engineering fix area | Bugs | Example tickets |
|-----------------|----------------------|------|-----------------|
| Invoice Number Not Generated | Number / sequence / auto-ID generation | 18 | Invoice Number Missing; unable to update the job done status |
| Job Card Status issue | Job Card — general product issue | 14 | Work Order Not Opening – Urgent Issue; Unable to Close Job Card Due to Quanti... |
| Invoice — Content Missing or Incorrect in PDF / Print | PDF / print rendering | 12 | Additional Discount Displayed as Labour Discount in Reports and Invoice; Work... |
| Customer Notifications — Notification Not Sent or Delivered | Email / WhatsApp / SMS delivery | 11 | WHATSAPP  Pack Activated but Customer Not Receiving Reminder Messages; Email ... |
| Offline mode data not syncing #57 | Reports — general product issue | 11 | Offline mode data not syncing #57; GOBYK Corporate Account Report Loading & C... |
| Duplicate Ticket | Duplicate report | 9 |  Kaura Motors- Duplicate Vendor Entries in Payment – Transaction Module; Dupl... |
| Customer Performance Issue – Investigation Required | General — general product issue | 6 | Technician unable to Clock out issue (AZ Garage); Customer Performance Issue ... |
| Issue while bulk upload in upload stock module  | Stock — general product issue | 6 | Unable to issue the part; Stock Value Mismatch for Parts -PADAMNABHAM AUTOMOB... |
| Reports — Integration or API Sync Failure | External API / sync integration | 5 | Bulk user import validation errors #41; Rate limit config not persisting #118 |
| Tax or Amount Calculation Incorrect | Tax / GST / calculation logic | 4 | GST Number Issue – Last Digit Missing; Collision Page Not Working in Mobile A... |
| Estimation details error |Sri Srinivasa auto garrage from kurnool | Estimation — general product issue | 4 | Unable to Unmark Parts from Estimation List; Incorrect Customer Phone Number ... |
| Job Card — UI Display or Screen Rendering Issue | UI display / screen rendering | 4 | Parts missing in inward bill - V2 AUTOMOTIVE; Issue While Adding Parts in Mas... |
| Kaura - Sales Register  Report – Amount Mismatch | Sales Register — general product issue | 3 | Kaura - Sales Register  Report – Amount Mismatch; Data Consistency: Discrepan... |
| Reports — Permission or Access Denied | Permissions / role access | 3 | Admin User missing; Role assignment not reflecting immediately #173 |
| Job Card — Configuration or Settings Issue | Configuration / settings | 3 | Job Card Module Visibility Issue After Disabling from Super Admin; Enhancemen... |

## Product modules most affected

| Module | Bugs |
|--------|------|
| Reports | 20 |
| Multiple Modules | 17 |
| Job Card | 11 |
| Invoice | 10 |
| Job Card / Invoice | 7 |
| Estimation | 6 |
| Sales Register / Reports | 4 |
| Job Card / Reports | 3 |
| Stock | 3 |
| Job Card / Estimation | 3 |
| Stock / Reports | 3 |
| Customer Notifications | 2 |

## Priority mix

| Priority | Count |
|----------|-------|
| high | 89 |
| medium | 27 |
| low | 5 |
| critical | 2 |

## Top workshops reporting bugs

| Workshop | Bugs |
|----------|------|
| TG Workshop | 3 |
| LACAUTOSERVICE | 3 |
| EXL AUTO WORKS | 2 |
| TURBO MOTORS GARAGE -AX1776919726730 | 2 |
| Action Auto | 2 |
| Bharat Motors | 1 |
| KAURA MOTORS NIGERIA LTD-AX1771576605032 | 1 |
| SAAKAR AUTOMOTIVE | 1 |

---
*Evidence from synced Asana tickets · rule-based classification · internal use only*