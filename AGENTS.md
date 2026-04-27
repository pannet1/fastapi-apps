# FastAPI Watchdog PoC - Project AGENTS.md

## Project Overview

This is a **Proof of Concept** for a trading bot system with two components:

| Component | Description | Runs |
|-----------|-------------|------|
| **Watchdog (main.py)** | APScheduler watchdog, runs 24/7, manages logic lifecycle | Always (systemd) |
| **Logic App** | Trading logic - starts/stops based on schedule + user actions | Only during market hours |

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                 WATCHDOG (systemd --user)                   │
│  - APScheduler with IntervalTrigger(60s)                   │
│  - Checks: within_schedule AND not paused → start logic    │
│  - Checks: outside schedule OR paused → stop logic         │
│  - Runs 24/7, never restarts logic itself                  │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                    LOGIC APP                                │
│  - Starts only when watchdog allows                        │
│  - Stops gracefully when watchdog stops                    │
│  - Broker token refresh happens on restart                 │
│  - Settings changes trigger stop → load → start            │
└─────────────────────────────────────────────────────────────┘
```

## User-Facing Pages

| Page | Trigger | Shows |
|------|---------|-------|
| **Sleeping Page** | Logic stopped OR outside schedule | Schedule info, Settings button, Logs button |
| **Logic Page** | Logic running AND within schedule | Trading dashboard |
| **Pause Overlay** | Settings/Save pressed | Countdown timer |

## Flow Examples

### 1. Market Hours - Logic Running
```
within_schedule=true, paused=false, running=true → Logic Page shown
```

### 2. User Presses Settings
```
Settings clicked → pause triggered (60s) → Logic stops
→ Page shows pause overlay with countdown
→ After countdown, watchdog sees within_schedule=true → auto-starts logic
```

### 3. Outside Market Hours
```
within_schedule=false → Sleeping Page shown
→ Watchdog keeps checking every 60s
→ When market opens (9:14), watchdog starts logic
```

## Schedule Configuration

```python
class ScheduleConfig:
    enabled = True
    start_hour = 9
    start_minute = 14
    end_hour = 23
    end_minute = 59
    trading_days = [0, 1, 2, 3, 4]  # Mon-Fri
```

## DO's and DON'Ts

### DO
- Use `systemd --user` for managing the watchdog (not systemctl in production)
- Use APScheduler (not cron/systemd timers) for schedule management
- Start server manually for testing: `.venv/bin/python -m uvicorn src.main:app --host 127.0.0.1 --port 8000`
- Test API directly with curl before testing in browser
- Always check for single uvicorn: `ps aux | grep uvicorn | grep -v grep`
- Use `uv` for Python package management

### DON'T
- **NEVER use `systemctl` (root)** - causes multiple uvicorn processes
- **NEVER use `print()`** - use logging instead
- **NEVER use MKT/MARKET order type** - use LIMIT with slippage
- Don't test stock-brokers package locally - only login allowed from registered IP
- Don't commit without running: `python3 -m py_compile src/main.py src/logic_app.py`

## Server Management Commands

### Local Development
```bash
# Start
cd /home/pannet1/py/github.com/pannet1/fastapi-apps
.venv/bin/python -m uvicorn src.main:app --host 127.0.0.1 --port 8000

# Test API
curl -s http://127.0.0.1:8000/api/schedule
curl -s http://127.0.0.1:8000/api/logic/status
curl -X POST http://127.0.0.1:8000/api/logic/start
curl -X POST http://127.0.0.1:8000/api/logic/stop
curl -X POST 'http://127.0.0.1:8000/api/logic/pause?reason=settings&duration=60'
```

### Server Deployment (SSH)
```bash
# Kill existing
ssh uma@65.20.83.178 'pkill -f uvicorn'

# Start fresh
ssh uma@65.20.83.178 'cd /path/to/project && .venv/bin/python -m uvicorn src.main:app --host 127.0.0.1 --port 8000 &'
```

### Systemd User Service (For Production)
```ini
# ~/.config/systemd/user/fastapi-watchdog.service
[Unit]
Description=FastAPI Watchdog Service
After=network.target

[Service]
Type=simple
WorkingDirectory=/home/pannet1/py/github.com/pannet1/fastapi-apps
ExecStart=/home/pannet1/py/github.com/pannet1/fastapi-apps/.venv/bin/python -m uvicorn src.main:app --host 127.0.0.1 --port 8000
Restart=on-failure
RestartSec=5

[Install]
WantedBy=default.target
```

```bash
# Enable and start
systemctl --user daemon-reload
systemctl --user enable fastapi-watchdog.service
systemctl --user start fastapi-watchdog.service
systemctl --user status fastapi-watchdog.service
```

## Files Structure

```
fastapi-apps/
├── src/
│   ├── main.py           # Watchdog app (APScheduler, routes)
│   └── logic_app.py      # Logic app (start/stop, state)
├── templates/
│   ├── sleeping.html     # Sleep page (countdown, memes, schedule)
│   └── logic.html        # Trading page (P&L, positions, market data)
├── factory/
│   ├── fastapi_app.service   # Systemd service template
│   └── nginx-dev.conf        # Nginx proxy config (dev)
├── tests/                # pytest tests
├── data/                 # Log files (gitignored)
├── pyproject.toml        # Dependencies (uv)
└── AGENTS.md             # This file
```

## Key Endpoints

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/` | GET | Main page (sleeping or logic based on state) |
| `/logic` | GET | Trading page |
| `/api/schedule` | GET | Schedule info, times, trading days |
| `/api/logic/status` | GET | Logic running state |
| `/api/logic/start` | POST | Start logic app |
| `/api/logic/stop` | POST | Stop logic app |
| `/api/logic/pause` | POST | Trigger pause (stops logic, prevents auto-start) |
| `/api/admin/logs` | GET | Get server logs |
| `/api/memory` | GET | Memory usage info |

