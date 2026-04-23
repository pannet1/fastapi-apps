# FastAPI Controller App

A FastAPI application that controls a runnable logic component with start/stop capability. The logic runs as a background task and can be toggled from a web UI.

## What It Does

- **Main App** (`main.py`) - Serves a web UI with Start/Stop button
- **Logic App** (`logic_app.py`) - Runnable component that starts/stops independently

The two apps appear as one unified application to the end user.

## Quick Start

```bash
# Create virtual environment
python3 -m venv .venv

# Activate
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Run
python -m uvicorn main:app --port 8000
```

Then open **http://localhost:8000** in your browser.

## Features

- **Web UI** - Start/Stop button toggles the logic app
- **API Endpoints** - Programmatic control
- **State Management** - Startup data preserved, app data cleared on stop
- **Graceful Shutdown** - Background task properly cancelled

## Architecture

```
localhost:8000
├── /                  → Web UI (Controller or Logic app)
├── /api/logic/status  → Get running state
├── /api/logic/data    → Get app data (only when running)
├── /api/logic/start   → Start logic app
├── /api/logic/stop    → Stop logic app
└── /api/memory       → Memory usage info
```

## Use Cases

- Trading bots that need scheduled start/stop
- Background workers triggered on demand
- Batch jobs that run intermittently
- Any app that should run independently of the main server

## Files

```
main.py          # Main controller app
logic_app.py    # Logic component (starts/stops)
requirements.txt
```

## API Examples

```bash
# Check status
curl http://127.0.0.1:8000/api/logic/status

# Start logic
curl -X POST http://127.0.0.1:8000/api/logic/start

# Get data (when running)
curl http://127.0.0.1:8000/api/logic/data

# Stop logic
curl -X POST http://127.0.0.1:8000/api/logic/stop
```

## Requirements

- Python 3.9+
- FastAPI
- Uvicorn
- Pydantic

Install with: `pip install -r requirements.txt`