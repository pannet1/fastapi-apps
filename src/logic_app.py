"""Logic App - Runnable FastAPI app with simulated trading.

Features:
- Startup data (initialized at start)
- Application data (runtime - cleared on stop)
- Fake websocket client (market data simulation)
"""

import asyncio
import json
import logging
import random
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

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
        self.paused = False
        self.pause_until: Optional[datetime] = None
        self.pause_reason: str = ""
    
    def is_running(self) -> bool:
        return self.running and self.background_task is not None and not self.background_task.done()
    
    def is_paused(self) -> bool:
        if self.paused and self.pause_until:
            if datetime.now() < self.pause_until:
                return True
            self.paused = False
            self.pause_until = None
            self.pause_reason = ""
        return False


_logic_state = LogicState()


# ============================================================
# Response Models
# ============================================================

class LogicStatus(BaseModel):
    running: bool
    started_at: Optional[str] = None
    account_id: Optional[str] = None
    session_id: Optional[str] = None  # Broker session ID (changes on every start)
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

def on_start(startup_data: dict, app_data: dict):
    """Called when logic app starts. Performs all initialization steps.
    
    startup_data: Contains config (account_id, session_id, etc.)
    app_data: Will contain runtime state (cleared on stop)
    """
    account_id = startup_data.get('account_id', 'UNKNOWN')
    session_id = startup_data.get('session_id', 'UNKNOWN')
    
    logger.info(f"[LIFECYCLE] ============================================")
    logger.info(f"[LIFECYCLE] Starting Initialization for account: {account_id}")
    logger.info(f"[LIFECYCLE] Session: {session_id}")
    
    # Step 1: Validate broker connection
    logger.info(f"[LIFECYCLE:1/12] Validating broker connection...")
    _validate_broker_connection(session_id)
    
    # Step 2: Authenticate and get access token
    logger.info(f"[LIFECYCLE:2/12] Authenticating with broker API...")
    access_token = _authenticate_with_broker(session_id)
    app_data['access_token'] = access_token  # Runtime - in app_data
    
    # Step 3: Fetch account details
    logger.info(f"[LIFECYCLE:3/12] Fetching account details...")
    account_details = _fetch_account_details(access_token, account_id)
    startup_data['account_details'] = account_details  # Config - in startup_data
    
    # Step 4: Validate subscription and margins
    logger.info(f"[LIFECYCLE:4/12] Validating subscription and margins...")
    margin_info = _validate_subscription(access_token)
    app_data['margin_info'] = margin_info  # Runtime - in app_data
    
    # Step 5: Fetch tradable symbols
    logger.info(f"[LIFECYCLE:5/12] Fetching tradable symbols...")
    symbols = _fetch_tradable_symbols(access_token, startup_data.get('symbols', []))
    app_data['symbols_data'] = symbols  # Runtime - in app_data
    startup_data['symbols'] = [s['symbol'] for s in symbols]  # Keep strings in startup_data for websocket
    
    # Step 6: Fetch initial market data (LTP)
    logger.info(f"[LIFECYCLE:6/12] Fetching initial market data...")
    initial_prices = _fetch_initial_prices(access_token, symbols)
    app_data['initial_prices'] = initial_prices  # Runtime - in app_data
    
    # Step 7: Initialize WebSocket connection
    logger.info(f"[LIFECYCLE:7/12] Setting up WebSocket connection...")
    ws_endpoint = _setup_websocket(access_token)
    app_data['ws_endpoint'] = ws_endpoint  # Runtime - in app_data
    
    # Step 8: Load cached strategy state
    logger.info(f"[LIFECYCLE:8/12] Loading cached strategy state...")
    strategy_state = _load_strategy_state(startup_data)
    app_data['strategy_state'] = strategy_state  # Runtime - in app_data
    
    # Step 9: Initialize trading strategies
    logger.info(f"[LIFECYCLE:9/12] Initializing trading strategies...")
    strategy_configs = _initialize_strategies(access_token, startup_data)
    app_data['strategy_configs'] = strategy_configs  # Runtime - in app_data
    
    # Step 10: Sync open orders and positions
    logger.info(f"[LIFECYCLE:10/12] Syncing open orders and positions...")
    open_orders, positions = _sync_orders_and_positions(access_token)
    app_data['synced_orders'] = open_orders  # Runtime - in app_data
    app_data['synced_positions'] = positions  # Runtime - in app_data
    
    # Step 11: Load historical P&L data
    logger.info(f"[LIFECYCLE:11/12] Loading historical P&L...")
    historical_pnl = _load_historical_pnl(access_token)
    app_data['historical_pnl'] = historical_pnl  # Runtime - in app_data
    
    # Step 12: Final health check
    logger.info(f"[LIFECYCLE:12/12] Running health checks...")
    health_status = _run_health_checks(app_data)
    app_data['health_status'] = health_status  # Runtime - in app_data
    
    logger.info(f"[LIFECYCLE] ============================================")
    logger.info(f"[LIFECYCLE] Initialization Complete!")
    logger.info(f"[LIFECYCLE] Account: {account_id}, Symbols: {len(symbols)}, Strategies: {len(strategy_configs)}")
    logger.info(f"[LIFECYCLE] Margin Available: {margin_info.get('available_margin', 'N/A')}")
    logger.info(f"[LIFECYCLE] ============================================")


