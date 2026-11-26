# 🌊 IN-GRES — India-Groundwater Resource Estimation System (AI Assistant, Diagnostics & Decision Support)

An evidence-grounded conversational AI, groundwater diagnostic, and scenario decision-support layer built on top of the **IN-GRES (India-Groundwater Resource Estimation System)** / **Central Ground Water Board (CGWB)** `2024–2025` national assessment dataset (**726 district/unit records across 37 Indian states & UTs, 723 unique district names**).

- **Upstream / Collaborative Repository (`origin`):** [`Tushar2332/INGRES_UPD`](https://github.com/Tushar2332/INGRES_UPD)
- **Personal Repository (`personal`):** [`syed102003/INGRES-CHATBOT`](https://github.com/syed102003/INGRES-CHATBOT)

---

## 📋 Table of Contents

- [Overview & Problem Statement](#-overview--problem-statement)
- [Project Context & Attribution](#-project-context--attribution)
- [Key Features & Modules](#-key-features--modules)
  - [1. Context-Aware Chat Assistant & Scope Guard](#1-context-aware-chat-assistant--scope-guard)
  - [2. Groundwater Diagnostic & Recommendation System](#2-groundwater-diagnostic--recommendation-system)
  - [3. What-If Extraction & Multi-Sector Scenario Analysis](#3-what-if-extraction--multi-sector-scenario-analysis)
  - [4. Interactive Visualizations & UI Integration](#4-interactive-visualizations--ui-integration)
- [System Architecture](#-system-architecture)
- [Data Ingestion & CGWB Methodology](#-data-ingestion--cgwb-methodology)
- [Technology Stack](#-technology-stack)
- [Repository Structure](#-repository-structure)
- [Installation & Setup](#-installation--setup)
- [Running the Application](#-running-the-application)
- [API Documentation](#-api-documentation)
- [Testing & Benchmark Methodology](#-testing--benchmark-methodology)
- [Known Limitations & Future Work](#-known-limitations--future-work)
- [Credits & References](#-credits--references)

---

## 🎯 Overview & Problem Statement

Official Indian groundwater assessments under **IN-GRES / CGWB (GEC 2024–2025)** are published in multi-row hierarchical workbooks separating **Command (`C`)**, **Non-Command (`NC`)**, and **Poor Quality (`PQ` / saline)** zones, sectoral groundwater extraction (Irrigation, Domestic, Industrial), recharge contributors, environmental flows, and aquifer storage.

Accessing and interpreting this data poses three practical challenges addressed by this project:
1. **Fragile workbook parsing & metric conflation:** Naive column-position reads misread merged headers or mix Freshwater (`C + NC`) official CGWB Stage with Total (`C + NC + PQ`) draft.
2. **Rigid chatbots & numerical hallucinations:** Keyword-only bots reject natural follow-up questions (e.g., asking *"Is it good to grow mango crops there?"* after checking a district) as unrecognized locations, or risk emitting unverified figures.
3. **Lack of actionable stress interpretation:** Knowing a district's percentage stage alone does not tell planners which sector drives draft, how many `ham` must be reduced to reach **Safe (`≤ 70%`)**, or what local field data is still missing before recommending interventions.

---

## 🤝 Project Context & Attribution

> **Important Attribution Note:** **IN-GRES (India-Groundwater Resource Estimation System)** is the official groundwater resource estimation framework and dataset ecosystem developed under CGWB / IIT Hyderabad standards. I did **not** build the IN-GRES platform or its government datasets, nor did I author the entire initial application scaffold from scratch.

### Baseline Codebase vs. Contributed Extensions

| Component | Origin / History | Details |
| --- | --- | --- |
| **IN-GRES / CGWB Workbook & Core Web Scaffold** | Official dataset + Initial repo (`afa14f4`) | `backend/ingres-data.xlsx`, FastAPI + React/Recharts core layout, initial `parser.py` scope guard, `verifier.py`, single-slider `WhatIfPanel.jsx`, `translation.py`, `evaluate.py` 50-query harness, optional `rasa/` project, and Render/Vercel configs. |
| **Data Integrity, Official `C+NC` Math, Diagnostics & Multi-Sector Scenarios** | Contributed via `feature/groundwater-diagnostics` (`89b8b04` / PR `#1`) | Rebuilt multi-row header workbook ingestion (`data_processor.py`, 56 mapped fields across 57 table columns), expanded `GroundwaterData` ORM (`models.py`), deterministic district lookup (`crud.py`), official Freshwater (`C+NC`) vs. Total (`C+NC+PQ`) calculations (`whatif.py`), `backend/app/diagnostics/` engine + intervention/scenario modules, `DiagnosticPanel.jsx`, multi-sector UI in `WhatIfPanel.jsx`, and tab integration in `App.jsx` / `Sidebar.jsx`. |
| **Context-Aware Chat Assistant & Agricultural Decision Support** | Contributed via `feature/context-aware-chat` (`6a1f440` / PR `#2`) | Built `backend/app/chat_advisor.py`, extended `parser.py` with crop/irrigation/sustainability/trend/concept intents + contextual follow-ups + targeted unknown-location extraction, added session state (`_SESSION_CONTEXT`, `session_id`, `context`) in `main.py` / `schemas.py` / `ChatWindow.jsx`, fixed exposed state What-If and rainfall comparison handlers, and added `backend/tests/test_chat_assistant.py`. |

---

## 🚀 Key Features & Modules

### 1. Context-Aware Chat Assistant & Scope Guard
Implemented across [`backend/app/main.py`](backend/app/main.py), [`backend/app/parser.py`](backend/app/parser.py), [`backend/app/chat_advisor.py`](backend/app/chat_advisor.py), [`backend/app/verifier.py`](backend/app/verifier.py), and [`frontend/src/components/ChatWindow.jsx`](frontend/src/components/ChatWindow.jsx).

- **Supported Query Intents:**
  - **Groundwater Lookups & Metrics:** `ask_groundwater`, `ask_rainfall`, `ask_extraction`, `ask_recharge`, `ask_availability`, `ask_category`, `ask_state_list`, `compare`, and chat-level `ask_whatif` previews (state-level What-If queries return verified state aggregates and prompt for district selection rather than picking an arbitrary district; rainfall comparisons report verified rainfall in `mm` for each compared entity).
  - **Advisory & Decision-Support Intents (`chat_advisor.py`):**
    - `ask_agricultural_suitability` — Evaluates crop queries (supporting `CROP_SYNONYMS` across 14 reference crops: *mango, rice/paddy, sugarcane, banana, coconut, arecanut, wheat, maize, cotton, groundnut, millets, pulses, vegetables, coffee*, plus `<grow|cultivate|plant> <crop>`) using a 5-part grounded template: **(1) Verified INGRES/CGWB Data**, **(2) Derived Groundwater Indicators**, **(3) General Agricultural Reference Context** (`CROP_PROFILES`, explicitly tagged as non-district-verified), **(4) Unavailable Local Data**, and **(5) Qualified Conclusion**.
    - `ask_crop_water_requirements` — Compares general crop water-demand tiers (low, low-to-moderate, moderate, high) alongside active district context if present.
    - `ask_irrigation_impact` — Explains how irrigation draft drives local extraction stage, distinguishing surface vs. groundwater sources and noting that pump/solar efficiency alone does not save water without pumping limits.
    - `ask_sustainability` — Quantifies current stage vs. the `70%` Safe ceiling (`required_reduction_to_safe_ham` and `%`), while disclosing that single-cycle `2024–2025` stage alone cannot prove multi-year water-table decline or local quality safety.
    - `ask_trends_causes` — Breaks down sectoral draft shares (`Irrigation`, `Domestic`, `Industrial`) and notes that multi-year piezometer series are not present in INGRES.
    - `ask_general_groundwater` — Explains CGWB extraction stage definitions and thresholds cleanly without inventing location data.
- **Multi-Turn Session Context & Clarifications:**
  - `ChatWindow.jsx` generates a session ID and passes `(session_id, context)` to `POST /chat`, backed by bounded server-side storage (`_SESSION_CONTEXT`, max 500 sessions in `main.py`).
  - Resolves anaphoric follow-ups (`"there"`, `"this district"`, `"What about rice?"`), handles missing-location clarification turns (`pending_clarification` asked → user replies with `"Mysuru"`), clears `last_district` when switching to a state query, and clears stale `last_crop` on location-only shifts.
- **Scope Guard & Numeric Verification (`parser.py` & `verifier.py`):**
  - Blocks out-of-scope forecasts/years (`> 2025`), unavailable historical years, unsupported metrics (`temperature`, `gdp`, `air quality`, etc.), and unrecognized place names (extracting only the place candidate rather than echoing entire questions).
  - `verify_response()` checks numeric values emitted in bot/diagnostic text against retrieved DB records, derived totals/percentages (`extra_allowed`), and CGWB thresholds (`70`, `90`, `100`) within `TOLERANCE = 0.6`, attaching `verified` badges and `verification_issues` to API/UI responses.

### 2. Groundwater Diagnostic & Recommendation System
Implemented across [`backend/app/diagnostics/engine.py`](backend/app/diagnostics/engine.py), [`backend/app/diagnostics/intervention_engine.py`](backend/app/diagnostics/intervention_engine.py), and [`frontend/src/components/DiagnosticPanel.jsx`](frontend/src/components/DiagnosticPanel.jsx) via `POST /diagnose`.

Rather than generating generic conservation tips, the recommendation engine operates on verified district metrics and applies strict epistemic tagging (`VERIFIED_FACT`, `DERIVED_CALCULATION`, `HYPOTHESIS_UNVERIFIED`, `DATA_MISSING`, `RECOMMENDATION`):

1. **Condition & Safe-Gap Quantification:** Separates official Freshwater (`C + NC`) Stage from Total (`C + NC + PQ`) Stage, computes `safe_target_extraction_ham = 0.70 × fresh_extractable_ham`, and calculates exact reduction needed (`ham` and `%`) to reach **Safe (`≤ 70%`)**.
2. **Sectoral & Recharge Attribution:** Computes draft shares for `Irrigation`, `Domestic`, and `Industrial`, plus shares across 8 recharge sources (`Rainfall Recharge`, `Surface Water Irrigation`, `Groundwater Irrigation`, `Canals`, `Tanks and Ponds`, `Water Conservation Structures`, `Pipelines`, `Sewages & Flash Flood Channels`).
3. **Evidence-Gated Recommendation Workflow (`analyze_interventions`):**
   - **Irrigation Demand Management & Micro-Irrigation Audit:** Triggered when `extraction_irrigation_ham > 0` and either irrigation share `≥ 40%` or stressed district draft `≥ 2,000 ham`; recommends reducing avoidable over-irrigation, irrigation scheduling, and evaluating drip/sprinkler adoption (with explicit caveats on return-flow recharge and missing crop mix).
   - **Domestic Leakage (NRW) & Wastewater Reuse:** Triggered when domestic share `≥ 15%`, stressed domestic draft `≥ 2,000 ham`, or `domestic_alloc_2025_ham > 1.1 × extraction_domestic_ham`; recommends municipal leakage audits, STP reuse, and alternative supply evaluation (with quality-testing warnings because quality fields are `0/726` populated).
   - **Industrial Water Audits & Non-Freshwater Substitution:** Triggered when industrial share `≥ 10%` or stressed industrial draft `≥ 1,000 ham`; highlights closed-loop recycling, ZLD/CETP effluent substitution, and PQ-zone substitution where present.
   - **Pumping Hours / Volumetric Control Guardrail:** Triggered alongside irrigation draft in stressed areas; warns that improving pump/solar energy efficiency lowers `kWh`/cost per `m³` but **does not reduce groundwater draft** unless pumping hours or extracted volumes are capped.
   - **Hydrogeology-Screened Artificial Recharge Study:** Triggered **only** in stressed districts with `rainfall_mm ≥ 600 mm` and recharge-worthy share `≥ 50%` (otherwise emits an unverified hypothesis prioritizing demand reduction over supply-side recharge), explicitly requiring external NAQUIM lithology and piezometer clearance.
4. **Explicit `DATA_MISSING` Registry:** Marks 9 external datasets unavailable in INGRES (`well_and_borewell_counts`, `pump_types_and_energy_sources`, `drip_and_sprinkler_adoption`, `crop_area_and_water_requirements`, `agricultural_electricity_consumption`, `groundwater_level_decline_trend`, `naquim_aquifer_hydrogeology`, `water_quality_tagging`, `sub_district_assessment_units`) alongside concrete verification next steps.

### 3. What-If Extraction & Multi-Sector Scenario Analysis
Implemented in [`backend/app/whatif.py`](backend/app/whatif.py), [`backend/app/diagnostics/scenario_simulator.py`](backend/app/diagnostics/scenario_simulator.py), and [`frontend/src/components/WhatIfPanel.jsx`](frontend/src/components/WhatIfPanel.jsx).

- **Uniform What-If Simulator (`POST /whatif`):**
  - **User Inputs:** State, District, and Extraction Change (`-80%` to `+100%` in the React slider/input; `-100%` to `+1000%` API validation).
  - **Calculations & Outputs:** Computes `new_extraction = max(0, current_extraction × (1 + pct_change / 100))`, `new_stage = (new_extraction / annual_extractable) × 100`, CGWB category transition (`Safe ≤ 70%`, `Semi-Critical 70–90%`, `Critical 90–100%`, `Over-Exploited > 100%`), reduction `%` needed to drop below `100%` (Over-Exploited ceiling) and `70%` (Safe ceiling), plus a before/after bar chart. Uses **Total (`C + NC + PQ`)** fields and displays a PQ-zone note where applicable.
- **Multi-Sector Scenario Comparison (`POST /whatif/scenarios`):**
  - **User Inputs:** Independent percentage adjustments for **Irrigation**, **Domestic**, and **Industrial** (`-100%` to `+100%` UI sliders, `-100%` to `+200%` UI numeric boxes, `-100%` to `+500%` API validation), customizable scenario names, 3 built-in presets, and up to 10 queued scenarios compared side-by-side.
  - **Basis Separation:** Uses `EXACT_CGWB_C_NC` when exact `C + NC` sectoral draft sums reconcile within `1.0 ham` (or non-PQ districts where total draft equals `C + NC`), and switches transparently to `ESTIMATE_MATHEMATICAL_SCENARIO` (proportional scaling) when PQ-zone sector splits are incomplete.
- **Scientific Scope Disclaimer:** Both What-If engines perform **deterministic arithmetic scenario calculations** on single-cycle `2024–2025` INGRES extraction/extractable ratios. They are **not** calibrated hydrogeological, aquifer-response, or climate/recharge predictive models, and simulated Safe transitions do not establish practical field feasibility without external MI Census, crop, energy, and piezometer verification.

### 4. Interactive Visualizations & UI Integration
Implemented in [`frontend/src/App.jsx`](frontend/src/App.jsx), [`frontend/src/components/ChartDisplay.jsx`](frontend/src/components/ChartDisplay.jsx), [`frontend/src/components/Sidebar.jsx`](frontend/src/components/Sidebar.jsx), and supporting card/badge components:
- Keeps **Chat**, **What-If Analysis**, and **Diagnostics** panes mounted simultaneously in `App.jsx` to preserve user state across tab switches, with one-click district handoffs between `DiagnosticPanel` and `WhatIfPanel`.
- Renders Recharts visualizations across `rainfall`, `extraction` (color-coded bars with `70%` / `90%` / `100%` CGWB reference lines), dual-panel `comparison` (rainfall + extraction stage), `state_overview` (district rainfall + extraction + CGWB category donut), standalone `cgwb_distribution`, `whatif_comparison`, and Diagnostic sectoral bar charts.
- Sidebar supports 8 UI languages (`en`, `hi`, `kn`, `te`, `ta`, `mr`, `bn`, `gu`; `TranslationService` also defines `ml` and `pa` entries) and quick-access navigation across all 37 states/UTs.

---

## 🏗️ System Architecture

```mermaid
flowchart TB
    UI["React 18 Frontend<br/>(ChatWindow · WhatIfPanel · DiagnosticPanel · ChartDisplay · Sidebar)"]
    API["FastAPI Backend (backend/app/main.py)<br/>CORS · Pydantic v2 Schemas · /chat · /whatif · /whatif/scenarios · /diagnose · /evaluate"]

    UI -->|Axios HTTP JSON| API

    subgraph ChatPipeline["Chat Assistant Pipeline (/chat)"]
        TR["translation.py<br/>Keyword Map + deep-translator"]
        PR["parser.py<br/>Intent · Crop · Location · Context · Scope Guard<br/>(+ optional Rasa HTTP)"]
        CA["chat_advisor.py<br/>Crop · Irrigation · Sustainability · Trends · Guide"]
        VR["verifier.py<br/>Numeric Consistency Check vs DB & Derived Values"]
        CTX["Session State (_SESSION_CONTEXT)<br/>& ChatHistory Logging"]
        TR --> PR --> CA --> VR --> CTX
    end

    subgraph DiagSim["Diagnostics & Simulation Pipeline"]
        WI["whatif.py<br/>Single-Target What-If & Official C+NC Metrics"]
        DG["diagnostics/engine.py<br/>Condition · Safe Gap · Evidence Registry"]
        IE["diagnostics/intervention_engine.py<br/>Evidence-Gated Interventions & DATA_MISSING Tags"]
        SS["diagnostics/scenario_simulator.py<br/>Sector-Wise C+NC vs Total Scenarios"]
        DG --> IE
        DG --> SS
        SS --> WI
    end

    API --> ChatPipeline
    API --> DiagSim

    DB[("SQLAlchemy 2.0 ORM<br/>SQLite (backend/ingres.db, default)<br/>or PostgreSQL (DATABASE_URL)")]
    XL["backend/ingres-data.xlsx<br/>(data_processor.py · GEC 2024–2025)"]

    XL -->|Startup Validation & Load| DB
    ChatPipeline --> DB
    DiagSim --> DB
```

---

## 📊 Data Ingestion & CGWB Methodology

- **Source Workbook:** [`backend/ingres-data.xlsx`](backend/ingres-data.xlsx) (sheet `GEC`, metadata Assessment Year `2024-2025`, source label `INGRES / CGWB (GEC-2024-2025)`).
- **Ingestion Pipeline ([`backend/app/data_processor.py`](backend/app/data_processor.py)):** Resolves merged 3-row multi-level column paths across **56 mapped workbook fields** (`HEADER_PATH_TO_FIELD`, stored across 57 columns including `id` in `groundwater_data`), explicitly preserves `0.0` numeric values via `clean_numeric()`, skips aggregate summary rows, validates 9 `REQUIRED_FIELDS` before modifying DB state, and stores **726 district/unit records** across **37 states/UTs** (`723` distinct district strings).
- **Official CGWB Classification Thresholds ([`backend/app/whatif.py`](backend/app/whatif.py)):**
  - 🟢 **Safe:** `Stage ≤ 70%`
  - 🟡 **Semi-Critical:** `70% < Stage ≤ 90%`
  - 🟠 **Critical:** `90% < Stage ≤ 100%`
  - 🔴 **Over-Exploited:** `Stage > 100%`
- **Freshwater (`C + NC`) vs. Total (`C + NC + PQ`) Basis:** In line with CGWB methodology, official stage metrics use Freshwater Command + Non-Command (`C + NC`) zones, kept separate from Total (`C + NC + PQ`) sums used when Poor Quality (`PQ`) breakdowns are incomplete.

---

## 🛠️ Technology Stack

Verified directly against [`backend/requirements.txt`](backend/requirements.txt), [`frontend/package.json`](frontend/package.json), and [`runtime.txt`](runtime.txt):

- **Backend:** Python (`3.12.8` in `runtime.txt`; 3.10+ compatible), `fastapi==0.109.0`, `uvicorn[standard]==0.27.0`, `sqlalchemy==2.0.25`, `pydantic==2.5.3`, `pydantic-settings==2.1.0`, `pandas==2.2.0`, `openpyxl==3.1.2`, `psycopg2-binary==2.9.9`, `deep-translator==1.11.4`, `python-dotenv==1.0.0`, `python-multipart==0.0.6`, `httpx==0.26.0`
- **Database:** SQLite (`backend/ingres.db` out of the box when `DATABASE_URL` is unset) or PostgreSQL via `DATABASE_URL`
- **Optional NLU Service:** Rasa NLU (`USE_RASA=false` by default; falls back cleanly to built-in regex/context parser in `parser.py`)
- **Frontend:** `react==^18.2.0`, `react-dom==^18.2.0`, `axios==^1.6.5`, `recharts==^2.15.4`, `react-icons==^5.0.1`, `react-scripts==5.0.1`
- **Testing & Deployment:** Python built-in `unittest` + `evaluate.py` benchmark, Render blueprint (`render.yaml`), Windows launchers (`run_app.bat`, `run_app.ps1`)

---

## 📁 Repository Structure

```text
INGRES_UPD/
├── backend/
│   ├── app/
│   │   ├── diagnostics/
│   │   │   ├── __init__.py
│   │   │   ├── engine.py                # Diagnostic orchestrator & numeric verification
│   │   │   ├── intervention_engine.py   # Threshold-gated interventions & DATA_MISSING tags
│   │   │   ├── scenario_simulator.py    # Multi-sector C+NC vs. Total math scenarios
│   │   │   └── schemas.py               # DiagnosticRequest/Response & Scenario schemas
│   │   ├── chat_advisor.py              # Grounded crop, irrigation, sustainability & trend advisor
│   │   ├── crud.py                      # Deterministic exact/normalized/partial DB lookups
│   │   ├── data_processor.py            # Merged-header GEC workbook ingestion (56 mapped fields)
│   │   ├── database.py                  # SQLite default / PostgreSQL DATABASE_URL setup
│   │   ├── evaluate.py                  # 50-question benchmark suite
│   │   ├── main.py                      # FastAPI app, routes, session context & ChatHistory
│   │   ├── models.py                    # GroundwaterData & ChatHistory SQLAlchemy models
│   │   ├── parser.py                    # Intent, crop, location, context & scope-guard parser
│   │   ├── schemas.py                   # Chat & What-If Pydantic schemas
│   │   ├── translation.py               # Multilingual keyword maps & deep-translator wrapper
│   │   ├── verifier.py                  # Numeric response checker against DB & derived figures
│   │   └── whatif.py                    # Single-target What-If & official C+NC Safe math
│   ├── tests/
│   │   └── test_chat_assistant.py       # Context, advisory, regression & benchmark unit tests
│   ├── .env.example                     # Backend PostgreSQL & Rasa environment template
│   ├── ingres-data.xlsx                 # CGWB / INGRES 2024–2025 Excel workbook
│   ├── ingres.db                        # Local SQLite database (726 records)
│   └── requirements.txt
├── frontend/
│   ├── public/
│   │   └── index.html
│   ├── src/
│   │   ├── components/
│   │   │   ├── CGWBBadge.jsx            # CGWB category badge component
│   │   │   ├── ChartDisplay.jsx         # Recharts visualizations (rainfall/extraction/compare)
│   │   │   ├── ChatWindow.jsx           # Context/session-aware Chat UI
│   │   │   ├── DataCard.jsx             # District metric card with source/year footer
│   │   │   ├── DataSourceTag.jsx        # Source, year & confidence tag component
│   │   │   ├── DiagnosticPanel.jsx      # Evidence-tagged Diagnostic UI tab
│   │   │   ├── InputBar.jsx             # Chat prompt input bar
│   │   │   ├── MessageBubble.jsx        # Enriched chat message renderer
│   │   │   ├── Sidebar.jsx              # Language selector, tab navigation & 37-state list
│   │   │   ├── VerificationBadge.jsx    # Verified / Verification-warning badge
│   │   │   └── WhatIfPanel.jsx          # Single-slider & multi-sector scenario UI tab
│   │   ├── App.css
│   │   ├── App.jsx                      # 3-tab app shell with cross-tab target handoff
│   │   └── index.js
│   ├── .env.example                     # REACT_APP_API_URL template
│   ├── package.json
│   └── package-lock.json
├── rasa/                                # Optional Rasa NLU domain, config, NLU & stories
├── render.yaml                          # Render PostgreSQL + FastAPI + React static deploy spec
├── run_app.bat                          # Windows batch launcher (backend + frontend)
├── run_app.ps1                          # Windows PowerShell launcher (backend + frontend)
├── runtime.txt                          # Python 3.12.8 runtime pin
├── vercel.json                          # Experimental frontend/backend service routing config
└── README.md
```

---

## 🔧 Installation & Setup

### Prerequisites
- **Python 3.10+** (`3.12.8` pinned in `runtime.txt`)
- **Node.js 18+** and **npm**
- *(Optional)* **PostgreSQL 14+** (not required for local development — SQLite is used automatically if `DATABASE_URL` is unset)

### 1. Clone a Repository

```bash
# Collaborative / upstream INGRES_UPD repository:
git clone https://github.com/Tushar2332/INGRES_UPD.git
cd INGRES_UPD

# Or personal fork repository:
git clone https://github.com/syed102003/INGRES-CHATBOT.git
cd INGRES-CHATBOT
```

### 2. Backend Setup

```bash
cd backend
python -m venv venv

# Windows PowerShell:
.\venv\Scripts\Activate.ps1
# macOS / Linux:
# source venv/bin/activate

pip install -r requirements.txt
```

- **Default database:** Without any `.env` file, [`database.py`](backend/app/database.py) uses local SQLite at `backend/ingres.db` and `startup_event()` automatically validates and reloads [`backend/ingres-data.xlsx`](backend/ingres-data.xlsx).
- **Optional PostgreSQL / Rasa config:** Copy `backend/.env.example` to `backend/.env`:
  ```env
  DATABASE_URL=postgresql://ingres_user:your_password@localhost:5432/ingres_db
  USE_RASA=false
  ```

### 3. Frontend Setup

From the repository root:

```bash
cd frontend
npm install
```

*(Optional)* Copy `frontend/.env.example` to `frontend/.env` and set `REACT_APP_API_URL` if the backend runs on a non-default origin (defaults to `http://localhost:8000`).

### 4. Optional Rasa NLU Setup
Rasa is **disabled by default** (`USE_RASA=false`), so no Rasa server is required. To enable Rasa NLU hybrid intent parsing (from the repository root):

```bash
cd rasa
pip install -r requirements.txt
rasa train
rasa run --enable-api --cors "*"
```
Then set `USE_RASA=true` and `RASA_SERVER_URL=http://localhost:5005` for the backend.

---

## 🏃 Running the Application

### Start Backend API Server (`http://localhost:8000`)

```bash
cd backend
python -m uvicorn app.main:app --reload --port 8000
```

### Start Frontend UI Server (`http://localhost:3000`)

```bash
cd frontend
npm start
```

### Windows One-Click Launchers
From the repository root, run `run_app.bat` or `.\run_app.ps1` (assumes `python` on `PATH` has backend dependencies installed; installs `frontend/node_modules` automatically if absent and starts both servers in separate windows).

---

## 🔌 API Documentation

FastAPI auto-generates interactive API documentation when the backend is running:
- **Swagger UI:** [`http://localhost:8000/docs`](http://localhost:8000/docs)
- **ReDoc:** [`http://localhost:8000/redoc`](http://localhost:8000/redoc)

### Live Endpoints (`backend/app/main.py`)

| Method | Endpoint | Purpose |
| --- | --- | --- |
| `POST` | `/chat` | Multi-turn conversational query (`message`, `language`, optional `session_id` & `context`) returning verified answer, charts, suggestions, badges & updated `context` |
| `POST` | `/whatif` | Single-district uniform extraction simulation (`state`, `district`, `pct_change` in `[-100, 1000]`) |
| `POST` | `/whatif/scenarios` | Multi-sector scenario comparison (`irrigation_pct_change`, `domestic_pct_change`, `industrial_pct_change`, 1–10 scenarios) with `C+NC` vs. `Total` separation |
| `POST` | `/diagnose` | Full district groundwater diagnosis, Safe-threshold gap, sector/recharge breakdown, evidence-gated interventions & `DATA_MISSING` registry |
| `GET` | `/evaluate` | Runs the 50-question benchmark evaluation against the live database |
| `GET` | `/states` | Lists all 37 states/UTs sorted alphabetically |
| `GET` | `/districts/{state}` | Lists districts belonging to the specified state |
| `GET` | `/data/{state}` | Returns up to 50 formatted district records (`_format_records(..., include_all=True)`) with CGWB category & metadata |
| `GET` | `/stats/total` | Total records (`726`), distinct states (`37`), distinct districts (`723`), Rasa flag & assessment metadata |
| `GET` | `/stats/{state}` | State averages (rainfall, extraction stage, recharge, net availability) and CGWB classification |
| `GET` | `/cgwb/{state}` | CGWB category counts (`SAFE`, `SEMI-CRITICAL`, `CRITICAL`, `OVER-EXPLOITED`) and donut chart payload |
| `GET` | `/assessment_year` | Assessment year (`2024-2025`), source label, and confidence tag |
| `GET` | `/health` | Health status, version string, `rasa_enabled`, and active feature list |

---

## 🧪 Testing & Benchmark Methodology

### 1. Automated Backend Unit & Regression Tests

```bash
cd backend
python -m unittest -v tests/test_chat_assistant.py
```

Verified on the `main` branch (**8 test methods, `0` failures, `0` skipped**):
- Multi-turn context resolution (`Mysuru` → `"Is it good to grow mango crops there?"` → `"What about rice?"` → `"Which crops require less water?"` → `"Would increasing irrigation put pressure on groundwater?"` → `"What about Bengaluru Urban?"`)
- State-level context reset (`Karnataka`), missing-location clarification follow-up, unknown-location token extraction (`"Atlantis"`), unsupported-metric refusal (`"GDP"`), general CGWB/trends/sustainability intents, state-level What-If guard, rainfall-specific comparisons, and end-to-end checks on `/whatif`, `/whatif/scenarios`, and `/diagnose`.

### 2. 50-Question Benchmark (`backend/app/evaluate.py` / `GET /evaluate`)
Evaluates 50 curated queries across 8 categories: Normal queries (10), Comparison (5), Historical years (5), Forecast traps (10), Unknown locations (5), Unsupported metrics (5), What-If queries (5), and CGWB categories (5). Verified latest run results (executed in-session with `HAS_DEEP_TRANSLATOR = False` for offline unit isolation):

| Metric | Measured Result |
| --- | --- |
| **Overall Accuracy** | **96.0%** (`50` queries) |
| **Correct Scope-Refusal Rate** | **100.0%** |
| **Unsupported Number Rate** | **0.0%** |

### 3. Frontend Production Build & Browser Verification

```bash
cd frontend
npm run build
```

- React production build compiles cleanly (`react-scripts build`).
- End-to-end browser verification confirmed `Chat`, `What-If Analysis`, and `Diagnostics` tab rendering, multi-turn chat follow-ups (`Mysuru` → mango → rice → `Bengaluru Urban`), preserved chat history across tab switches, zero console errors, and zero failed HTTP requests.

---

## ⚠️ Known Limitations & Future Work

- **District-Level & Single-Cycle Data Boundary:** Loaded INGRES records cover a single `2024–2025` district snapshot; well/pump counts (6th Minor Irrigation Census), drip/sprinkler adoption rates, crop acreage, agricultural feeder power consumption, piezometer water-level decline series, NAQUIM aquifer lithology, sub-district (block/taluk) units, and district water-quality tags (`0/726` populated) are absent and explicitly labeled `DATA_MISSING`.
- **In-Memory Session Context:** `_SESSION_CONTEXT` in `main.py` holds up to 500 sessions in Python memory and resets on backend restarts.
- **Offline vs. Live Translation:** Regional district aliases work offline, whereas full non-English query/response translation via `deep-translator` requires internet connectivity (unit tests set `HAS_DEEP_TRANSLATOR = False`).
- **Response Verification Heuristic:** `verifier.py` checks numerical consistency (within `±0.6` tolerance and skipping integers `< 2` or years `1990–2030`) rather than semantic text entailment.
- **Known Pre-Existing Parser Edge Cases:**
  1. `ask_whatif` contains regex `r'\bsimulat\b'`, which misses `"Simulate 30% reduction..."` (routing it to `ask_extraction`).
  2. District matching appends inferred parent states into `found_states`, causing `compare` queries like `"Mysore vs Bangalore groundwater"` to include `Karnataka` alongside both districts.
  3. Queries asking to list districts filtered by CGWB category (e.g., *"Which districts in Punjab are over-exploited?"*) currently return the state summary and category counts rather than a filtered list of districts.
- **Root Cleanup Opportunity:** `all_code.txt`, `copy_all_files.js`, and local review diff/backup artifacts remain untracked or legacy from initial scaffolding.

---

## 🙏 Credits & References

- **IN-GRES / CGWB:** [Central Ground Water Board & IIT Hyderabad IN-GRES Portal](https://ingres.iith.ac.in/home) for `GEC 2024–2025` groundwater resource estimation data and thresholds.
- **Core Team & Contributors:** Baseline project scaffold by Tushar Pandita (`Tushar2332/INGRES_UPD`); Diagnostics, Data Integrity/C+NC separation, Sector Scenarios, Context-Aware Chat Assistant, and Documentation extensions by Syed Abdul Manan (`syed102003`).
- **Frameworks & Libraries:** FastAPI, SQLAlchemy, Pydantic, OpenPyXL, Pandas, React, Recharts, deep-translator, and Rasa.
