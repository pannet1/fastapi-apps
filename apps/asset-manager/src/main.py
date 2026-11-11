# main.py
from datetime import date, datetime
from typing import Any, Dict, List, Optional

from fastapi import Depends, FastAPI, Query, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.orm import Session

from am_agent_service import (
    add_fixed_asset,
    add_inventory_item,
    get_business_performance_summary,
    record_payment,
    record_sale,
    seed_sample_data_if_empty,
)
from database import Asset, Base, Customer, Inventory, PaymentLog, Sale, engine, get_db
from routes import asset, inventory, sales

# Initialize Database Tables
Base.metadata.create_all(bind=engine)

app = FastAPI(title="Asset Manager", description="Agent-ready asset, inventory and business ledger manager")

# Mount Static for Product Photos
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# Register Routers
app.include_router(inventory.router)
app.include_router(asset.router)
app.include_router(sales.router)


# Seed initial starter data on first run if database is fresh
with Session(engine) as _init_db:
    seed_sample_data_if_empty(_init_db)


@app.get("/agent")
def redirect_agent_hub():
    return RedirectResponse(url="/agent", status_code=303)


# -------------------------------------------------------------
# Agent & Machine-Readable API Routes
# -------------------------------------------------------------
@app.get("/api/agent/summary")
def agent_summary(
    format: str = Query("json", description="Output format: 'json' or 'markdown'"),
    db: Session = Depends(get_db),
):
    """
    Agent endpoint: Extracts structured or markdown summary of business performance:
    revenue, COGS, gross margin, cash collected, accounts receivable, inventory, and net worth.
    """
    res = get_business_performance_summary(db, fmt=format)
    if format == "markdown":
        return res["markdown"]
    return res


@app.get("/api/agent/inventory")
def agent_inventory(
    status: Optional[str] = Query(None, description="Filter by status, e.g. 'In-Stock', 'Sold'"),
    brand: Optional[str] = Query(None, description="Filter by brand"),
    db: Session = Depends(get_db),
):
    """Agent endpoint: Inspect current inventory items, purchase costs, and market selling prices."""
    q = db.query(Inventory)
    if status:
        q = q.filter(Inventory.status == status)
    if brand:
        q = q.filter(Inventory.brand.ilike(f"%{brand}%"))
    items = q.all()

    return {
        "count": len(items),
        "items": [
            {
                "inventory_id": item.inventory_id,
                "batch_id": item.batch_id,
                "brand": item.brand,
                "model": item.model,
                "serial": item.serial,
                "purchase_price": item.purchase_price,
                "selling_price": item.selling_price,
                "intended_profit": item.intended_profit,
                "status": item.status,
                "sale_id": item.sale_id,
            }
            for item in items
        ],
    }


@app.get("/api/agent/sales")
def agent_sales(db: Session = Depends(get_db)):
    """Agent endpoint: Returns all sales transactions, payment statuses, and linked customers."""
    sales = db.query(Sale).all()
    return {
        "sales_count": len(sales),
        "sales": [
            {
                "sale_id": s.id,
                "customer": s.customer.name if s.customer else "Unknown",
                "sale_date": str(s.sale_date),
                "total_amount": s.total_amount,
                "amount_paid": s.amount_paid,
                "balance": round(s.total_amount - s.amount_paid, 2),
                "items_count": len(s.items),
            }
            for s in sales
        ],
    }


@app.get("/api/agent/debtors")
def agent_debtors(db: Session = Depends(get_db)):
    """Agent endpoint: Returns list of customers with pending receivable balances."""
    sales = db.query(Sale).all()
    unpaid = [
        {
            "sale_id": s.id,
            "customer": s.customer.name if s.customer else "Unknown",
            "sale_date": str(s.sale_date),
            "total_amount": s.total_amount,
            "amount_paid": s.amount_paid,
            "balance_due": round(s.total_amount - s.amount_paid, 2),
        }
        for s in sales
        if (s.total_amount - s.amount_paid) > 0.01
    ]
    return {
        "pending_debtors_count": len(unpaid),
        "total_receivables": round(sum(d["balance_due"] for d in unpaid), 2),
        "debtors": unpaid,
    }