## Current State (As of 2026-04-27)

- **Schedule:** 09:14 - 23:59, Mon-Fri
- **Watchdog interval:** 60 seconds
- **Pause duration:** 60 seconds
- **Server port:** 8000
- **Single uvicorn:** Verified

## Key Implementation Patterns

### 1. Router Prefix Rule
**DO:** Add prefix only in main app, not in router definition
```python
# logic_app.py
router = APIRouter(tags=["logic"])  # No prefix!

# main.py
app.include_router(logic_router, prefix="/api/logic")  # Prefix here
```
**DON'T:** Double prefix causes `/api/logic/logic/status`

### 2. Background Task with Queue
**DO:** Use `asyncio.wait_for` with timeout
```python
async def background_processor(app_data, data_queue):
    while _logic_state.running:
        try:
            data = await asyncio.wait_for(data_queue.get(), timeout=0.5)
            # Process data...
        except TimeoutError:
            pass  # Expected: no data in queue, loop again
        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.error(f"Background logic error: {e}")
```
**DON'T:** Use `data_queue.empty()` before get - causes issues

### 3. Graceful Shutdown Sequence
```python
async def stop_logic():
    _logic_state.running = False
    if _logic_state.ws_client:
        await _logic_state.ws_client.disconnect()
    if _logic_state.app_data:
        _logic_state.app_data.clear()  # Frees memory
    if _logic_state.background_task:
        _logic_state.background_task.cancel()
        try:
            await _logic_state.background_task
        except asyncio.CancelledError:
            pass
```

### 4. Data Models
**Use plain dict** for high-frequency data (orders, positions) - faster than Pydantic
```python
order = {
    "id": str(uuid.uuid4())[:8].upper(),
    "symbol": symbol,
    "side": side,
    ...
}
app_data["orders"].append(order)
```

### 5. State Management
- `startup_data`: Initialized at start, preserved (API keys, config)
- `app_data`: Created at start, cleared on stop (positions, orders, cache)

## Common Pitfalls & Debugging

### Async/Await Bugs

**Symptom:** `TypeError: object dict can't be used in 'await' expression`

**Cause:** Function is sync but called with `await`

**Fix:** Make function async
```python
# Wrong
def start_logic():
    return {"status": "started", ...}

# Correct
async def start_logic():
    return {"status": "started", ...}
```

### asyncio.TimeoutError vs built-in TimeoutError

**Symptom:** Spurious `Background logic error: TimeoutError:` every 0.5s

**Cause:** `asyncio.wait_for()` raises `asyncio.TimeoutError`, NOT `builtins.TimeoutError`

**Fix:**
```python
# Wrong
except TimeoutError:
    pass

# Correct
except asyncio.TimeoutError:
    pass
```

### Clear Pycache After Code Changes

**Symptom:** Changes don't take effect, old errors persist

**Fix:**
```bash
find . -name '__pycache__' -exec rm -rf {} +
find . -name '*.pyc' -delete
```

### Log File Path Issues

**Symptom:** Logs show "No server.log found" even though logs exist

**Cause:** Hardcoded path to wrong file

**Fix:** Use dynamic path relative to project root
```python
# Wrong
log_path = Path(__file__).parent.parent / 'server.log'

# Correct
log_path = Path(__file__).parent.parent / 'data' / 'log.txt'
```

### systemd Multi-Instance Issue

**Symptom:** Multiple uvicorn processes running

**Causes:**
1. Service crashes and systemd restarts it
2. Manual start while service is already running
3. Missing lock mechanism

**Debug:**
```bash
ps aux | grep uvicorn | grep -v grep
systemctl --user status fastapi_app.service
journalctl --user -u fastapi_app.service -n 50
```

**Fix:** App has built-in PID lock file mechanism
```python
# Lock file: data/app.pid
# Auto-created on startup, auto-removed on shutdown
# Checks if another instance is running before starting
```

**To test lock:**
```bash
# Start first
.venv/bin/python -m uvicorn src.main:app --port 8000 &

# Try second (should fail)
.venv/bin/python -m uvicorn src.main:app --port 8001
# Output: "Another instance is running (PID: X). Exiting."
```

**For testing:** Set `SKIP_PID_LOCK=1` environment variable

### HTTP Basic Auth Middleware

**Setup:** Set via environment variable
```bash
export HTTP_AUTH='username:password'
```

**Check:**
```bash
# Without auth (401)
curl http://127.0.0.1:8000/

# With auth (200)
curl -u username:password http://127.0.0.1:8000/
```

### Testing Checklist

- [ ] Only ONE uvicorn process: `ps aux | grep uvicorn | grep -v grep | wc -l`
- [ ] Schedule shows correct times: `curl -s /api/schedule`
- [ ] Start logic manually: `curl -X POST /api/logic/start`
- [ ] Stop logic: `curl -X POST /api/logic/stop`
- [ ] Logs endpoint works: `curl -s /api/admin/logs`
- [ ] Auth works when enabled: `curl -u user:pass /`
- [ ] No spurious errors in logs after 10+ seconds