def _validate_broker_connection(session_id: str) -> bool:
    """Validate that broker API is reachable."""
    logger.info(f"[BROKER] Validating connection for session: {session_id}")
    # Simulate API check
    import time
    time.sleep(0.05)  # Simulate network latency
    logger.info(f"[BROKER] Connection validated: OK")
    return True


def _authenticate_with_broker(session_id: str) -> str:
    """Authenticate and get access token."""
    import hashlib
    token = hashlib.sha256(f"{session_id}_{uuid.uuid4()}".encode()).hexdigest()[:24]
    logger.info(f"[BROKER] Authenticated, access token: {token[:8]}...")
    return token


def _fetch_account_details(access_token: str, account_id: str) -> dict:
    """Fetch account details like name, email, broker info."""
    details = {
        "account_id": account_id,
        "client_name": "Demo Trader",
        "email": "trader@example.com",
        "broker": "Finvasia",
        "account_type": "COMMON",
        "pan": "XXXXXXXXXX1234",
    }
    logger.info(f"[BROKER] Account details fetched: {details['client_name']}, {details['broker']}")
    return details


def _validate_subscription(access_token: str) -> dict:
    """Validate subscription status and margin."""
    margin = {
        "available_margin": random.uniform(50000, 500000),
        "used_margin": random.uniform(0, 100000),
        "blocked_margin": random.uniform(0, 50000),
        "day_margin": random.uniform(100000, 1000000),
        "subscription_active": True,
        "subscription_expiry": "2026-12-31",
    }
    logger.info(f"[BROKER] Margin available: ₹{margin['available_margin']:.2f}, Subscription: {margin['subscription_active']}")
    return margin


def _fetch_tradable_symbols(access_token: str, requested_symbols: list) -> list:
    """Fetch list of tradable symbols with their details."""
    symbols_with_data = []
    for sym in requested_symbols:
        symbols_with_data.append({
            "symbol": sym,
            "token": str(uuid.uuid4())[:10],
            "exchange": "NSE",
            "lot_size": random.choice([75, 100, 125, 250]),
            "tick_size": 0.05,
            "allowed": True,
        })
    logger.info(f"[BROKER] Fetched {len(symbols_with_data)} tradable symbols")
    return symbols_with_data


