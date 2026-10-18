# Monitor XAI — User Manual

Public Contracts and Tenders Monitor. Based on the Theory of Corrupt Phenomena by Vicente Humberto Monteverde, PhD.

Manual version: October 2026 · gobbocomprartgn-production.up.railway.app

## 1. What is Monitor XAI?

Monitor XAI (eXplainable Artificial Intelligence) is a web platform for the automated auditing of Argentina's national government procurement. Every business day it reads the notices in the Official Gazette (BORA), cross-references them with Comprar.gob.ar and the National Treasury (TGN), and applies a matrix of risk indicators. Every result can be explained: the system shows which indicator was triggered and why.

> **Important:** the system does NOT detect criminal offenses, is not a whistleblowing channel, and does not assess the conduct of individuals. It analyzes discretionary government decisions and flags patterns that deserve a closer look.

## 2. What it measures: two matrices

The system uses two different matrices. It is important not to confuse them.

### 2.1 Tender Risk Matrix (what you see in Tenders and on the Dashboard)

It is applied to every contract award published in the BORA. It adds up the weights of the indicators that are triggered:

| Indicator | Weight | When it is triggered |
|---|---|---|
| Direct Award | 3.0 | The procedure is a direct award, an exception-based award or an abbreviated price comparison. |
| Single Vendor | 2.5 | The same CUIT (tax ID) appears in two or more awards on the same day. |
| Threshold Amount | 2.5 | The amount is up to 10% below a threshold that would require a more competitive procedure (1,000 or 5,000 modules, Decree 1030/2016, art. 27). This suggests contract splitting. |
| Multi-Agency Vendor | 1.5 | The same CUIT is paid by several agencies in TGN. It cannot be triggered today: the TGN API does not report the payee's CUIT. |

The **risk index (0 to 10)** is the sum of the weights divided by 9.5 and multiplied by 10. Since the last indicator cannot be triggered, the highest possible value today is 8.42.

| Level | Index | Note |
|---|---|---|
| High | 7 or more | In practice, it requires Direct Award, Single Vendor and Threshold Amount to be triggered together. |
| Medium | 4 to 6.99 | A Direct Award is always at least Medium, even though its index is 3.16. |
| Low | below 4 | Low does not mean "no risk": it means no indicator in the matrix was triggered. |

### 2.2 Theoretical regressive-transfer scenarios

This is Dr. Monteverde's conceptual framework: grand corruption is not limited to illegal acts, but includes legal decisions that shift income from groups with less bargaining power to groups with more. The system classifies texts into seven scenarios using keywords:

| Scenario | Weight | Direction of the transfer |
|---|---|---|
| Retirement / Pensions | 10.0 | Retirees → State |
| Tax Shifting | 9.5 | Taxpayers → State |
| Privatization / Concession | 9.0 | State → Private sector |
| Public Works / Contracts | 8.5 | State → Contractors |
| Public Utility Tariffs | 7.5 | Users → Utility companies |
| Regulated Consumer Prices | 6.5 | Consumers → Producers |
| Wages and Collective Bargaining | 5.5 | Employees → Employers |

This classification is used by the `POST /api/analisis` endpoint and by the AI second opinion (Section 11). It plays no part in the tender risk index.

Reference: Monteverde, V. H. (2020). Great corruption – theory of corrupt phenomena. Journal of Financial Crime, Vol. 28 No. 2, pp. 580-595. https://doi.org/10.1108/JFC-04-2020-0062

## 3. Data sources and their limits

- **Official Gazette (BORA), Third Section:** the day's index of notices and the text of each award (sometimes a PDF). The vendor, CUIT and amount are extracted from that text; extraction can fail.
- **Comprar.gob.ar:** processes with an upcoming bid opening, as they stand at query time. There is no history, so past days are not queried.
- **TGN (Presupuesto Abierto, the open budget portal):** credit paid during the year by each agency, in millions of pesos. It does not report the payee's CUIT, so it **does not confirm that a specific vendor was paid**. It has no daily history either.

Matches with Comprar and TGN are made by comparing words in the agency name (at least two significant words). Each award gets a label:

