# FastAPI Watchdog App - Development Guide

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                 WATCHDOG (main.py)                         │
│  - APScheduler with IntervalTrigger(60s)                   │
│  - Auto start/stop logic based on schedule                 │
│  - Accesses logic state via request.app.state.logic         │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                 LOGIC APP (logic_app.py)                   │
│  - Stores state in request.app.state.logic                  │
│  - No changes needed to existing app!                      │
│  - Just use request.app.state.logic in routes              │
└─────────────────────────────────────────────────────────────┘
```

## Principle: Zero Changes to Logic App

**Only additions allowed, no modifications to existing logic app code.**

The main app adapts to whatever logic app is provided.

## State Access Pattern

### For Logic App Routes (No Changes)

```python
# In your existing logic app, just use:
@app.get('/status')
async def status(request: Request):
    state = request.app.state.logic
    return {'running': state.running}
```

### For Main App (Additions Only)

```python
# In main.py lifespan, expose state from logic app
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Get reference to logic app's state
    # Logic app stores it in app.state.logic (per its own convention)
    pass

# In routes that need logic state:
@app.get('/api/logic/status')
async def status(request: Request):
    # Standard pattern: logic app exposes state as app.state.logic
    return request.app.state.logic
```

## Key Implementation Patterns

### 1. Router Prefix Rule
**DO:** Add prefix only in main app, not in router definition
```python
# logic_app.py
router = APIRouter(tags=['logic'])  # No prefix!

# main.py
app.include_router(logic_router, prefix='/api/logic')  # Prefix here
```

### 2. Async/Await Rules
- If function is async, use `await`
- If function is sync, don't use `await`
- `asyncio.wait_for()` raises `asyncio.TimeoutError`, NOT `builtins.TimeoutError`

```python
# Wrong
def start_logic():
    return {...}

# Correct
async def start_logic():
    return {...}

# Wrong exception handling
except TimeoutError:
    pass

# Correct
except asyncio.TimeoutError:
    pass
```

### 3. Graceful Shutdown
```python
async def stop_logic():
    _logic_state.running = False
    if _logic_state.ws_client:
        await _logic_state.ws_client.disconnect()
    if _logic_state.background_task:
        _logic_state.background_task.cancel()
        try:
            await _logic_state.background_task
        except asyncio.CancelledError:
            pass
```

### 4. State Management
- `startup_data`: Config (account_id, session_id) - preserved on restart
- `app_data`: Runtime (positions, orders, cache) - cleared on stop

### 5. PID Lock (Prevent Multiple Instances)
```python
# Check if another instance is running
if LOCK_FILE.exists():
    old_pid = int(LOCK_FILE.read_text())
    try:
        os.kill(old_pid, 0)  # Process exists
        sys.exit(1)  # Exit, another instance running
    except OSError:
        pass  # Stale lock, can proceed
```

## Common Pitfalls

### asyncio.TimeoutError vs built-in TimeoutError
```python
# asyncio.wait_for raises asyncio.TimeoutError
except asyncio.TimeoutError:
    pass  # Expected: no data in queue
```

### Clear Pycache After Changes
```bash
find . -name '__pycache__' -exec rm -rf {} +
```

### Log File Path
```python
# Use dynamic path, not hardcoded
log_path = Path(__file__).parent.parent / 'data' / 'log.txt'
```

## File Structure

```
├── src/
│   ├── main.py           # Watchdog + controller
│   ├── logic_app.py      # Logic app (no changes needed)
│   └── state.py          # Optional: shared state module
├── templates/
│   ├── sleeping.html    # Sleep page
│   └── logic.html       # Trading page
├── factory/
│   ├── fastapi_app.service   # Systemd template
│   └── nginx-dev.conf        # Nginx config
├── tests/
├── pyproject.toml
├── README.md
└── AGENTS.md
```

## Testing Checklist

- [ ] Only ONE uvicorn: `ps aux | grep uvicorn | grep -v grep | wc -l`
- [ ] Schedule works: `curl -s /api/schedule`
- [ ] Start/stop logic: `curl -X POST /api/logic/start`
- [ ] Logs endpoint: `curl -s /api/admin/logs`
- [ ] No spurious errors after 10+ seconds
- [ ] New session on each start (check logs for `[BROKER]`)

## Environment Variables

| Variable | Purpose |
|----------|---------|
| `HTTP_AUTH` | HTTP Basic Auth (format: `user:pass`) |
| `SKIP_PID_LOCK` | Skip PID lock for testing (`1` to skip) |

## Commands

```bash
# Setup
uv sync --python 3.10

# Run
uv run python -m uvicorn src.main:app --port 8000

# Test
uv run pytest tests/ -v

# Systemd
cp factory/fastapi_app.service ~/.config/systemd/user/
systemctl --user enable --now fastapi_app.service
```

## Milestones

| Tag | Description |
|-----|-------------|
| `v1.0.0-standalone` | Original standalone pattern with _logic_state singleton |
| `milestone-standalone-logic_state` | Branch backup |
| `main` | Refactored to use `request.app.state.logic` (minimal changes) |