def _fetch_initial_prices(access_token: str, symbols: list) -> dict:
    """Fetch last traded prices for all symbols."""
    prices = {}
    for sym in symbols:
        prices[sym['symbol']] = {
            "ltp": random.uniform(100, 5000),
            "open": random.uniform(100, 5000),
            "high": random.uniform(100, 5000),
            "low": random.uniform(100, 5000),
            "close": random.uniform(100, 5000),
            "volume": random.randint(100000, 10000000),
        }
    logger.info(f"[BROKER] Fetched LTP for {len(prices)} symbols")
    return prices


def _setup_websocket(access_token: str) -> str:
    """Setup and return WebSocket endpoint."""
    ws_id = str(uuid.uuid4())[:8]
    endpoint = f"wss://api.broker.com/stream/{ws_id}"
    logger.info(f"[BROKER] WebSocket endpoint ready: {endpoint[:40]}...")
    return endpoint


def _load_strategy_state(startup_data: dict) -> dict:
    """Load cached strategy state from previous session."""
    state = {
        "last_trade_time": datetime.now().isoformat(),
        "trade_count": 0,
        "last_symbol": None,
        "indicators": {
            "rsi": random.uniform(30, 70),
            "macd": random.uniform(-5, 5),
        },
        "cache_valid": True,
    }
    logger.info(f"[STRATEGY] Loaded cached state, indicators: RSI={state['indicators']['rsi']:.2f}")
    return state


def _initialize_strategies(access_token: str, startup_data: dict) -> list:
    """Initialize trading strategies with their parameters."""
    strategies = []
    for strat_name in startup_data.get('strategies', ['momentum', 'mean_reversion']):
        strategies.append({
            "name": strat_name,
            "enabled": True,
            "params": {
                "lookback_period": random.randint(14, 30),
                "threshold": random.uniform(0.01, 0.05),
                "max_positions": random.randint(3, 10),
            },
            "status": "initialized",
        })
    logger.info(f"[STRATEGY] Initialized {len(strategies)} strategies: {[s['name'] for s in strategies]}")
    return strategies


def _sync_orders_and_positions(access_token: str) -> tuple:
    """Sync open orders and positions from broker."""
    orders = []  # Would fetch from broker
    positions = []  # Would fetch from broker
    logger.info(f"[BROKER] Synced {len(orders)} open orders, {len(positions)} positions")
    return orders, positions


def _load_historical_pnl(access_token: str) -> dict:
    """Load historical P&L data."""
    pnl = {
        "today_pnl": random.uniform(-5000, 15000),
        "week_pnl": random.uniform(-10000, 30000),
        "month_pnl": random.uniform(-20000, 50000),
    }
    logger.info(f"[BROKER] Loaded historical P&L: Today={pnl['today_pnl']:.2f}")
    return pnl


def _run_health_checks(app_data: dict) -> dict:
    """Run health checks on all systems."""
    checks = {
        "broker_connection": "healthy",
        "websocket": "healthy",
        "margin": "healthy",
        "strategies": "healthy",
        "symbols": "healthy",
    }
    all_healthy = all(v == "healthy" for v in checks.values())
    logger.info(f"[HEALTH] All systems healthy: {all_healthy}")
    return {"passed": all_healthy, "details": checks}


def on_stop(app_data: dict):
    """Called when logic app stops."""
    logger.info(f"[LIFECYCLE] on_stop called - cleaning up {len(app_data.get('positions', {}))} positions")
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
            
        except asyncio.TimeoutError:
            pass  # Expected: no data in queue within 0.5s, loop again
        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.error(f"Background logic error: {type(e).__name__}: {e}")
            
    app_data.clear()


def login() -> tuple[str, str]:
    """Simulate broker login - generates new session on every call.
    
    In real implementation, this would:
    1. Connect to broker API
    2. Authenticate with credentials
    3. Get access token and refresh token
    4. Return session ID and token
    
    Returns:
        tuple: (session_id, session_token)
    """
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    session_id = f"SES_{timestamp}_{str(uuid.uuid4())[:6].upper()}"
    session_token = str(uuid.uuid4()).replace('-', '')[:32]
    
    logger.info(f"[BROKER] New session created: {session_id}")
    return session_id, session_token


