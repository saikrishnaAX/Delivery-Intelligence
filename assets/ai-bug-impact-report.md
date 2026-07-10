# AI Adoption Impact Report (for CEO)

**Generated:** 2026-07-04T09:27:27 UTC  
**AI adoption date:** 1 May 2026  
**Data source:** All synced Asana tickets (created_at)

## Part 1 — Bug intake comparison

| Period | Months | Total bugs | Avg bugs / month |
|--------|--------|------------|------------------|
| Pre-AI (Dec 2025 – Apr 2026) | 5 | 254 | **50.8** |
| Post-AI (May 2026 – present) | 3 | 131 | **61.5** (full months) |

**Change:** +21.1% bugs per month (post vs pre)  
**Verdict:** Average bugs created per month is 21.1% higher after AI adoption (50.8/mo pre-AI vs 61.5/mo post-AI full months). This is correlational — more delivery volume also increased post-AI. June 2026 had 74 bugs — the highest single month in the window.

*Jul 2026 is partial (8 bugs in 4 days) — excluded from primary avg.*

### Monthly breakdown — bugs created

| Month | Period | Tickets | **Bugs** | Bug % of tickets |
|-------|--------|---------|----------|------------------|
| Dec 2025 | Pre-AI | 144 | **20** | 13.9% |
| Jan 2026 | Pre-AI | 154 | **46** | 29.9% |
| Feb 2026 | Pre-AI | 174 | **54** | 31.0% |
| Mar 2026 | Pre-AI | 169 | **65** | 38.5% |
| Apr 2026 | Pre-AI | 216 | **69** | 31.9% |
| May 2026 | Post-AI | 201 | **49** | 24.4% |
| Jun 2026 | Post-AI | 229 | **74** | 32.3% |
| Jul 2026 | Post-AI | 21 | **8** | 38.1% |

---

## Part 2 — Nature of issues (May–Jun 2026, post-AI)

**Bugs created:** 123 · **Still open:** 48 · **High/critical:** 91

### Executive summary

- Largest cluster: "Invoice Number Not Generated" (18 bugs) — Number / sequence / auto-ID generation.
- Dominant themes: UI (35), Other (23), Performance (21).
- Most affected areas: Reports (20), Multiple Modules (17), Job Card (11).
- 91 of 123 bugs were high or critical priority.

### Root cause themes

| Theme | Bugs |
|-------|------|
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

### Engineering-fix clusters

| Issue | Fix area | Bugs |
|-------|----------|------|
| Invoice Number Not Generated | Number / sequence / auto-ID generation | 18 |
| Job Card Status issue | Job Card — general product issue | 14 |
| Invoice — Content Missing or Incorrect in PDF / Print | PDF / print rendering | 12 |
| Customer Notifications — Notification Not Sent or Delivered | Email / WhatsApp / SMS delivery | 11 |
| Offline mode data not syncing #57 | Reports — general product issue | 11 |
| Duplicate Ticket | Duplicate report | 9 |
| Customer Performance Issue – Investigation Required | General — general product issue | 6 |
| Issue while bulk upload in upload stock module  | Stock — general product issue | 6 |
| Reports — Integration or API Sync Failure | External API / sync integration | 5 |
| Tax or Amount Calculation Incorrect | Tax / GST / calculation logic | 4 |
| Estimation details error |Sri Srinivasa auto garrage from kurnool | Estimation — general product issue | 4 |
| Job Card — UI Display or Screen Rendering Issue | UI display / screen rendering | 4 |

### Product modules affected

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

### Recommended engineering focus

1. Invoice Number Not Generated
2. Job Card Status issue
3. Invoice — Content Missing or Incorrect in PDF / Print
4. Customer Notifications — Notification Not Sent or Delivered
5. Offline mode data not syncing #57

## Methodology

Bugs counted from all synced tickets by created_at month. Bug = Asana Type or AI category classified as bug. Pre-AI = Dec 2025 through Apr 2026 (5 calendar months). Post-AI = May 2026 through report date.

---
*Internal Autorox Delivery Intelligence — not causal proof of AI impact.*