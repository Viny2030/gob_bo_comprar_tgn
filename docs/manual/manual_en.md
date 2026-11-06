# Monitor XAI — User Manual

Monitor of Public Contracts and Tenders of Argentina's national government.

Manual version: November 2026 · comprar.ecosistematransparencia.com.ar

## 1. What is Monitor XAI?

Monitor XAI (eXplainable Artificial Intelligence) is a web platform for the automated auditing of Argentina's national government procurement. Every business day it reads the notices in the Official Gazette (BORA), cross-references them with Comprar.gob.ar and the National Treasury (TGN), applies a matrix of risk indicators and places each notice within its legal framework. Every result can be explained: the system shows which indicator was triggered and why.

> **Important:** the system does NOT detect criminal offenses, is not a whistleblowing channel, and does not assess the conduct of individuals. It analyzes discretionary government decisions and flags patterns that deserve a closer look.

## 2. What it measures

### 2.1 Tender Risk Matrix (shown under Tenders and on the Dashboard)

It is applied to every contract award published in the BORA. It adds up the weights of the indicators that are triggered:

| Indicator | Weight | When it is triggered |
|---|---|---|
| Direct Contracting | 3.0 | The procedure is a direct contract, an exception, or an abbreviated tender. |
| Single Supplier | 2.5 | The same CUIT (tax ID) appears in two or more awards on the same day. |
| Threshold Amount | 2.5 | The amount is up to 10% below a threshold that requires a more competitive procedure (1,000 or 5,000 modules, Decree 1030/2016, art. 27). It suggests contract splitting. |
| Multi-Agency Supplier | 1.5 | The same CUIT is paid by several agencies in TGN. It cannot be triggered today: the TGN API does not report the beneficiary's CUIT. |

The **risk index (0 to 10)** is the sum of the weights divided by 9.5 and multiplied by 10. Since the last indicator cannot be triggered, the highest possible value today is 8.42.

| Level | Index | Note |
|---|---|---|
| High | 7 or more | In practice it requires Direct Contracting, Single Supplier and Threshold Amount to be triggered together. |
| Medium | 4 to 6.99 | A Direct Contract is always at least Medium, even though its index is 3.16. |
| Low | below 4 | Low does not mean "no risk": it means no indicator in the matrix was triggered. |

### 2.2 Legal framework of each notice

Besides risk, each notice is placed in the legal regime that governs it (details in Section 9):

- **Regime:** goods and services (Delegated Decree 1023/2001), public works (Law 13,064), concessions (Laws 17,520 and 23,696) or sale of state property.
- **Who contracts:** state-owned companies, the Judiciary, the Public Prosecution Service, Congress and national universities have their own procurement regimes; those notices are flagged and not assessed against Decree 1030/2016.
- **Procedure and amount:** public or private tender or competition, direct contract or auction; the amount is expressed in modules.

## 3. Data sources and their limits

- **Official Gazette (BORA), Third Section:** index of the day's notices and the text of each award (sometimes a PDF). The supplier, CUIT and amount are extracted from that text; extraction can fail. Since 22 Oct 2026 the BORA does not answer servers located outside Argentina: that is why reports are generated on a computer in Argentina (Section 4).
- **Comprar.gob.ar:** procedures with upcoming openings, as listed at the time of the query. There is no history: a day generated late has no Comprar data.
- **TGN (Presupuesto Abierto):** credit paid during the year by each agency, in millions of pesos. It does not report the beneficiary's CUIT, so it **does not confirm that a specific supplier was paid**. It has no daily history either.

Cross-references with Comprar and TGN are made by matching words in the agency name (at least two meaningful words). Each award receives a label:

| Label | Meaning |
|---|---|
| 📋 SOLO BORA | The agency was not found in Comprar or TGN. |
| 🔷 BORA + COMPRAR | The agency has open procedures in Comprar. |
| 🔶 BORA + TGN (por organismo) | The agency has executed payments during the year. It does not mean this supplier was paid. |
| 🔶 BORA + TGN (cobró) | Match by CUIT in TGN. It does not happen today, because of the API limit. |
| 🚨 FLUJO COMPLETO | There is a CUIT and the agency matches in both Comprar and TGN. It is a match by agency, not the tracing of a payment. |

