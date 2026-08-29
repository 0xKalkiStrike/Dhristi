# Installation

## Prerequisites
- Python 3.11+ (3.13 supported), Node 18+ (22 supported), ~2 GB free disk.
- GPU optional (CUDA auto-detected; CPU fallback otherwise).

## Backend (local)
```bash
cd backend
python -m venv .venv
# Windows: .venv\Scripts\activate   | Linux/Mac: source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env                # edit if using PostgreSQL
python ../scripts/setup/init_db.py
python ../scripts/setup/download_models.py
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

## Frontend (local)
```bash
cd frontend
npm install
npm run dev            # http://localhost:5173
```

## PostgreSQL (optional)
Set in `backend/.env`:
```
DATABASE_URL=postgresql+psycopg://drishti:drishti@localhost:5432/drishti
```
Install the driver: `pip install "psycopg[binary]"`. Then run `init_db.py` (or Alembic).

## Alembic migrations (optional)
```bash
cd backend
alembic revision --autogenerate -m "init"
alembic upgrade head
```
`init_db.py` already creates all tables for a zero-config start; Alembic is for schema
evolution in a PostgreSQL deployment.

## Docker
```bash
cd docker
docker compose up --build
# frontend :5173  backend :8000  postgres :5432
```
AI inference runs on CPU in-container. For GPU, run the backend natively and point the
frontend/env at it.

## GPU notes
- The app calls `torch.cuda.is_available()` and uses CUDA automatically when present.
- Set `AI_DEVICE=cpu` to force CPU. `AI_DEVICE=cuda` requires a CUDA-enabled torch build.
- On CPU, lower `PROCESS_FPS` and raise `DETECT_EVERY_N_FRAMES` for smoother throughput.

## MongoDB (native, non-Docker) — optional live-event store
```powershell
scripts\setup\setup_mongodb.ps1        # portable Community ZIP -> mongod on :27017
```
See [mongodb.md](mongodb.md). Disable with `MONGODB_ENABLED=false`.

## Port forwarding (FastAPI HTTP+WS proxy)
```powershell
scripts\setup\run_port_forward.ps1     # 0.0.0.0:9000 -> http://127.0.0.1:8000
```
See [port_forwarding.md](port_forwarding.md).

## Windows PowerShell helpers
`scripts\setup\setup_backend.ps1`, `run_backend.ps1`, `setup_frontend.ps1`, `run_frontend.ps1`,
`setup_mongodb.ps1`, `run_mongodb.ps1`, `run_port_forward.ps1`.
