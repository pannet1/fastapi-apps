"""Main Controller App - Shows different UI based on logic app state.

Includes APScheduler for auto start/stop within scheduled hours.
The logic app remains unaware of the schedule - only the controller manages it.
"""

import gc
import sys
from contextlib import asynccontextmanager
from datetime import datetime

from fastapi import FastAPI
from fastapi.responses import HTMLResponse, RedirectResponse
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from src.logic_app import (
    create_logic_router,
    start_logic,
    stop_logic,
    _logic_state,
    load_template,
)

# ============================================================
# Schedule Configuration (in controller only)
# ============================================================


class ScheduleConfig:
    """Schedule configuration for auto start/stop - controller only."""

    def __init__(self):
        self.enabled = True
        # Indian market hours: 9:14 AM to 3:31 PM
        self.start_hour = 9
        self.start_minute = 14
        self.end_hour = 15
        self.end_minute = 31

    def is_within_schedule(self) -> bool:
        """Check if current time is within scheduled hours."""
        if not self.enabled:
            return True

        now = datetime.now()
        current_minutes = now.hour * 60 + now.minute
        start_minutes = self.start_hour * 60 + self.start_minute
        end_minutes = self.end_hour * 60 + self.end_minute

        return start_minutes <= current_minutes < end_minutes

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
    if not _logic_state.is_running() and schedule_config.is_within_schedule():
        await start_logic()


async def scheduled_stop():
    """Auto-stop logic at scheduled end time."""
    if _logic_state.is_running():
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
    pass


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    await on_startup()
    
    # Setup scheduler
    if schedule_config.enabled:
        scheduler.add_job(
            scheduled_start,
            trigger=CronTrigger(
                hour=schedule_config.start_hour, minute=schedule_config.start_minute
            ),
            id="scheduled_start",
        )
        scheduler.add_job(
            scheduled_stop,
            trigger=CronTrigger(
                hour=schedule_config.end_hour, minute=schedule_config.end_minute
            ),
            id="scheduled_stop",
        )
        scheduler.start()

        # Check if should auto-stop on startup (outside schedule)
        if _logic_state.is_running() and not schedule_config.is_within_schedule():
            await stop_logic()

    yield

    # Shutdown
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
# Routes
# ============================================================


@app.get("/", response_class=HTMLResponse)
async def root():
    """Show controller UI when stopped, logic app UI when running."""
    if _logic_state.is_running() and schedule_config.is_within_schedule():
        return HTMLResponse(load_template("logic"))
    return HTMLResponse(load_template("controller"))


@app.get("/logic", response_class=HTMLResponse)
async def logic_page():
    """Dedicated logic app page."""
    return HTMLResponse(load_template("logic"))


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