## 4. Processes

### 4.1 Daily report generation

It runs on its own on a computer with an Argentine connection, registered in GitHub as the project's runner. It is scheduled Monday to Friday at 08:30 and 12:30 (Argentina time); the 12:30 run is a retry and does nothing if the report is already there. If the computer is off, the run waits for up to 24 hours and starts as soon as it is turned on.

On each run it:

1. Fetches the latest published reports.
2. Looks for business days with no report (skipping weekends and holidays) and checks that the BORA responds.
3. Queries Comprar.gob.ar and TGN, for today only, because they have no history.
4. For each missing day, reads the index of the BORA Third Section and splits it into tenders and awards.
5. Extracts the supplier, CUIT and amount from each award.
6. Cross-references BORA → Comprar → TGN by agency (Section 3) and applies the risk matrix (Section 2.1).
7. Saves two Excel files: `reporte_YYYY-MM-DD.xlsx` (all sheets) and `flujo_licitaciones_YYYY-MM-DD.xlsx`. If the day was generated late, it adds an "ℹ️ Origen" sheet saying so.
8. Publishes the Excel files to the project repository.

### 4.2 Publishing on the site

When a report is published, the site picks it up in two ways: the server updates itself from the repository, and the **Actualizar datos en vivo** button (Tenders) or **Traer reportes publicados** (Data Loading) downloads it in seconds without waiting. The button compares each file with the published one and only downloads what is new or changed; if a day already existed, it keeps a backup copy before replacing it.

### 4.3 Missing-report check

At 14:00 on each business day an automatic check looks for today's report. If it is missing, it sends a warning email. If the computer is turned on later, the report is still generated and the warning no longer applies.

### 4.4 Manual generation

To fill in a day by hand, on the computer in Argentina, from the project folder:

```
python tools/actualizar_desde_pc.py --dry-run      # lists the missing days
python tools/actualizar_desde_pc.py --publicar     # generates and publishes them
```

For the report to include TGN, the computer needs the `TGN_TOKEN` variable.

### 4.5 Manual upload of an Excel file

From **Data Loading**, with the admin key, you can upload a daily Excel file produced outside the automatic pipeline (Section 8). The system checks that it has the sheets of a monitor report before saving it.

## 5. Navigation

- **Dashboard:** summary of the latest report.
- **Licitaciones (Tenders):** the day's BORA → Comprar → TGN cross-flow, with per-award detail and legal framework.
- **Carga de Datos (Data Loading):** loads the published reports, picks the day and allows manual uploads.
- **Documentación (Documentation):** system description and downloads.
- **Manual:** this document.
- **Estado (Status):** system health and missing days (Section 13).
- **API:** interactive documentation (Swagger) at `/docs`.

## 6. Dashboard

Shows the latest available report.

- **Cards:** Processes Analyzed, Average Intensity (average risk index, 0 to 10), High Risk Alerts and Total Reports saved.
- **Distribution by type:** number of awards by BORA procedure type (public tender, direct contract, etc.).
- **Risk level:** how many awards ended up High, Medium and Low.
- **Algorithmic Analysis Detail:** up to 50 rows with agency, procedure type, index and level.
- **Latest report:** the file for the most recent day. Download it from the Status page or with `GET /api/reporte/YYYY-MM-DD/excel`.

## 7. Tenders — BORA → Comprar → TGN cross-flow

This is the main screen for daily monitoring.

- **Status bar:** date of the data and sources. The 🚀 **Actualizar datos en vivo** button loads the published reports the server does not have yet (Section 4.2) and shows the summary of the latest day.
- **Flow stages:** BORA Tenders, Comprar, Awarded and TGN. Clicking a stage filters the table; "Reset" removes the filter.
- **Metrics:** Total BORA Notices, With Extracted CUIT, Without CUIT (pending manual review) and Full Flow.
- **Legal framework of the notices:** how many notices there are per regime and per procedure, how many come from entities with their own regime, and the list of those with remarks (Section 9).
- **Tabs:** BORA Tenders, Comprar.gob.ar and Awards.
- **Next to each CUIT:** ✓ or ⚠️ depending on the check digit (Section 10), and 🌍 INTERNATIONAL ALERT if MEACI finds matches (Section 11).
- **🤖 Explain with AI:** writes why a row got its risk level (Section 12).
- To see an earlier day: `/licitaciones?fecha=YYYY-MM-DD`, or pick it in Data Loading.

