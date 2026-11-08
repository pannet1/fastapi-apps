# main.py
from fastapi import Depends, FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy import func  # Add this import
from sqlalchemy.orm import Session  # Add this line

from database import Asset, Base, Inventory, Sale, engine, get_db
from routes import asset, inventory, sales  # Import both routers

# Initialize Database Tables
Base.metadata.create_all(bind=engine)

app = FastAPI()

# Mount Static for Product Photos
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# Register Routers
app.include_router(inventory.router)
app.include_router(asset.router)
app.include_router(sales.router)


@app.get("/manual", response_class=HTMLResponse)
def manual(request: Request):
    """Plain-language user manual, always reachable from the nav."""
    return templates.TemplateResponse("manual.html", {"request": request})


@app.get("/")
def dashboard(request: Request, db: Session = Depends(get_db)):
    # a) Fixed Assets (Tools)
    asset_val = db.query(func.sum(Asset.cost)).scalar() or 0

    # b) Inventory: Fetch both Cost and Market Value
    # stock_cost = Minimum value (what you paid)
    # stock_market = Maximum value (what you expect to get)
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
    # Min Worth: Stock Cost + Cash (Assumes tools are worth $0 and no profit made)
    min_worth = stock_cost + total_cash_received
    # Max Worth: Assets + Stock Market + Receivables + Cash
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
