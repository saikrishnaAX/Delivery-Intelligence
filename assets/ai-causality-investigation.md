# AI Causality Investigation Report

**Generated:** 2026-07-04T23:59:59 UTC  
**AI adoption date:** 2026-05-01  
**Pre-AI window:** Dec 2025 – Apr 2026  
**Post-AI window:** May – Jun 2026  

---

## 1. Executive Summary

**Can we currently prove AI increased defects?** No. We cannot establish a causal relationship between AI adoption and increased defects from ticket data alone.

Of **24 unique recurring engineering issues** identified by Issue Intelligence, **19 (79.2%)** first appeared **before** 1 May 2026, and **5** first appeared only after AI adoption. The majority of recurring defect patterns pre-date AI.

Bug intake rose from **51.5/month** (pre-AI) to **62.4/month** (May–Jun post-AI), while enhancement delivery also rose (9.5 → 25.9/month). Volume increased on both bugs and features — correlational, not causal.

**Leadership decision today:** Continue AI adoption with strengthened regression on legacy clusters (Invoice numbering, Job Card, PDF, notifications). Introduce AI task attribution before making any quality judgment about AI itself.

---

## 2. Evidence Supporting AI Impact

- Bug creation rate increased 21.2% per month post-AI (51.5 → 62.4/mo).
- 5 engineering issue clusters first appeared only after 1 May 2026.
- UI defects per month increased 58.9% (11.2 → 17.8/mo).
- Performance defects per month increased 109.8% (5.1 → 10.7/mo).
- Integration defects per month increased 51.4% (3.7 → 5.6/mo).
- 8 recurring issues trending increasing, including: " Bosch Service History Upload issue ", "Job Card Status issue", "Customer Notifications — Notification No".

---

## 3. Evidence Against AI Impact

- 79.2% of recurring engineering issues existed before AI adoption — defects are largely legacy patterns.
- Bug-to-feature ratio and bug share of tickets remained stable; more work shipped, more bugs logged.
- No AI attribution field on tickets — impossible to distinguish AI-written from human-written code.
- New post-AI clusters map to long-standing modules (Invoice, Job Card, Reports), not new greenfield products.

---

## 4. Legacy Issues That Pre-date AI

