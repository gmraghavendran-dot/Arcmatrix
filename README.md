# ArcMatrix



## Windows setup
```powershell
.\setup_venv.ps1
.\venv312\Scripts\Activate.ps1
```

Then create `.env` from `.env.example` and run:
```powershell
.\start.ps1
```

API: `http://127.0.0.1:8000/`
Docs: `http://127.0.0.1:8000/docs`

---


Enterprise Engineering, Cloud, CI/CD & AI Intelligence Platform.

## Current architecture

- PostgreSQL `arcmatrix`
- `raw` source tables
- `core` standardized tables
- `analytics` intelligence tables
- FastAPI backend
- Plain HTML/CSS/JS dashboard

The four source domains are kept separate because their natural keys and time ranges differ.

## Requirements

- Python 3.12+
- PostgreSQL with the existing `arcmatrix` database and analytics tables
- Windows PowerShell commands below

## Setup

1. Create the virtual environment:

```powershell
python -m venv venv312
```

2. Activate it:

```powershell
.\venv312\Scripts\Activate.ps1
```

3. Install packages:

```powershell
python -m pip install --upgrade pip
pip install -r requirements.txt
```

4. Copy environment template:

```powershell
Copy-Item .env.example .env
```

Edit `.env` and set your PostgreSQL password and local dataset path.

## Start the API + dashboard

From `C:\ArcMatrix`:

```powershell
python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000 --reload
```

Open:

- Dashboard: http://127.0.0.1:8000/
- API docs: http://127.0.0.1:8000/docs
- Health: http://127.0.0.1:8000/health

## API endpoints

- `/api/platform/summary`
- `/api/platform/health`
- `/api/engineering/summary`
- `/api/cicd/summary`
- `/api/cloud/summary`
- `/api/ai/summary`
- `/api/insights/summary`
- `/api/insights/critical`

## Important data-model note

ArcMatrix does not claim unsupported causal relationships across the four datasets. The source time ranges are different, so the platform presents domain-specific evidence and platform-level summaries rather than fabricating cross-domain causality.

## Data loaders

Existing project loaders are retained:

- `ingestion.py` — generic source ingestion
- `load_github.py` — GHPR raw loader
- `load_cicd.py` — direct CI/CD raw loader

These should be run only when reloading raw data; the backend reads from the already-prepared PostgreSQL analytics tables.
