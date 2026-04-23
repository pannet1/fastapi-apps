# FastAPI Controller Architecture - Learnings

## Overview

A main FastAPI app controls a logic app with start/stop capability. The logic app runs as a background task and can be started/stopped from the main app's UI.

## Key Learnings

### 1. Router Prefix Issue

**Problem:** Double prefix (`/api/logic/logic/status`)
- Logic router had `prefix="/logic"` 
- Main app added `prefix="/api"` 
- Result: `/api/logic/logic/status`

**Solution:** Remove prefix from logic router, add only in main:
```python
# logic_app.py
router = APIRouter(tags=["logic"])  # No prefix

# main.py
app.include_router(logic_router, prefix="/api/logic")  # Add prefix here
```

### 2. Background Task Crash Fix

**Problem:** App crashes when using `data_queue.empty()` before getting data
- Calling `.empty()` on async queue before getting can cause issues
- Should just block wait on `get()`

**Solution:** Use proper blocking wait with timeout:
```python
async def background_processor(app_data: dict, data_queue: asyncio.Queue):
    while _logic_state.running:
        try:
            # Let the queue block. This yields control back to the event loop.
            data = await asyncio.wait_for(data_queue.get(), timeout=0.5)
            # Process data...
        except TimeoutError:
            # Expected behavior if no data arrives within 0.5s. Just loop again.
            pass
        except asyncio.CancelledError:
            break
        except Exception as e:
            print(f"Background logic error: {e}")
    app_data.clear()
```

### 3. UI State Switching

**Problem:** Need different UIs for stopped vs running state

**Solution:** Check state in root endpoint:
```python
@app.get("/", response_class=HTMLResponse)
async def root():
    if _logic_state.is_running():
        return HTMLResponse(LOGIC_APP_HTML)
    return HTMLResponse(CONTROLLER_HTML)
```

### 4. Order Model Issue

**Problem:** Pydantic `Order` model causing issues in background task

**Solution:** Use plain dict instead:
```python
order = {
    "id": str(uuid.uuid4())[:8].upper(),
    "symbol": symbol,
    "side": side,
    ...
}
app_data["orders"].append(order)
```

### 5. Graceful Shutdown Pattern

```python
async def stop_logic():
    _logic_state.running = False
    
    # Stop websocket
    if _logic_state.ws_client:
        await _logic_state.ws_client.disconnect()
    
    # Clear app data (frees memory)
    if _logic_state.app_data:
        _logic_state.app_data.clear()
    
    # Cancel background task
    if _logic_state.background_task:
        _logic_state.background_task.cancel()
        try:
            await _logic_state.background_task
        except asyncio.CancelledError:
            pass
    
    return {"status": "stopped", "message": "Logic app stopped gracefully"}
```

## File Structure

```
project/
├── main.py          # Controller app (main entry point)
├── logic_app.py       # Logic app (runs when started)
├── requirements.txt  # Python dependencies
├── .gitignore        # Standard Python gitignore
└── .venv/            # Virtual environment
```

## Key Patterns

1. **State Management:** Global `_logic_state` singleton
2. **Startup Data:** Initialized at start, preserved (API keys, account ID)
3. **App Data:** Created at start, cleared on stop (positions, orders, market cache)
4. **WebSocket Client:** Fake client generates simulated market data
5. **UI Switching:** Different HTML based on running state

## Testing Endpoints

```bash
# Status
curl http://127.0.0.1:8000/api/logic/status

# Start
curl -X POST http://127.0.0.1:8000/api/logic/start

# Data (only when running)
curl http://127.0.0.1:8000/api/logic/data

# Stop
curl -X POST http://127.0.0.1:8000/api/logic/stop

# Memory
curl http://127.0.0.1:8000/api/memory
```

## Notes

- `app_data.clear()` frees memory on stop
- Background task properly handles cancellation
- Error logging in except block helps debugging
- TimeoutError is expected (no data in queue)