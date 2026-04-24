"""Logic App - Runnable FastAPI app with simulated trading.

Features:
- Startup data (initialized at start)
- Application data (runtime - cleared on stop)
- Fake websocket client (market data simulation)
"""

import asyncio
import json
import random
import uuid
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel


# ============================================================
# Template Loader
# ============================================================

def load_template(name: str) -> str:
    """Load HTML template from templates folder."""
    template_path = Path(__file__).parent.parent / "templates" / f"{name}.html"
    return template_path.read_text()


# ============================================================
# Data Models
# ============================================================

class Order(BaseModel):
    id: str
    symbol: str
    side: str
    quantity: float
    price: float
    timestamp: str
    status: str = "pending"


class Position(BaseModel):
    symbol: str
    quantity: float
    avg_price: float
    current_price: float
    pnl: float = 0.0


class MarketData(BaseModel):
    symbol: str
    bid: float
    ask: float
    last: float
    volume: float
    timestamp: str


# ============================================================
# Fake Websocket Client
# ============================================================

class FakeWebsocketClient:
    """Simulated websocket for market data."""
    
    def __init__(self, symbols: List[str]):
        self.symbols = symbols
        self.connected = False
        self._task: Optional[asyncio.Task] = None
        self._callbacks: List[asyncio.Queue] = []
        self._base_prices = {s: random.uniform(100, 5000) for s in symbols}
    
    async def connect(self):
        await asyncio.sleep(0.1)
        self.connected = True
    
    async def disconnect(self):
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        self.connected = False
    
    def subscribe(self, callback: asyncio.Queue):
        self._callbacks.append(callback)
    
    def start(self):
        if not self._task:
            self._task = asyncio.create_task(self._receive_data())
    
    async def _receive_data(self):
        while self.connected:
            for symbol in self.symbols:
                change = random.uniform(-0.5, 0.5)
                base = self._base_prices[symbol]
                price = base * (1 + change / 100)
                self._base_prices[symbol] = price
                bid = price - random.uniform(0.1, 1.0)
                ask = price + random.uniform(0.1, 1.0)
                data = MarketData(
                    symbol=symbol,
                    bid=round(bid, 2),
                    ask=round(ask, 2),
                    last=round(price, 2),
                    volume=random.uniform(1000, 100000),
                    timestamp=datetime.now().isoformat(),
                )
                for cb in self._callbacks:
                    await cb.put(data.json())
            await asyncio.sleep(1)


# ============================================================
# Application State
# ============================================================

class LogicState:
    def __init__(self):
        self.running = False
        self.background_task: Optional[asyncio.Task] = None
        self.started_at: Optional[datetime] = None
        self.startup_data: Optional[dict] = None
        self.app_data: Optional[dict] = None
        self.ws_client: Optional[FakeWebsocketClient] = None
    
    def is_running(self) -> bool:
        return self.running and self.background_task is not None and not self.background_task.done()


_logic_state = LogicState()


# ============================================================
# Response Models
# ============================================================

class LogicStatus(BaseModel):
    running: bool
    started_at: Optional[str] = None
    account_id: Optional[str] = None
    active_positions: int = 0
    open_orders: int = 0


class LogicData(BaseModel):
    timestamp: str
    total_pnl: float
    trade_count: int
    positions: List[Position]
    market_data: List[MarketData]


# ============================================================
# Lifecycle Hooks
# ============================================================

def on_start(startup_data: dict):
    """Called when logic app starts."""
    print(f"[LIFECYCLE] on_start called with: {startup_data.get('account_id')}")
    pass


def on_stop(app_data: dict):
    """Called when logic app stops."""
    print(f"[LIFECYCLE] on_stop called")
    pass


# ============================================================
# Background Processor
# ============================================================

async def background_processor(app_data: dict, data_queue: asyncio.Queue):
    while _logic_state.running:
        try:
            # Let the queue block. This yields control back to the event loop.
            data = await asyncio.wait_for(data_queue.get(), timeout=0.5)
            
            market_data = MarketData(**json.loads(data))
            app_data["market_cache"][market_data.symbol] = market_data
            
            if market_data.symbol in app_data["positions"]:
                pos = app_data["positions"][market_data.symbol]
                pos["current_price"] = market_data.last
                pos["pnl"] = (pos["current_price"] - pos["avg_price"]) * pos["quantity"]
            
            app_data["last_update"] = market_data.timestamp
            
            if random.random() < 0.1 and len(app_data["positions"]) < 3:
                symbol = random.choice(list(app_data["market_cache"].keys()))
                side = random.choice(["BUY", "SELL"])
                qty = random.uniform(1, 10)
                order = Order(
                    id=str(uuid.uuid4())[:8].upper(),
                    symbol=symbol,
                    side=side,
                    quantity=round(qty, 2),
                    price=market_data.last,
                    timestamp=datetime.now().isoformat(),
                    status="filled",
                )
                app_data["orders"].append(order)
                app_data["trade_count"] += 1
                
                if symbol in app_data["positions"]:
                    if side == "BUY":
                        app_data["positions"][symbol]["quantity"] += qty
                    else:
                        app_data["positions"][symbol]["quantity"] -= qty
                else:
                    app_data["positions"][symbol] = {
                        "symbol": symbol,
                        "quantity": qty if side == "BUY" else -qty,
                        "avg_price": market_data.last,
                        "current_price": market_data.last,
                        "pnl": 0.0
                    }
                    
            app_data["total_pnl"] = sum(p["pnl"] for p in app_data["positions"].values())
            
        except TimeoutError:
            # Expected behavior if no data arrives within 0.5s. Just loop again.
            pass
        except asyncio.CancelledError:
            break
        except Exception as e:
            # Print the error instead of passing, so you aren't blind to actual logic bugs
            print(f"Background logic error: {e}")
            
    app_data.clear()