| Label | Meaning |
|---|---|
| 📋 SOLO BORA (BORA only) | The agency was found neither in Comprar nor in TGN. |
| 🔷 BORA + COMPRAR | The agency has open processes in Comprar. |
| 🔶 BORA + TGN (por organismo) | The agency has payments executed this year. It does not mean this vendor was paid. |
| 🔶 BORA + TGN (cobró) | A CUIT match in TGN. It does not happen today, because of the API limitation. |
| 🚨 FLUJO COMPLETO (complete flow) | There is a CUIT and the agency matches in both Comprar and TGN. It is an agency-level match, not the tracing of a payment. |

## 4. Automatic updates

The full cycle runs on its own, Monday to Friday, at 08:00 and 12:00 (Argentina time). The 12:00 run is a retry: if the morning run already produced the report, it does nothing. No report is generated on weekends or on days without a BORA edition. Each report is saved as two Excel files per day and appears on the site with the next repository update.

No manual action is needed for daily monitoring.

## 5. Navigation

- **Dashboard:** summary of the latest report.
- **Licitaciones (Tenders):** the BORA → Comprar → TGN cross-referenced flow for the latest report, with detail per award.
- **Análisis en Vivo (Live Analysis):** manually runs the cycle for a given day.
- **Documentación (Documentation):** theoretical framework and downloads.
- **Manual:** this document.
- **Estado (Status):** system health and missing days (Section 12).
- **API:** interactive documentation (Swagger) at `/docs`.

## 6. Dashboard

Shows the latest available report.

- **Cards:** Processes Analyzed, Average Intensity (average risk index, 0 to 10), High-Risk Alerts and Total Reports stored.
- **Distribution by type:** number of awards per BORA procedure type (public tender, direct award, etc.).
- **Risk level:** how many awards ended up as High, Medium and Low.
- **Algorithmic Analysis Detail:** up to 50 rows with agency, procedure type, index and level.
- **Latest report:** the file for the most recent day. Download it from the Status page or with `GET /api/reporte/YYYY-MM-DD/excel`.

## 7. Live Analysis

Lets you run the cycle for a chosen day.

1. Pick a day on the calendar. All days since 23 Feb 2026 are shown; those that already have a report are marked.
2. Click 🚀. The analysis runs in the background and the screen polls its progress; it usually takes one to five minutes.
3. When it finishes, the totals are shown along with links to the Dashboard and Tenders.

> **Keep in mind:** only one analysis can run at a time, and at most one every 10 minutes. For a past day, only the BORA is queried, because Comprar and TGN only reflect today's state. Re-running a past day that already has a report would therefore replace it with a report containing less data: it requires the admin key, and the system saves a backup copy before replacing it. A past day that has no report yet can be filled in without a key.

## 8. Tenders — BORA → Comprar → TGN cross-referenced flow

This is the main screen for daily monitoring.

- **Status bar:** the date of the data and the sources. The "Actualizar datos en vivo" (refresh live data) button runs today's cycle (same rules as Section 7).
- **Flow stages:** BORA Tenders, Comprar, Awarded and TGN. Clicking a stage filters the table; "Reset" clears the filter.
- **Metrics:** Total BORA Publications, With CUIT Extracted, Without CUIT (pending manual review) and Complete Flow.
- **Tabs:** BORA Tenders, Comprar.gob.ar and Awards.
- **Next to each CUIT:** ✓ or ⚠️ depending on the check digit (Section 9), and 🌍 INTERNATIONAL ALERT if MEACI finds a match (Section 10).
- **🤖 Explain with AI:** writes out why a row received its risk level (Section 11).

## 9. CUIT format validation

The CUIT is extracted from the notice text, so it may be misread. The system checks the check digit using the modulus-11 algorithm of AFIP (now ARCA, the federal tax agency).

- ✓ It **does confirm** that the number has 11 digits and a correct check digit.
- ⚠️ It **does not query** any registry: it does not confirm actual registration, the legal name or the taxpayer's status.

```
GET /api/cuit/validar?cuit=30-12345678-1
GET /api/cuit/validar-lote?cuits=30-12345678-1,20-12345678-6   (up to 200)
```

