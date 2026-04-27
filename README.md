# FastAPI Watchdog App

A FastAPI application with APScheduler watchdog that manages a trading logic component with start/stop capability and market hours scheduling.

## Features

- **Scheduled Auto-Start/Stop** - Logic runs only during configured market hours (Mon-Fri, 09:14 - 23:59)
- **Watchdog Service** - APScheduler checks every 60s, auto-manages logic lifecycle
- **Web UI** - Trading dashboard when running, sleeping page when stopped
- **Manual Override** - Restart button available anytime
- **Systemd Integration** - Runs as user service, survives reboots
- **HTTP Basic Auth** - Optional authentication via environment variable

## Quick Start

```bash
# Setup
uv sync --python 3.10

# Run locally (for testing)
uv run python -m uvicorn src.main:app --host 127.0.0.1 --port 8000

# Run tests
uv run pytest tests/ -v
```

Open **http://127.0.0.1:8000** in your browser.

## Local Dev with Nginx (Production Simulation)

```bash
# Terminal 1: Run app on 8000
uv run python -m uvicorn src.main:app --host 127.0.0.1 --port 8000

# Terminal 2: Run nginx on 8080 (proxy to 8000)
sudo nginx -c /path/to/factory/nginx-dev.conf
```

Now access via **http://localhost:8080** (simulates production proxy).

## HTTP Basic Auth (Optional)

Enable authentication by setting environment variable:

```bash
# Enable auth
HTTP_AUTH='username:password' uv run python -m uvicorn src.main:app --port 8000

# With systemd
# Add to ~/.config/systemd/user/fastapi_app.service:
# Environment=HTTP_AUTH=username:password
```

## Production Deployment

```bash
# Install service (one-time)
mkdir -p ~/.config/systemd/user
cp factory/fastapi_app.service ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable fastapi_app.service

# Start service
systemctl --user start fastapi_app.service

# View logs
journalctl --user -u fastapi_app.service -f
```

## Architecture

```
┌─────────────────────────────────────────────┐
│           WATCHDOG (APScheduler)            │
│  - Runs 24/7                                │
│  - Checks every 60s                         │
│  - Auto start/stop based on schedule        │
└─────────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────┐
│              LOGIC APP                       │
│  - Starts only when watchdog allows          │
│  - Runs trading logic                        │
│  - Stops gracefully when triggered           │
└─────────────────────────────────────────────┘
```

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | Main page (sleeping or logic) |
| `/logic` | GET | Trading dashboard |
| `/api/schedule` | GET | Schedule info |
| `/api/logic/status` | GET | Logic running state |
| `/api/logic/start` | POST | Start logic |
| `/api/logic/stop` | POST | Stop logic |
| `/api/logic/data` | GET | Trading data (when running) |
| `/api/admin/logs` | GET | Application logs |

## Configuration

Edit `src/main.py` to change schedule:

```python
self.start_hour = 9
self.start_minute = 14
self.end_hour = 23
self.end_minute = 59
self.trading_days = [0, 1, 2, 3, 4]  # Mon-Fri
```

## Requirements

- Python 3.10+
- uv (package manager)

Install: `uv sync --python 3.10`

## Files

```
├── src/
│   ├── main.py          # Watchdog + controller
│   └── logic_app.py     # Trading logic component
├── templates/
│   ├── sleeping.html    # Sleep page (when stopped)
│   └── logic.html       # Trading dashboard (when running)
├── factory/
│   ├── fastapi_app.service  # Systemd template
│   └── nginx-dev.conf       # Nginx proxy config (dev)
├── tests/               # pytest tests
├── scripts/             # Utility scripts
├── data/                # Log files (gitignored)
├── pyproject.toml
└── AGENTS.md            # Development instructions
```

## Logs

Application logs are written to `data/log.txt`.

View: `tail -f data/log.txt`

## License

MIT