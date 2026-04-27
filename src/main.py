"""Main Controller App - Shows different UI based on logic app state.

Includes APScheduler for auto start/stop within scheduled hours.
The logic app remains unaware of the schedule - only the controller manages it.

Architecture:
- Watchdog (main.py): Runs 24/7, manages logic app lifecycle
- Logic app: Starts/stops based on schedule + user actions
"""

import gc
import logging
import os
import signal
import sys
from base64 import b64decode
from contextlib import asynccontextmanager
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

# Configure logging
log_dir = Path(__file__).parent.parent / 'data'
log_dir.mkdir(exist_ok=True)
log_file = log_dir / 'log.txt'

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_file),
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger(__name__)

# ============================================================
# PID Lock File - Prevent Multiple Instances
# ============================================================

LOCK_FILE = Path(__file__).parent.parent / 'data' / 'app.pid'

def check_pid_lock() -> bool:
    """Check if another instance is running. Returns True if can proceed."""
    if not LOCK_FILE.exists():
        return True
    
    try:
        old_pid = int(LOCK_FILE.read_text().strip())
        # Check if process exists
        try:
            os.kill(old_pid, 0)  # Signal 0 just checks if process exists
            logger.error(f"Another instance is running (PID: {old_pid}). Exiting.")
            return False
        except OSError:
            # Process doesn't exist, stale lock file - can proceed
            logger.info(f"Stale lock file found (PID: {old_pid}). Proceeding.")
            return True
    except (ValueError, IOError):
        # Invalid lock file, can proceed
        return True

def acquire_pid_lock() -> None:
    """Write current PID to lock file."""
    LOCK_FILE.write_text(str(os.getpid()))
    logger.info(f"PID lock acquired: {os.getpid()}")

def release_pid_lock() -> None:
    """Remove lock file on shutdown."""
    if LOCK_FILE.exists():
        try:
            current_pid = int(LOCK_FILE.read_text().strip())
            if current_pid == os.getpid():
                LOCK_FILE.unlink()
                logger.info("PID lock released")
        except (ValueError, IOError):
            pass

# For testing: skip lock check if we're being imported
# Set SKIP_PID_LOCK=1 to disable lock (for testing)
_is_lock_enabled = os.environ.get('SKIP_PID_LOCK', '') != '1'

# HTTP Basic Auth (set via environment for security)
def get_auth_credentials() -> Optional[tuple[str, str]]:
    """Get credentials from environment. Returns (username, password) or None."""
    import os
    auth = os.environ.get('HTTP_AUTH', '')
    if not auth:
        return None
    try:
        username, password = auth.split(':', 1)
        return (username, password)
    except ValueError:
        return None

def verify_basic_auth(request) -> bool:
    """Verify Basic Auth header. Returns True if authenticated or auth disabled."""
    credentials = get_auth_credentials()
    if credentials is None:
        return True  # Auth disabled
    
    auth_header = request.headers.get('Authorization', '')
    if not auth_header.startswith('Basic '):
        return False
    
    try:
        encoded = auth_header[6:]
        decoded = b64decode(encoded).decode('utf-8')
        provided_user, provided_pass = decoded.split(':', 1)
        return provided_user == credentials[0] and provided_pass == credentials[1]
    except Exception:
        return False

from src.logic_app import (
    create_logic_router,
    start_logic,
    stop_logic,
    _logic_state,
    load_template,
)


# ============================================================
# Template Loader with Header/Footer
# ============================================================

def load_page_template(name: str) -> str:
    templates_dir = Path(__file__).parent.parent / 'templates'
    template_path = templates_dir / f'{name}.html'
    return template_path.read_text()

# ============================================================
# Schedule Configuration (in controller only)
# ============================================================


class ScheduleConfig:
    """Schedule configuration for auto start/stop - controller only."""

    def __init__(self):
        self.enabled = True
        # Schedule: 9:14 AM to 11:59 PM
        self.start_hour = 9
        self.start_minute = 14
        self.end_hour = 23
        self.end_minute = 59
        # Trading days (0=Monday, 4=Friday for Indian market)
        self.trading_days = [0, 1, 2, 3, 4]
        self.trading_day_names = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri']

    def is_within_schedule(self) -> bool:
        if not self.enabled:
            return True

        if _logic_state.is_paused():
            return False

        now = datetime.now()
        if now.weekday() not in self.trading_days:
            return False

        current_minutes = now.hour * 60 + now.minute
        start_minutes = self.start_hour * 60 + self.start_minute
        end_minutes = self.end_hour * 60 + self.end_minute

        return start_minutes <= current_minutes < end_minutes

    def is_paused(self) -> bool:
        """Check if logic is paused (user action)."""
        return _logic_state.is_paused()

    def pause_reason(self) -> str:
        """Get current pause reason."""
        if _logic_state.paused and _logic_state.pause_until:
            remaining = (_logic_state.pause_until - datetime.now()).total_seconds()
            if remaining > 0:
                return f"{_logic_state.pause_reason} ({int(remaining)}s)"
        return ""

    def can_start(self) -> bool:
        """Check if logic can be started."""
        return self.is_within_schedule() and not _logic_state.is_running()


    def time_until_start(self) -> str:
        """Return time until schedule starts."""
        if not self.enabled or self.is_within_schedule():
            return "now"

        now = datetime.now()
        start_minutes = self.start_hour * 60 + self.start_minute
        current_minutes = now.hour * 60 + now.minute
        mins_until = start_minutes - current_minutes

        if mins_until < 0:
            mins_until += 1440  # Tomorrow

        hours = mins_until // 60
        mins = mins_until % 60

        if hours > 0:
            return f"{hours}h {mins}m"
        return f"{mins}m"

    def time_until_end(self) -> str:
        """Return time until schedule ends."""
        if not self.enabled or not self.is_within_schedule():
            return "outside"

        now = datetime.now()
        end_minutes = self.end_hour * 60 + self.end_minute
        current_minutes = now.hour * 60 + now.minute
        mins_until = end_minutes - current_minutes

        if mins_until <= 0:
            return "now"

        hours = mins_until // 60
        mins = mins_until % 60

        if hours > 0:
            return f"{hours}h {mins}m"
        return f"{mins}m"