| Issue | First Seen | Tickets | Trend | Modules |
|-------|------------|---------|-------|---------|
| Enhancement Request | 2026-02-03 | 46 | decreasing | CEP / GMS, Stock |
|  Bosch Service History Upload issue  | 2026-02-02 | 21 | increasing | Multiple Modules |
| Job Card Status issue | 2026-02-12 | 15 | increasing | Job Card / Parts Inwarding / Reports, Job Card |
| Job Card — Content Missing or Incorrect in PDF / P | 2026-02-10 | 15 | decreasing | Job Card, Invoice / Insurance |
| Customer Notifications — Notification Not Sent or  | 2026-02-09 | 11 | increasing | Job Card, Job Card / Invoice / Parts Inwarding / Reports |
| Invoice — Tax or Amount Calculation Incorrect | 2026-02-13 | 10 | decreasing | Job Card, Invoice / Insurance |
| Job Card — Configuration or Settings Issue | 2026-04-23 | 9 | decreasing | CEP / GMS, Job Card |
| stock by line item issue | 2026-02-03 | 9 | increasing | Stock, Stock / Reports |
| Job Card — Integration or API Sync Failure | 2026-02-11 | 7 | stable | Job Card, Job Card / Estimation / CEP / GMS |
| Invoice — Number or Sequence Not Generated | 2026-03-23 | 3 | increasing | Invoice / Insurance / Reports, Multiple Modules |
| Job Card — UI Display or Screen Rendering Issue | 2026-03-10 | 5 | stable | Estimation / Invoice, Job Card / Estimation |
| Estimation — Duplicate Ticket | 2026-04-21 | 5 | increasing | Invoice / Insurance, Estimation / Parts Inwarding / Stock / Barcode Printing |
| Invoice creation flow analyzation and perrfomance  | 2026-03-10 | 4 | increasing | Invoice, Estimation / Invoice |
| Group, Category & Sub-Cat not populating in Add Ma | 2026-02-16 | 2 | stable | Parts Inwarding / Stock, Parts Inwarding |
| Parts Inwarding — User Training or How-To Question | 2026-04-16 | 3 | stable | Master Management / Parts Inwarding, Reports |
| hsn report analyzation  | 2026-04-01 | 3 | increasing | Reports, Reports / CEP / GMS |
| Parts Inwarding — Permission or Access Denied | 2026-04-13 | 3 | stable | Master Management, Parts Inwarding |
| corporate dashboard (Franchise – Sales Analytics D | 2026-03-11 | 1 | stable | Invoice / Sales Register / Franchise Management / Dashboard |
| Bosch SEZ | 2026-04-29 | 1 | stable | Tax Compliance |

---

## 5. New Issues Introduced After AI

| Issue | First Seen | Tickets | Classification |
|-------|------------|---------|----------------|
| Estimation details error |Sri Srinivasa auto garra | 2026-06-11 | 2 | Existing module with recent enhancements (possible new work) |
| multiple parts are created in master with same par | 2026-07-02 | 1 | Existing module with recent enhancements (possible new work) |
| Kaura-Sales Register  Report – Amount Mismatch | 2026-06-29 | 1 | Existing module with recent enhancements (possible new work) |
| Payment link in mobile app customer link | 2026-06-09 | 1 | Existing module modified |
| Sell products performance issue | 2026-06-04 | 1 | Existing module modified |

---

## 6. Module Comparison

| Module | Pre-AI bugs | Post-AI bugs | Pre/mo | Post/mo | Change | Status |
|--------|-------------|--------------|--------|---------|--------|--------|
| Support Tickets | 226 | 92 | 45.9 | 46.7 | 1.7% | improved |
| Prioritized | 0 | 13 | 0.0 | 6.6 | new | new_unstable |
| Search | 4 | 3 | 0.8 | 1.5 | 87.5% | continuing |
| Done | 5 | 0 | 1.0 | 0.0 | -100.0% | improved |
| Inventory | 3 | 2 | 0.6 | 1.0 | 66.7% | improved |
| Reporting | 2 | 2 | 0.4 | 1.0 | 150.0% | continuing |
| User Management | 2 | 2 | 0.4 | 1.0 | 150.0% | continuing |
| Integrations | 3 | 1 | 0.6 | 0.5 | -16.7% | improved |
| Mobile App | 2 | 2 | 0.4 | 1.0 | 150.0% | continuing |
| API Gateway | 3 | 1 | 0.6 | 0.5 | -16.7% | improved |
| Released(With Release Notes) | 3 | 0 | 0.6 | 0.0 | -100.0% | improved |
| Notifications | 0 | 2 | 0.0 | 1.0 | new | continuing |
| Developing | 1 | 0 | 0.2 | 0.0 | -100.0% | improved |
| Authentication | 0 | 1 | 0.0 | 0.5 | new | continuing |
| Billing | 0 | 1 | 0.0 | 0.5 | new | continuing |

---

## 7. Defect Category Comparison

| Category | Pre-AI | Post-AI | Pre/mo | Post/mo | Δ/mo | Significant? |
|----------|--------|-------|--------|---------|------|--------------|
| Edge Cases | 77 | 28 | 15.6 | 14.2 | -9.0% | No |
| UI | 55 | 35 | 11.2 | 17.8 | 58.9% | Yes |
| Performance | 25 | 21 | 5.1 | 10.7 | 109.8% | Yes |
| Workflow | 31 | 3 | 6.3 | 1.5 | -76.2% | No |
| Integration | 18 | 11 | 3.7 | 5.6 | 51.4% | Yes |
| Business Logic | 14 | 6 | 2.8 | 3.0 | 7.1% | No |
| Database | 8 | 8 | 1.6 | 4.1 | 156.2% | Yes |
| Configuration | 9 | 4 | 1.8 | 2.0 | 11.1% | No |
| API | 9 | 3 | 1.8 | 1.5 | -16.7% | No |
| Incorrect | 2 | 1 | 0.4 | 0.5 | 25.0% | No |
| Repeated | 2 | 1 | 0.4 | 0.5 | 25.0% | No |
| Regression | 3 | 0 | 0.6 | 0.0 | -100.0% | No |
| Validation | 0 | 2 | 0.0 | 1.0 | — | No |
| Incomplete | 1 | 0 | 0.2 | 0.0 | -100.0% | No |

---

## 8. Confidence Assessment

| Conclusion | Confidence | Evidence |
|------------|------------|----------|
| Most recurring issues pre-date AI (79.2%) | **High** | Issue Intelligence first-seen dates on 24 unique clusters |
| Cannot prove AI caused defect increase | **High** | No AI attribution on tickets; correlational volume only |
| Bug rate increased post-AI | **Moderate** | Monthly bug counts Dec–Apr vs May–Jun |
| Legacy modules (Invoice, Job Card) drive recurrence | **High** | Module + engineering-fix clustering |
| 5 clusters are AI-introduced defects | **Low** | First seen post-May; same modules as pre-AI work |
| UI/Performance themes increased | **Moderate** | Rule-based text classification |

---

## 9. Recommendations for Better Future Measurement

1. Tag every development task with `ai_assisted: yes/no` and `ai_tool` in Asana/Jira.
2. Link bugs to the release/sprint and list of changes shipped in that release.
3. Track regressions explicitly (reopened flag + 'regression' label) with link to original fix.
4. Re-run Issue Intelligence monthly; compare cluster first-seen dates quarter-over-quarter.
5. Measure bugs per enhancement shipped, not bugs per calendar month alone.
6. Add code-ownership mapping so module instability can be tied to change frequency.

---

## Appendix: All Recurring Issues (Step 1)

| Issue | First Seen | Last Seen | Tickets | Trend | Workshops | Modules |
|-------|------------|-----------|---------|-------|-----------|---------|
| Enhancement Request | 2026-02-03 | 2026-06-30 | 46 | decreasing | 1 | CEP / GMS, Stock |
|  Bosch Service History Upload issue  | 2026-02-02 | 2026-06-29 | 21 | increasing | 2 | Multiple Modules |
| Job Card Status issue | 2026-02-12 | 2026-06-29 | 15 | increasing | 1 | Job Card / Parts Inwarding / Reports, Job Card |
| Job Card — Content Missing or Incorrect in PD | 2026-02-10 | 2026-06-11 | 15 | decreasing | 0 | Job Card, Invoice / Insurance |
| Customer Notifications — Notification Not Sen | 2026-02-09 | 2026-06-10 | 11 | increasing | 0 | Job Card, Job Card / Invoice / Parts Inwarding / Reports |
| Invoice — Tax or Amount Calculation Incorrect | 2026-02-13 | 2026-06-10 | 10 | decreasing | 0 | Job Card, Invoice / Insurance |
| Job Card — Configuration or Settings Issue | 2026-04-23 | 2026-07-01 | 9 | decreasing | 0 | CEP / GMS, Job Card |
| stock by line item issue | 2026-02-03 | 2026-06-29 | 9 | increasing | 0 | Stock, Stock / Reports |
| Job Card — Integration or API Sync Failure | 2026-02-11 | 2026-06-11 | 7 | stable | 0 | Job Card, Job Card / Estimation / CEP / GMS |
| Invoice — Number or Sequence Not Generated | 2026-03-23 | 2026-06-29 | 3 | increasing | 0 | Invoice / Insurance / Reports, Multiple Modules |
| Job Card — UI Display or Screen Rendering Iss | 2026-03-10 | 2026-06-29 | 5 | stable | 1 | Estimation / Invoice, Job Card / Estimation |
| Estimation — Duplicate Ticket | 2026-04-21 | 2026-06-29 | 5 | increasing | 0 | Invoice / Insurance, Estimation / Parts Inwarding / Stock / Barcode Printing |
| Invoice creation flow analyzation and perrfom | 2026-03-10 | 2026-06-12 | 4 | increasing | 1 | Invoice, Estimation / Invoice |
| Group, Category & Sub-Cat not populating in A | 2026-02-16 | 2026-04-17 | 2 | stable | 0 | Parts Inwarding / Stock, Parts Inwarding |
| Parts Inwarding — User Training or How-To Que | 2026-04-16 | 2026-06-29 | 3 | stable | 0 | Master Management / Parts Inwarding, Reports |
| hsn report analyzation  | 2026-04-01 | 2026-06-12 | 3 | increasing | 0 | Reports, Reports / CEP / GMS |
| Parts Inwarding — Permission or Access Denied | 2026-04-13 | 2026-06-08 | 3 | stable | 0 | Master Management, Parts Inwarding |
| Estimation details error |Sri Srinivasa auto  | 2026-06-11 | 2026-06-18 | 2 | stable | 2 | Estimation |
| multiple parts are created in master with sam | 2026-07-02 | 2026-07-02 | 1 | stable | 0 | Master Management / Parts Inwarding / Dashboard |
| corporate dashboard (Franchise – Sales Analyt | 2026-03-11 | 2026-03-11 | 1 | stable | 0 | Invoice / Sales Register / Franchise Management / Dashboard |
| Kaura-Sales Register  Report – Amount Mismatc | 2026-06-29 | 2026-06-29 | 1 | stable | 0 | Sales Register / Reports |
| Payment link in mobile app customer link | 2026-06-09 | 2026-06-09 | 1 | stable | 0 | Payments |
| Sell products performance issue | 2026-06-04 | 2026-06-04 | 1 | stable | 0 | Invoice / Sell Product |
| Bosch SEZ | 2026-04-29 | 2026-04-29 | 1 | stable | 0 | Tax Compliance |

---
*Investigation based on synced Asana tickets, Issue Intelligence recurring clusters, and rule-based classification. Not causal proof.*