def start_logic():
    if _logic_state.is_running():
        return {"status": "already_running", "message": "Logic app is already running"}
    
    # Startup data
    _logic_state.startup_data = {
        "api_key": "fake_api_key_" + str(uuid.uuid4())[:8],
        "account_id": "ACC_" + str(uuid.uuid4())[:6].upper(),
        "strategies": ["momentum", "mean_reversion"],
        "symbols": ["RELIANCE", "TCS", "INFY", "HDFCBANK", "ITC"],
        "max_position_size": 100.0,
        "max_loss_per_trade": 1000.0,
        "stop_loss_pct": 0.5,
    }
    
    # Application data
    _logic_state.app_data = {
        "positions": {},
        "orders": [],
        "market_cache": {},
        "total_pnl": 0.0,
        "trade_count": 0,
        "last_update": None,
    }
    
    # Lifecycle hook
    on_start(_logic_state.startup_data)
    
    # Websocket client
    _logic_state.ws_client = FakeWebsocketClient(_logic_state.startup_data["symbols"])
    _logic_state.running = True
    _logic_state.started_at = datetime.now()
    
    data_queue = asyncio.Queue()
    _logic_state.ws_client._callbacks = [data_queue]
    
    async def run_app():
        await _logic_state.ws_client.connect()
        _logic_state.ws_client.start()
        await background_processor(_logic_state.app_data, data_queue)

    
    _logic_state.background_task = asyncio.create_task(run_app())
    
    return {
        "status": "started",
        "message": "Logic app started",
        "startup_data": _logic_state.startup_data
    }


async def stop_logic():
    if not _logic_state.is_running():
        return {"status": "already_stopped", "message": "Logic app is not running"}
    
    # Lifecycle hook
    on_stop(_logic_state.app_data)
    
    _logic_state.running = False
    
    if _logic_state.ws_client:
        await _logic_state.ws_client.disconnect()
        _logic_state.ws_client = None
    
    if _logic_state.app_data:
        _logic_state.app_data.clear()
        _logic_state.app_data = None
    
    if _logic_state.background_task and not _logic_state.background_task.done():
        _logic_state.background_task.cancel()
        try:
            await _logic_state.background_task
        except asyncio.CancelledError:
            pass
    
    await asyncio.sleep(0.1)
    _logic_state.background_task = None
    _logic_state.started_at = None
    
    return {"status": "stopped", "message": "Logic app stopped gracefully. Application data cleared."}


def get_logic_status():
    app_data = _logic_state.app_data
    return LogicStatus(
        running=_logic_state.is_running(),
        started_at=_logic_state.started_at.isoformat() if _logic_state.started_at else None,
        account_id=_logic_state.startup_data.get("account_id") if _logic_state.startup_data else None,
        active_positions=len(app_data["positions"]) if app_data else 0,
        open_orders=len(app_data["orders"]) if app_data else 0,
    )


def get_logic_data():
    if not _logic_state.is_running():
        raise HTTPException(status_code=503, detail="Logic app is not running")
    app_data = _logic_state.app_data
    return LogicData(
        timestamp=datetime.now().isoformat(),
        total_pnl=app_data["total_pnl"],
        trade_count=app_data["trade_count"],
        positions=[Position(**p) for p in app_data["positions"].values()],
market_data=list(app_data["market_cache"].values()),
    )


# ============================================================
# Router
# ============================================================

def create_logic_router() -> APIRouter:
    router = APIRouter(tags=["logic"])
    
    @router.get("/status", response_model=LogicStatus)
    async def status():
        return get_logic_status()
    
    @router.get("/data", response_model=LogicData)
    async def data():
        return get_logic_data()
    
    @router.post("/start")
    async def start():
        return start_logic()
    
    @router.post("/stop")
    async def stop():
        return await stop_logic()
    
    return router