schedule_config = ScheduleConfig()
scheduler = AsyncIOScheduler()


# ============================================================
# Scheduler Jobs
# ============================================================


async def scheduled_start():
    """Auto-start logic at scheduled time."""
    if schedule_config.can_start():
        await start_logic()


async def scheduled_stop():
    if _logic_state.is_running() and not schedule_config.is_within_schedule():
        await stop_logic()


async def watchdog_check():
    if schedule_config.is_within_schedule() and not _logic_state.is_running():
        await start_logic()
    elif not schedule_config.is_within_schedule() and _logic_state.is_running():
        await stop_logic()


# ============================================================
# Memory Tracking
# ============================================================


def get_memory_usage() -> dict:
    gc.collect()
    logic_size = sys.getsizeof(_logic_state)
    startup_size = sys.getsizeof(_logic_state.startup_data)
    app_size = sys.getsizeof(_logic_state.app_data)
    ws_size = sys.getsizeof(_logic_state.ws_client)
    return {
        "logic_state_bytes": logic_size,
        "startup_data_bytes": startup_size or 0,
        "app_data_bytes": app_size or 0,
        "ws_client_bytes": ws_size or 0,
        "total_bytes": (startup_size or 0) + (app_size or 0) + (ws_size or 0),
    }


# ============================================================
# FastAPI App
# ============================================================


# ============================================================
# Lifecycle Hooks
# ============================================================

async def on_startup():
    """Called on server startup."""
    pass


async def on_shutdown():
    """Called on server shutdown."""
    release_pid_lock()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Check PID lock when server starts (skip for testing)
    global _is_lock_enabled
    if _is_lock_enabled:
        if not check_pid_lock():
            logger.error("Another instance is running. Exiting.")
            sys.exit(1)
        acquire_pid_lock()
    
    await on_startup()
    
    if schedule_config.enabled:
        scheduler.add_job(
            watchdog_check,
            trigger=IntervalTrigger(seconds=60),
            id='watchdog_check',
        )
        scheduler.start()

    yield

    if scheduler.running:
        scheduler.shutdown()
    await on_shutdown()


app = FastAPI(
    title="FastAPI Controller",
    description="Control trading logic app with schedule",
    version="1.0.0",
    lifespan=lifespan,
)


# ============================================================
# HTTP Basic Auth Middleware
# ============================================================

@app.middleware('http')
async def auth_middleware(request: Request, call_next):
    if not verify_basic_auth(request):
        return Response(
            content='Unauthorized',
            status_code=401,
            headers={'WWW-Authenticate': 'Basic realm="Restricted"'}
        )
    return await call_next(request)


# ============================================================
# Routes
# ============================================================


@app.get("/", response_class=HTMLResponse)
async def root():
    """Show sleeping page when stopped/paused, logic app when running."""
    if _logic_state.is_running() and schedule_config.is_within_schedule():
        return HTMLResponse(load_page_template("logic"))
    return HTMLResponse(load_page_template("sleeping"))


@app.get("/logic", response_class=HTMLResponse)
async def logic_page():
    """Dedicated logic app page."""
    if _logic_state.is_running() and schedule_config.is_within_schedule():
        return HTMLResponse(load_page_template("logic"))
    return HTMLResponse(load_page_template("sleeping"))


@app.get("/api/memory")
async def memory_info():
    memory = get_memory_usage()
    return {
        "running": _logic_state.running,
        "has_startup_data": _logic_state.startup_data is not None,
        "has_app_data": _logic_state.app_data is not None,
        "has_ws_client": _logic_state.ws_client is not None,
        "schedule_enabled": schedule_config.enabled,
        "within_schedule": schedule_config.is_within_schedule(),
        "time_until_end": schedule_config.time_until_end(),
        **memory,
    }


@app.get("/api/schedule")
async def schedule_info():
    """Get schedule information."""
    return {
        "enabled": schedule_config.enabled,
        "start_time": f"{schedule_config.start_hour:02d}:{schedule_config.start_minute:02d}",
        "end_time": f"{schedule_config.end_hour:02d}:{schedule_config.end_minute:02d}",
        "within_schedule": schedule_config.is_within_schedule(),
        "time_until_start": schedule_config.time_until_start(),
        "time_until_end": schedule_config.time_until_end(),
        "running": _logic_state.is_running(),
        "paused": schedule_config.is_paused(),
        "pause_reason": schedule_config.pause_reason(),
        "schedule_times": f"{schedule_config.start_hour:02d}:{schedule_config.start_minute:02d} - {schedule_config.end_hour:02d}:{schedule_config.end_minute:02d}",
        "trading_days": schedule_config.trading_day_names,
    }


# Legacy redirect for /home
@app.get("/home", response_class=RedirectResponse)
async def home_redirect():
    return RedirectResponse("/")


# Mount logic app
logic_router = create_logic_router()
app.include_router(logic_router, prefix="/api/logic")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)



@app.get('/api/admin/logs')
async def get_logs():
    try:
        log_path = Path(__file__).parent.parent / 'data' / 'log.txt'
        if log_path.exists():
            content = log_path.read_text()[-5000:]  # Last 5000 chars
        else:
            content = 'No logs found'
        return {'content': content, 'status': 'ok'}
    except Exception as e:
        return {'content': f'Error: {e}', 'status': 'error'}
