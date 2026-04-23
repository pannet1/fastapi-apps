# FastAPI Controller Architecture Specification

## Overview
- **Project**: FastAPI app with controller pattern
- **Core functionality**: Main app controls a runnable logic app with start/stop UI
- **Target users**: End users who see a single unified app

## Architecture

### Design Decision: Single Process Pattern
For the apps to "appear as one", the best approach is:
- **logic_app.py**: Exports router and lifecycle functions
- **main.py**: Includes logic_app router + manages lifecycle state

This gives:
- Single port (8000)
- Unified endpoints and UI
- Graceful start/stop control

### File Structure
```
/home/pannet1/py/github/fastapi-apps/
├── main.py          # Controller app with UI
├── logic_app.py     # Logic app (runs independently in same process)
└── SPEC.md        # This file
```

## Functionality Specification

### logic_app.py
- Exports `create_logic_router()` - returns FastAPI router
- Exports `start_logic()` - starts background tasks
- Exports `stop_logic()` - graceful shutdown
- Provides `/api/logic/status` endpoint
- Provides `/api/logic/data` endpoint (sample data)
- Runs background task when started

### main.py
- State management: `logic_running` boolean
- UI: HTML page with Start/Stop button
- Endpoints:
  - `GET /` - UI page
  - `GET /api/logic/start` - Start logic app
  - `GET /api/logic/stop` - Stop logic app gracefully
  - Mounts logic_app router under `/api/logic/`

### Graceful Shutdown Requirements
1. Signal background tasks to stop
2. Wait for in-flight requests to complete
3. Clean up resources
4. Update state

## UI Specification

### Button Behavior
- Show "Start" when logic is stopped
- Show "Stop" when logic is running
- Toggle via API call
- Visual feedback on state change

### Styling
- Clean, modern look
- Clear state indication
- Simple, intuitive

## Acceptance Criteria
- [ ] User visits / and sees UI with button
- [ ] Clicking Start starts logic app, button changes to Stop
- [ ] Clicking Stop gracefully stops logic app, button changes to Start
- [ ] /api/logic/status reflects current state
- [ ] /api/logic/data returns data only when running
- [ ] Graceful shutdown completes without errors
- [ ] Appears as single unified app to end user