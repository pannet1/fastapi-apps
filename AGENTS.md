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
│   ├── sleeping.html     # Main page (settings, logs, schedule info)
│   └── logic.html        # Trading page (P&L, positions, market data)
├── requirements.txt
├── AGENTS.md             # This file
└── server.log            # Application logs
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

## Pause Mechanism

**Trigger:** User clicks Settings or Save button

**Effect:**
1. Logic app stops gracefully
2. `_logic_state.paused = True`
3. `_logic_state.pause_until = datetime.now() + timedelta(seconds=60)`
4. `is_within_schedule()` returns `False` (because paused)
5. Watchdog does NOT restart logic during pause

**After countdown:**
1. `is_paused()` returns `False`
2. `is_within_schedule()` returns `True` (if within market hours)
3. Watchdog starts logic

## Testing Checklist

- [ ] Only ONE uvicorn process: `ps aux | grep uvicorn | grep -v grep | wc -l`
- [ ] Schedule shows correct times: `curl -s /api/schedule`
- [ ] Start logic manually: `curl -X POST /api/logic/start`
- [ ] Stop logic: `curl -X POST /api/logic/stop`
- [ ] Pause triggers countdown: `curl -X POST '/api/logic/pause?reason=settings&duration=10'`
- [ ] After pause, watchdog auto-starts: wait 70s, check `/api/logic/status`
- [ ] Settings button opens modal
- [ ] Logs button opens modal
- [ ] Browser shows correct page based on state

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