## 8. Data Loading

1. Click 🔄 **Traer reportes publicados**: the server downloads the reports it does not have yet (Section 4.2). It takes a few seconds.
2. Pick a day from the list; only days with a report are shown, most recent first. The link opens that day under Tenders or downloads the Excel file.
3. **Manual upload (admin):** enter the day, the file type (`reporte` or `flujo_licitaciones`), the file and the admin key. If the day already had a report, the previous one is backed up before it is replaced.

## 9. Legal framework

The `/marco-normativo` page lists the rules the system uses, with their verification status (in force, partially repealed or unverified) and the corrections made to the initial list. For each notice it assesses:

- **Material regime**, from the notice's category and text, with the matching rules and platform (COMPR.AR for goods and services; CONTRAT.AR for public works and concessions).
- **Subjective scope:** whether the agency contracts under its own regime.
- **Selection procedure.** Direct contracts carry a remark to check the legal ground invoked (Delegated Decree 1023/2001, art. 25, para. d).
- **Amount in modules:** module of ARS 40,000 (Decree 666/2024). Thresholds per procedure are only checked if configured, because the current consolidated text could not be confirmed.
- **Cross-cutting controls:** proactive transparency (Law 27,275), sworn statement of interests (Decree 202/2017), tax compliance (AFIP General Resolution 4164/2017) and an integrity program where applicable (Law 27,401, art. 24).

> It is an indicator of formal compliance built from the text of the notice, not a legal opinion.

## 10. CUIT format validation

The CUIT is extracted from the notice text, so it may be misread. The system checks the check digit with AFIP's (now ARCA's) modulo 11 algorithm.

- ✓ **Confirms** that the number has 11 digits and a correct check digit.
- ⚠️ **Does not query** any registry: it does not confirm actual registration, the company name or the taxpayer's status.

```
GET /api/cuit/validar?cuit=30-12345678-1
GET /api/cuit/validar-lote?cuits=30-12345678-1,20-12345678-6   (up to 200)
```

## 11. International sanctions check (MEACI)

MEACI is an independent service that looks up the supplier's CUIT in international sanctions databases. If there is a match, the row shows 🌍 INTERNATIONAL ALERT. If MEACI does not respond, the page still loads, without that signal.

```
GET /api/cruce-cuit?cuit=30-68728814-5
GET /api/cruce-cuits-bulk?cuits=cuit1,cuit2,cuit3   (up to 50)
```

## 12. Second opinion with AI

When configured, the AI (Claude, by Anthropic) offers two functions:

- **Explain risk:** writes in plain language why an award got its level, using only the indicators the matrix already calculated.
- **Classify notice:** suggests a topic category for a notice's text (public works, concession, utility rates, etc.), with its reasoning.

Each visitor can make 10 queries per day, and there is a daily cap for the whole site. Failed queries are not counted. The AI is advisory: **it does not change the risk index or level**.

## 13. System status

The `/estado` page shows the Argentina time, the latest report (with a download link), how many rows each source returned, the business days in the last 30 without a report, whether the database and the AI are available, and whether report protection is active. `GET /api/diagnostico` also reports whether the server can reach the BORA and how the last AI query ended.

## 14. How to interpret the results

- The index is an **indicator score**, not a probability or proof.
- A High or Medium level means the original notice is worth reviewing; it does not imply wrongdoing.
- "Without CUIT" usually means a PDF notice or one worded unusually: check the notice in the BORA.
- The TGN labels and "Full Flow" are matches by agency, not confirmed payments to a supplier.
- A notice from an entity with its own regime is not assessed against Decree 1030/2016: compare it with that entity's rules.
- Reports before October 2026 were calculated with an earlier version of the matrix, which added 1.36 points to every row. To compare periods, use the recalculated data (see MEJORAS.md).

