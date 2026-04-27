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

## UI Requirements

### CSS Variables (Shared)

```css
:root {
  --bg-gradient: linear-gradient(135deg, #1a1a2e 0%, #16213e 50%, #0f3460 100%);
  --header-bg: rgba(0,0,0,0.3);
  --card-bg: rgba(255,255,255,0.05);
  --accent-green: #00ff88;
  --accent-red: #ff4757;
  --accent-blue: #00d9ff;
  --text-muted: #6b7280;
}

body {
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
  background: var(--bg-gradient);
  color: #eaeaea;
}

.icon-btn {
  background: rgba(255,255,255,0.1);
  border: none;
  padding: 0.5rem;
  border-radius: 8px;
  cursor: pointer;
  font-size: 1.2rem;
}
.icon-btn:hover {
  background: rgba(255,255,255,0.2);
  transform: scale(1.05);
}

.modal-overlay {
  position: fixed;
  top: 0; left: 0; right: 0; bottom: 0;
  background: rgba(0,0,0,0.8);
  display: none;
  align-items: center;
  justify-content: center;
  z-index: 1000;
}

.countdown-time {
  font-size: 2.5rem;
  font-weight: 700;
  color: #00d9ff;
  font-family: monospace;
}
```

### Common Layout (All Pages)

**Header:**
```html
<header class='app-header'>
  <div class='header-left'>
    <span class='logo'>📈</span>
    <span class='title'>Trading Bot</span>
  </div>
  <div class='header-right'>
    <button class='icon-btn' onclick='openSettingsModal()'>⚙️</button>
    <button class='icon-btn' onclick='restartLogic()'>🔄</button> <!-- Logic page only -->
    <button class='icon-btn' onclick='openLogsModal()'>📋</button>
  </div>
</header>
```

**Footer:**
```html
<footer class='app-footer'>
  Made with ❤️ by <a href='https://ecomsense.in'>ecomsense.in</a>
</footer>
```

### Sleeping Page (When Stopped/Outside Schedule)

**Content:**
- Rotating emoji memes (😴💤🥱😎☕🌙)
- Funny trading quotes (rotating every 8s)
- Live countdown to market open (HH:MM:SS)
- Schedule info card (Opens/Closes)
- Trading days badges (Mon-Fri, today highlighted)

**No:** Status indicator, time in footer, Start/Stop button

### Logic Page (When Running/Within Schedule)

**Content:**
- P&L card (₹X, green/red)
- Trade count
- Active positions
- Account ID
- Market data with prices/volumes

**Header Buttons:**
- ⚙️ Settings (opens modal, no restart)
- 🔄 Restart (stop → start → reload)
- 📋 Logs (opens modal)

### Modals (Common)

**Settings Modal:**
```html
<div id='settingsModal' class='modal-overlay'>
  <div class='modal-content'>
    <div class='modal-header'>
      <span>⚙️ Settings</span>
      <button onclick='closeSettingsModal()'>×</button>
    </div>
    <input id='apiKey' placeholder='API Key'>
    <input id='maxPosition' placeholder='Max Position'>
    <input id='stopLoss' placeholder='Stop Loss %'>
    <button onclick='saveAndRestart()'>Save & Restart</button> <!-- Logic page -->
    <button onclick='saveSettings()'>Save Settings</button> <!-- Sleeping page -->
  </div>
</div>
```

**Logs Modal:**
```html
<div id='logsModal' class='modal-overlay'>
  <div class='modal-content'>
    <div class='log-content' id='logContent'>Loading...</div>
    <button onclick='refreshLogs()'>Refresh</button>
  </div>
</div>
```

### JavaScript Pattern

```javascript
// Modal functions (reuse across pages)
function openSettingsModal() { ... }
function closeSettingsModal() { ... }
function openLogsModal() { ... }
function closeLogsModal() { ... }
async function refreshLogs() {
  const resp = await fetch('/api/admin/logs');
  document.getElementById('logContent').textContent = resp.content;
}

// Settings: Save only, no countdown
async function saveSettings() {
  closeSettingsModal();
  await fetch('/api/logic/stop', {method:'POST'});
}

// Restart
async function restartLogic() {
  await fetch('/api/logic/stop', {method:'POST'});
  await new Promise(r => setTimeout(r, 500));
  await fetch('/api/logic/start', {method:'POST'});
  location.reload();
}
```

## Milestones

| Tag | Description |
|-----|-------------|
| `v1.0.0-standalone` | Original standalone pattern with _logic_state singleton |
| `milestone-standalone-logic_state` | Branch backup |
| `main` | Refactored to use `request.app.state.logic` (minimal changes) |