## 10. International sanctions check (MEACI)

MEACI is a separate service that looks up the vendor's CUIT in international sanctions databases. If there is a match, the row shows 🌍 INTERNATIONAL ALERT. If MEACI does not respond, the screen still loads, without that signal.

```
GET /api/cruce-cuit?cuit=30-68728814-5
GET /api/cruce-cuits-bulk?cuits=cuit1,cuit2,cuit3   (up to 50)
```

## 11. AI second opinion

When configured, the AI (Anthropic's Claude) offers two functions:

- **Explain risk:** writes, in plain language, why an award received its level, using only the indicators the matrix already computed.
- **Classify notice:** suggests one of the seven theoretical scenarios for a text, with its reasoning.

Each visitor can make 3 requests per day, and there is a daily cap for the whole site. Failed requests are not counted. The AI is advisory only: **it does not change the risk index or level**.

## 12. System status

The `/estado` page shows the time in Argentina, the latest report (with a download link), how many rows each source returned, the business days in the last 30 that have no report, whether the database and the AI are available, and whether report protection is active.

## 13. How to interpret the results

- The index is an **indicator score**, not a probability or proof.
- A High or Medium level means the original notice is worth reviewing; it does not imply wrongdoing.
- "Without CUIT" usually means a PDF notice or one with unusual wording: check the notice in the BORA.
- The TGN labels and "Complete Flow" are agency-level matches, not confirmed payments to a vendor.
- Reports from before October 2026 were computed with an earlier version of the matrix that added 1.36 points to every row. To compare periods, use the recalculated data (see MEJORAS.md).

## 14. REST API

Interactive documentation at `/docs`.

| Endpoint | Description |
|---|---|
| `GET /api/status` | General status |
| `GET /api/estado-sistema` | Detailed status (Section 12) |
| `GET /api/reportes` | List of stored reports |
| `GET /api/dias-disponibles` | Days with a report |
| `GET /api/licitaciones/datos?fecha=YYYY-MM-DD` | Data for a day (latest by default) |
| `GET /api/reporte/YYYY-MM-DD/excel` | Downloads the day's Excel file (`?tipo=flujo` for the flow file) |
| `POST /api/licitaciones/ejecutar?fecha=YYYY-MM-DD` | Starts the cycle for a day |
| `GET /api/licitaciones/estado` | Progress of the running cycle |
| `POST /api/analisis` | Classification into theoretical scenarios (requires the key) |
| `GET /api/marco-teorico` | The seven scenarios |
| `GET /api/cuit/validar` · `GET /api/cuit/validar-lote` | CUIT format validation |
| `GET /api/cruce-cuit` · `GET /api/cruce-cuits-bulk` | MEACI check |
| `GET /api/ia/status` · `GET /api/ia/usos` | AI availability and remaining requests |
| `POST /api/ia/explicar-riesgo` · `POST /api/ia/clasificar` | AI second opinion |
| `GET /health` | Health check |

## 15. Recommended workflow

1. Open **Tenders**: the day's report is generated automatically at 08:00.
2. Review High and Medium rows first, along with "Without CUIT" rows.
3. Check the ✓/⚠️ icon before relying on a CUIT.
4. Pay special attention to any 🌍 INTERNATIONAL ALERT.
5. Open the original BORA notice (linked in each row) before drawing conclusions.
6. If a day is missing, check it under **Status** and fill it in from **Live Analysis**.

## 16. Downloads

- This manual in Spanish and English (.docx), from this page.
- Dr. Monteverde's article (.docx) and the dashboard guide (.docx), from Documentation.
- Each day's Excel file, from Status or with `GET /api/reporte/YYYY-MM-DD/excel`.

## 17. Disclaimer

> This tool is experimental and academic in nature. The data comes from official public sources of the Argentine government. Results are algorithmic risk indicators: they do not imply a value judgment, an accusation or a finding of liability against any company, agency or person. The goal is to promote transparency and informed debate about public spending.

Contact: vhmonte@retina.ar / viny01958@gmail.com · MIT License