## 15. REST API

Interactive documentation at `/docs`.

| Endpoint | Description |
|---|---|
| `GET /api/status` | General status |
| `GET /api/estado-sistema` · `GET /api/diagnostico` | Detailed status (Section 13) |
| `GET /api/reportes` | List of saved reports |
| `GET /api/dias-disponibles` | Days with a report |
| `GET /api/licitaciones/datos?fecha=YYYY-MM-DD` | Data for a day (latest by default) |
| `GET /api/reporte/YYYY-MM-DD/excel` | Downloads the day's Excel file (`?tipo=flujo` for the flow file) |
| `POST /api/datos/actualizar` · `GET /api/datos/estado` | Loads the published reports (Section 4.2) |
| `POST /api/admin/subir-reporte?fecha=YYYY-MM-DD&tipo=reporte` | Manual upload of an Excel file (requires key) |
| `GET /api/licitaciones/normativa?fecha=YYYY-MM-DD` | Legal framework of each notice of the day |
| `GET /api/marco-normativo` | Catalogue of rules |
| `GET /api/cuit/validar` · `GET /api/cuit/validar-lote` | CUIT format validation |
| `GET /api/cruce-cuit` · `GET /api/cruce-cuits-bulk` | MEACI check |
| `GET /api/ia/status` · `GET /api/ia/usos` | AI availability and remaining queries |
| `POST /api/ia/explicar-riesgo` · `POST /api/ia/clasificar` | Second opinion with AI |
| `GET /health` | Healthcheck |

## 16. Recommended workflow

1. Open **Tenders** and click 🚀 **Actualizar datos en vivo** to load the day's report.
2. Review the High and Medium rows first, and those "Without CUIT".
3. Check the ✓/⚠️ icon before accepting a CUIT.
4. Pay special attention to any 🌍 INTERNATIONAL ALERT.
5. Look at the remarks in the legal framework panel, especially direct contracts.
6. Open the original BORA notice (linked in each row) before drawing conclusions.
7. If a day is missing, check it under **Status**: it is filled in automatically when the computer in Argentina is turned on, or by hand (Section 4.4).

## 17. 🕸️ How this site connects to the rest of the ecosystem

This site is part of the **Transparency Ecosystem**: eleven monitors that query each other. Below, which sites it exchanges data with ("uses →" = takes data from that site; "← used by" = that site takes data from this one) and which official sources feed it. The graph is interactive: click any site to see its profile.

[Open the full graph ↗](https://mapa.ecosistematransparencia.com.ar/grafo?nodo=comprar&lang=en)

**Connections**

- **uses → Contratos**: Same BORA awards; the daily cross-validation checks they match day by day and in amount.
- **uses → MEACI**: Checks supplier CUITs against MEACI's sanctioned list and that MEACI is reachable.
- **← used by Mapa**: Link and live status. The daily cross-validation (Mon–Fri 13:00) compares Comprar and Contratos day by day, to the peso.

**Official sources**

- Official Gazette (BORA), 3rd section
- COMPR.AR
- National Treasury (TGN)

Every connection in detail, and how figures are cross-checked between sites: [mapa.ecosistematransparencia.com.ar/en/manual#conexiones](https://mapa.ecosistematransparencia.com.ar/en/manual#conexiones)

## 18. Downloads

- Manual in Spanish and English (.docx), from this page.
- Dashboard guide (.docx), from Documentation.
- Each day's Excel file, from Status, from Data Loading or with `GET /api/reporte/YYYY-MM-DD/excel`.

## 19. Disclaimer

> This tool is experimental and academic in nature. The data comes from official public sources of the Argentine government. Results are algorithmic risk indicators: they do not imply a value judgment, an accusation or a finding of liability against any company, agency or person. The goal is to promote transparency and informed debate about public spending.

Contact: vhmonte@retina.ar / viny01958@gmail.com · MIT License
