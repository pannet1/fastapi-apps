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
from typing import Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel


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
# Lifecycle
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
# UI Templates
# ============================================================

CONTROLLER_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>FastAPI Controller</title>
  <style>
    * { margin: 0; padding: 0; box-sizing: border-box; }
    body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; min-height: 100vh; display: flex; align-items: center; justify-content: center; background: linear-gradient(135deg, #1a1a2e 0%, #16213e 50%, #0f3460 100%); color: #eaeaea; }
    .container { background: rgba(255,255,255,0.05); backdrop-filter: blur(10px); border: 1px solid rgba(255,255,255,0.1); border-radius: 16px; padding: 2rem; text-align: center; max-width: 400px; width: 90%; box-shadow: 0 8px 32px rgba(0,0,0,0.3); }
    h1 { font-size: 1.75rem; font-weight: 600; margin-bottom: 0.5rem; background: linear-gradient(90deg, #00d9ff, #00ff88); -webkit-background-clip: text; -webkit-text-fill-color: transparent; background-clip: text; }
    .subtitle { color: #6b7280; font-size: 0.9rem; margin-bottom: 2rem; }
    .status-card { background: rgba(0,0,0,0.3); border-radius: 12px; padding: 1.25rem; margin-bottom: 1rem; }
    .status-label { font-size: 0.75rem; text-transform: uppercase; letter-spacing: 0.1em; color: #6b7280; margin-bottom: 0.5rem; }
    .status-value { font-size: 1.25rem; font-weight: 600; }
    .status-value.running { color: #00ff88; }
    .status-value.stopped { color: #ff4757; }
    .status-value::before { content: '●'; margin-right: 0.5rem; }
    .status-value.warn { color: #f39c12; }
    .schedule-card { background: rgba(0,0,0,0.2); border-radius: 8px; padding: 0.75rem; margin-bottom: 1rem; font-size: 0.8rem; }
    .schedule-time { font-weight: 600; color: #00d9ff; }
    .schedule-status { margin-top: 0.5rem; }
    .schedule-status.active { color: #00ff88; }
    .schedule-status.inactive { color: #ff4757; }
    .info { display: flex; justify-content: center; gap: 2rem; margin-bottom: 1.5rem; font-size: 0.85rem; color: #9ca3af; }
    button { background: linear-gradient(135deg, #00d9ff 0%, #00a8cc 100%); border: none; border-radius: 8px; padding: 0.875rem 2rem; font-size: 1rem; font-weight: 600; color: #0f172a; cursor: pointer; transition: all 0.2s; width: 100%; }
    button:hover { transform: translateY(-2px); box-shadow: 0 4px 20px rgba(0,217,255,0.4); }
    button.stop { background: linear-gradient(135deg, #ff4757 0%, #c0392b 100%); }
    button:disabled { opacity: 0.5; cursor: not-allowed; }
    .error-msg { color: #f39c12; font-size: 0.8rem; margin-top: 0.5rem; }
  </style>
</head>
<body>
  <div class="container">
    <h1>FastAPI Controller</h1>
    <p class="subtitle">Control Your Trading App</p>
    
    <div class="schedule-card">
      <div class="status-label">Schedule</div>
      <div class="schedule-time" id="scheduleTime">09:15 - 15:30</div>
      <div class="schedule-status" id="scheduleStatus">Checking...</div>
    </div>
    
    <div class="status-card">
      <div class="status-label">Logic App Status</div>
      <div class="status-value stopped" id="status">Stopped</div>
    </div>
    <div class="info">
      <span>Account: <span class="value" id="account">—</span></span>
      <span>Positions: <span class="value" id="positions">0</span></span>
    </div>
    <button id="toggleBtn" onclick="toggleLogic()">Start Logic App</button>
    <div class="error-msg" id="errorMsg"></div>
  </div>
  <script>
    let isRunning = false;
    async function updateStatus() {
      try {
        const [logicResp, schedResp] = await Promise.all([
          fetch('/api/logic/status'),
          fetch('/api/schedule')
        ]);
        const data = await logicResp.json();
        const sched = await schedResp.json();
        
        isRunning = data.running;
        
        // Auto-redirect to logic page if running + within schedule
        if (data.running && sched.within_schedule) {
          window.location.href = '/logic';
          return;
        }
        
        // Update status
        document.getElementById('status').textContent = data.running ? 'Running' : 'Stopped';
        document.getElementById('status').className = 'status-value ' + (data.running ? 'running' : 'stopped');
        
        // Update schedule status
        const schedStatus = document.getElementById('scheduleStatus');
        if (sched.within_schedule) {
          schedStatus.textContent = 'Within schedule • Active for ' + sched.time_until_end;
          schedStatus.className = 'schedule-status active';
        } else {
          schedStatus.textContent = 'Outside schedule • Opens in ' + sched.time_until_start;
          schedStatus.className = 'schedule-status inactive';
        }
        
        // Update button
        const btn = document.getElementById('toggleBtn');
        const errorMsg = document.getElementById('errorMsg');
        
        if (data.running) {
          btn.textContent = 'Stop Logic App';
          btn.className = 'stop';
          errorMsg.textContent = '';
        } else {
          if (sched.within_schedule) {
            btn.textContent = 'Start Logic App';
            btn.className = '';
            errorMsg.textContent = '';
          } else {
            btn.textContent = 'Start Logic App';
            btn.className = '';
            btn.disabled = true;
            errorMsg.textContent = 'Outside scheduled hours. Try at ' + sched.time_until_start;
          }
        }
        
        document.getElementById('account').textContent = data.account_id || '—';
        document.getElementById('positions').textContent = data.active_positions || 0;
      } catch(e) { console.error(e); }
    }
    async function toggleLogic() {
      const btn = document.getElementById('toggleBtn');
      btn.disabled = true;
      try {
        await fetch('/api/logic/' + (isRunning ? 'stop' : 'start'), { method: 'POST' });
        location.reload();
      } finally { btn.disabled = false; }
    }
    setInterval(updateStatus, 2000);
    setInterval(updateStatus, 2000);
  </script>
</body>
</html>"""


LOGIC_APP_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Trading Logic App</title>
  <style>
    * { margin: 0; padding: 0; box-sizing: border-box; }
    body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; min-height: 100vh; background: linear-gradient(135deg, #0f0f23 0%, #1a1a2e 100%); color: #eaeaea; padding: 1rem; }
    .header { display: flex; justify-content: space-between; align-items: center; padding: 1rem 0; border-bottom: 1px solid rgba(255,255,255,0.1); margin-bottom: 1rem; }
    h1 { font-size: 1.5rem; background: linear-gradient(90deg, #00ff88, #00d9ff); -webkit-background-clip: text; -webkit-text-fill-color: transparent; }
    button { background: linear-gradient(135deg, #ff4757 0%, #c0392b 100%); border: none; border-radius: 8px; padding: 0.5rem 1.5rem; font-size: 0.9rem; font-weight: 600; color: white; cursor: pointer; }
    .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 1rem; }
    .card { background: rgba(255,255,255,0.05); border: 1px solid rgba(255,255,255,0.1); border-radius: 12px; padding: 1rem; }
    .card h3 { font-size: 0.75rem; text-transform: uppercase; color: #6b7280; margin-bottom: 0.5rem; }
    .card .value { font-size: 1.5rem; font-weight: 600; }
    .card .value.positive { color: #00ff88; }
    .card .value.negative { color: #ff4757; }
    .market-data { margin-top: 1rem; }
    .market-item { display: flex; justify-content: space-between; padding: 0.75rem; background: rgba(0,0,0,0.2); border-radius: 8px; margin-bottom: 0.5rem; }
    .symbol { font-weight: 600; color: #00d9ff; }
    .price { font-family: monospace; }
  </style>
</head>
<body>
  <div class="header">
    <h1>Trading Logic App</h1>
    <button onclick="stopLogic()">Stop & Return to Controller</button>
  </div>
  <div class="grid">
    <div class="card">
      <h3>Total P&L</h3>
      <div class="value" id="pnl">₹0.00</div>
    </div>
    <div class="card">
      <h3>Trade Count</h3>
      <div class="value" id="trades">0</div>
    </div>
    <div class="card">
      <h3>Positions</h3>
      <div class="value" id="positions">0</div>
    </div>
    <div class="card">
      <h3>Account</h3>
      <div class="value" id="account">—</div>
    </div>
  </div>
  <div class="market-data">
    <h3 style="margin: 1rem 0 0.5rem; font-size: 0.75rem; text-transform: uppercase; color: #6b7280;">Market Data</h3>
    <div id="marketData"></div>
  </div>
  <script>
    async function loadData() {
      try {
        // Check schedule - auto-redirect if outside schedule
        const schedResp = await fetch('/api/schedule');
        const sched = await schedResp.json();
        
        if (!sched.within_schedule) {
          // Outside schedule - auto-stop and redirect
          await fetch('/api/logic/stop', { method: 'POST' });
          window.location.href = '/';
          return;
        }
        
        const status = await fetch('/api/logic/status').then(r => r.json());
        
        // If logic stopped externally, redirect
        if (!status.running) {
          window.location.href = '/';
          return;
        }
        
        document.getElementById('account').textContent = status.account_id || '—';
        document.getElementById('positions').textContent = status.active_positions || 0;
        const data = await fetch('/api/logic/data').then(r => r.json());
        document.getElementById('pnl').textContent = '₹' + data.total_pnl.toFixed(2);
        document.getElementById('pnl').className = 'value ' + (data.total_pnl >= 0 ? 'positive' : 'negative');
        document.getElementById('trades').textContent = data.trade_count;
        const marketDiv = document.getElementById('marketData');
        marketDiv.innerHTML = data.market_data.map(m => '<div class="market-item"><span class="symbol">' + m.symbol + '</span><span class="price">₹' + m.last + ' <span style="color:#6b7280;">(' + m.volume.toFixed(0) + ')</span></span></div>').join('');
      } catch(e) { 
        console.error(e);
        // On error, try to redirect to controller
        window.location.href = '/';
      }
    }
    async function stopLogic() {
      await fetch('/api/logic/stop', { method: 'POST' });
      window.location.href = '/';
    }
    loadData();
    setInterval(loadData, 2000);
  </script>
</body>
</html>"""


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