class InventoryInput(BaseModel):
    brand: str
    model: str
    serial: str
    purchase_price: float
    profit: Optional[str] = "25%"
    batch_id: Optional[int] = None
    selling_price: Optional[float] = None
    description: Optional[str] = None


@app.post("/api/agent/inventory")
def api_add_inventory(payload: InventoryInput, db: Session = Depends(get_db)):
    """Agent/API endpoint: Add new inventory item into system."""
    res = add_inventory_item(
        db,
        brand=payload.brand,
        model=payload.model,
        serial=payload.serial,
        purchase_price=payload.purchase_price,
        profit=payload.profit or "25%",
        batch_id=payload.batch_id,
        selling_price=payload.selling_price,
        description=payload.description,
    )
    return res


class SaleInput(BaseModel):
    customer_name: str
    paid: float
    item_ids: List[int]
    sale_date: Optional[str] = None


@app.post("/api/agent/sales")
def api_record_sale(payload: SaleInput, db: Session = Depends(get_db)):
    """Agent/API endpoint: Record a sale to a customer."""
    sale_d = None
    if payload.sale_date:
        try:
            sale_d = datetime.strptime(payload.sale_date, "%Y-%m-%d").date()
        except Exception:
            sale_d = None

    res = record_sale(
        db,
        customer_name=payload.customer_name,
        paid=payload.paid,
        item_ids=payload.item_ids,
        sale_date=sale_d,
    )
    return res


class PaymentInput(BaseModel):
    sale_id: int
    amount: float
    note: Optional[str] = "Part Payment"
    payment_date: Optional[str] = None


@app.post("/api/agent/payments")
def api_record_payment(payload: PaymentInput, db: Session = Depends(get_db)):
    """Agent/API endpoint: Record a payment installment for an unpaid sale."""
    pay_d = None
    if payload.payment_date:
        try:
            pay_d = datetime.strptime(payload.payment_date, "%Y-%m-%d").date()
        except Exception:
            pay_d = None

    res = record_payment(
        db,
        sale_id=payload.sale_id,
        amount=payload.amount,
        note=payload.note or "Part Payment",
        payment_date=pay_d,
    )
    return res


# -------------------------------------------------------------
# Human-Facing UI Routes
# -------------------------------------------------------------
@app.get("/manual", response_class=HTMLResponse)
def manual(request: Request):
    """Plain-language user manual, always reachable from the nav."""
    return templates.TemplateResponse("manual.html", {"request": request})


@app.get("/")
def dashboard(request: Request, db: Session = Depends(get_db)):
    # a) Fixed Assets (Tools)
    asset_val = db.query(func.sum(Asset.cost)).scalar() or 0

    # b) Inventory: Fetch both Cost and Market Value
    stock_cost = (
        db.query(func.sum(Inventory.purchase_price))
        .filter(Inventory.status != "Sold")
        .scalar()
        or 0
    )
    stock_market = (
        db.query(func.sum(Inventory.selling_price))
        .filter(Inventory.status != "Sold")
        .scalar()
        or 0
    )

    # c) Outstanding Receivables
    sales = db.query(Sale).all()
    total_receivable = sum((s.total_amount - s.amount_paid) for s in sales)

    # d) Liquidity (Cash/Checking): Total payments collected so far
    total_cash_received = db.query(func.sum(Sale.amount_paid)).scalar() or 0

    # Calculation Logic
    min_worth = stock_cost + total_cash_received
    max_worth = asset_val + stock_market + total_receivable + total_cash_received

    item_count = db.query(Inventory).filter(Inventory.status != "Sold").count()

    return templates.TemplateResponse(
        "dashboard.html",
        {
            "request": request,
            "min_worth": min_worth,
            "max_worth": max_worth,
            "stock_cost": stock_cost,
            "stock_market": stock_market,
            "total_receivable": total_receivable,
            "total_cash": total_cash_received,
            "item_count": item_count,
            "asset_value": asset_val,
        },
    )
