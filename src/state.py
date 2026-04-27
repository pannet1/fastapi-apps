# Core state management for logic app
# This module is shared between main.py and logic_app.py
# Background jobs access this directly, requests access via request.app.state.logic

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, Any


@dataclass
class LogicState:
    running: bool = False
    started_at: Optional[datetime] = None
    startup_data: Optional[dict] = None  # Config: api_key, account_id, session_id
    app_data: Optional[dict] = None  # Runtime: positions, orders, cache (cleared on stop)
    ws_client: Optional[Any] = None  # Websocket client
    background_task: Optional[Any] = None  # Async task
    paused: bool = False
    pause_until: Optional[datetime] = None
    pause_reason: str = ''
    
    def is_running(self) -> bool:
        # Running means: running flag is True AND not paused
        # Note: background_task completion is checked separately in start/stop
        if not self.running:
            return False
        if self.paused:
            return False
        if self.pause_until and datetime.now() > self.pause_until:
            self.paused = False
            self.pause_until = None
        return True
    
    def is_paused(self) -> bool:
        if not self.paused:
            return False
        if self.pause_until and datetime.now() > self.pause_until:
            self.paused = False
            self.pause_until = None
            return False
        return True


# Singleton instance - accessible from background jobs
_logic_state = LogicState()


def get_logic_state() -> LogicState:
    return _logic_state