async def start_logic():
    if _logic_state.is_running():
        return {"status": "already_running", "message": "Logic app is already running"}
    
    # Login to broker - generates new session token on every start
    session_id, session_token = login()
    logger.info(f"New broker session: {session_id}")
    
    # Startup data
    _logic_state.startup_data = {
        "api_key": "fake_api_key_" + str(uuid.uuid4())[:8],
        "account_id": "ACC_" + str(uuid.uuid4())[:6].upper(),
        "strategies": ["momentum", "mean_reversion"],
        "symbols": ["RELIANCE", "TCS", "INFY", "HDFCBANK", "ITC"],
        "max_position_size": 100.0,
        "max_loss_per_trade": 1000.0,
        "stop_loss_pct": 0.5,
        # Broker session info
        "session_id": session_id,
        "session_token": session_token,
        "logged_in_at": datetime.now().isoformat(),
    }
    

    
    # Initialize app_data first (runtime state, cleared on stop)
    _logic_state.app_data = {
        "positions": {},
        "orders": [],
        "market_cache": {},
        "total_pnl": 0.0,
        "trade_count": 0,
        "last_update": None,
    }
    
    # Lifecycle hook (passes both startup_data and app_data)
    on_start(_logic_state.startup_data, _logic_state.app_data)
    
    # Extract symbol strings for websocket (handle both strings and dicts)
    raw_symbols = _logic_state.startup_data.get('symbols', [])
    if raw_symbols and isinstance(raw_symbols[0], dict):
        symbol_strings = [s['symbol'] for s in raw_symbols]
    else:
        symbol_strings = raw_symbols
    
    # Store initialization data in app_data (runtime state, not startup config)
    _logic_state.app_data = {
        "positions": {},
        "orders": [],
        "market_cache": {},
        "total_pnl": 0.0,
        "trade_count": 0,
        "last_update": None,
        # Runtime data from initialization
        "access_token": _logic_state.startup_data.get('access_token'),
        "account_details": _logic_state.startup_data.get('account_details'),
        "margin_info": _logic_state.startup_data.get('margin_info'),
        "initial_prices": _logic_state.startup_data.get('initial_prices'),
        "ws_endpoint": _logic_state.startup_data.get('ws_endpoint'),
        "strategy_state": _logic_state.startup_data.get('strategy_state'),
        "strategy_configs": _logic_state.startup_data.get('strategy_configs'),
        "historical_pnl": _logic_state.startup_data.get('historical_pnl'),
        "health_status": _logic_state.startup_data.get('health_status'),
    }
    
    # Websocket client
    _logic_state.ws_client = FakeWebsocketClient(symbol_strings)
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


async def pause_logic(reason: str = "manual", duration_seconds: int = 60):
    """Pause logic app - stops it and prevents auto-restart for specified duration."""
    if _logic_state.is_running():
        await stop_logic()
    
    _logic_state.paused = True
    _logic_state.pause_until = datetime.now() + timedelta(seconds=duration_seconds)
    _logic_state.pause_reason = reason
    
    return {
        "status": "paused",
        "reason": reason,
        "until": _logic_state.pause_until.isoformat(),
    }


def get_logic_status():
    app_data = _logic_state.app_data
    return LogicStatus(
        running=_logic_state.is_running(),
        started_at=_logic_state.started_at.isoformat() if _logic_state.started_at else None,
        account_id=_logic_state.startup_data.get("account_id") if _logic_state.startup_data else None,
        session_id=_logic_state.startup_data.get("session_id") if _logic_state.startup_data else None,
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
        return await start_logic()
    
    @router.post("/stop")
    async def stop():
        return await stop_logic()
    
    @router.post("/pause")
    async def pause(reason: str = "manual", duration: int = 60):
        return await pause_logic(reason=reason, duration_seconds=duration)
    
    return router