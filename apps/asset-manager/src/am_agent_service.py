from datetime import date, datetime
from typing import Any, Dict, List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import func

from database import Asset, Batch, Customer, Inventory, PaymentLog, Sale
from contacts_service import build_vcard


def get_business_performance_summary(db: Session, fmt: str = "json") -> Dict[str, Any]:
    """
    Computes business performance metrics:
    - Revenue, COGS, Gross Profit, Margin
    - Cash collected vs Outstanding Receivables (Debtors)
    - Inventory valuation (Cost basis vs Market value)
    - Fixed Assets
    - Net Worth (Conservative Min vs Optimistic Max)
    """
    sales = db.query(Sale).all()
    total_sales = round(sum(s.total_amount for s in sales), 2)
    sales_count = len(sales)

    # Cost of Goods Sold (COGS) for sold inventory items
    sold_items = db.query(Inventory).filter(Inventory.status == "Sold").all()
    cogs = round(sum((item.purchase_price or 0.0) + (item.total_expenses or 0.0) for item in sold_items), 2)
    gross_profit = round(total_sales - cogs, 2)
    gross_margin_pct = round((gross_profit / total_sales * 100), 1) if total_sales > 0 else 0.0

    # Liquidity & Receivables
    cash_collected = round(sum(s.amount_paid for s in sales), 2)
    receivables = round(sum((s.total_amount - s.amount_paid) for s in sales if (s.total_amount - s.amount_paid) > 0.01), 2)

    debtors = []
    for s in sales:
        bal = round(s.total_amount - s.amount_paid, 2)
        if bal > 0.01:
            debtors.append({
                "sale_id": s.id,
                "customer": s.customer.name if s.customer else "Unknown",
                "sale_date": str(s.sale_date),
                "total_amount": round(s.total_amount, 2),
                "amount_paid": round(s.amount_paid, 2),
                "balance_due": bal,
            })

    # Inventory Valuation
    in_stock_items = db.query(Inventory).filter(Inventory.status != "Sold").all()
    in_stock_count = len(in_stock_items)
    stock_cost = round(sum(item.purchase_price or 0.0 for item in in_stock_items), 2)
    stock_market = round(sum(item.selling_price or 0.0 for item in in_stock_items), 2)
    unrealized_profit = round(stock_market - stock_cost, 2)

    # Brand breakdown
    brand_counts = {}
    for item in in_stock_items:
        b = item.brand or "Unbranded"
        brand_counts[b] = brand_counts.get(b, 0) + 1

    # Fixed Assets
    assets = db.query(Asset).all()
    asset_val = round(sum(a.cost for a in assets), 2)
    asset_list = [{"id": a.id, "name": a.name, "cost": round(a.cost, 2), "purchase_date": str(a.purchase_date)} for a in assets]

    # Valuation
    conservative_min_worth = round(stock_cost + cash_collected, 2)
    optimistic_max_worth = round(asset_val + stock_market + receivables + cash_collected, 2)

    result = {
        "revenue_and_profit": {
            "total_sales_revenue": total_sales,
            "sales_count": sales_count,
            "cost_of_goods_sold": cogs,
            "gross_profit": gross_profit,
            "gross_margin_pct": gross_margin_pct,
        },
        "liquidity_and_receivables": {
            "cash_collected": cash_collected,
            "outstanding_receivables": receivables,
            "collection_rate_pct": round((cash_collected / total_sales * 100), 1) if total_sales > 0 else 0.0,
            "unpaid_debtors": debtors,
        },
        "inventory_health": {
            "in_stock_count": in_stock_count,
            "stock_cost_basis": stock_cost,
            "stock_market_value": stock_market,
            "unrealized_potential_profit": unrealized_profit,
            "brand_summary": brand_counts,
        },
        "fixed_assets": {
            "total_asset_value": asset_val,
            "asset_count": len(assets),
            "assets": asset_list,
        },
        "business_valuation": {
            "conservative_min_worth": conservative_min_worth,
            "optimistic_max_worth": optimistic_max_worth,
            "formula_notes": {
                "min_worth": "Stock Cost Basis + Cash Collected",
                "max_worth": "Fixed Assets + Stock Market Value + Outstanding Receivables + Cash Collected",
            },
        },
    }

    if fmt == "markdown":
        return {"markdown": _format_business_markdown(result), "data": result}
    return result


def _format_business_markdown(summary: Dict[str, Any]) -> str:
    rp = summary.get("revenue_and_profit", {})
    lr = summary.get("liquidity_and_receivables", {})
    inv = summary.get("inventory_health", {})
    fa = summary.get("fixed_assets", {})
    val = summary.get("business_valuation", {})
    debtors = lr.get("unpaid_debtors", [])

    lines = [
        "### 🏢 Business Performance Summary",
        f"- **Revenue**: ${rp.get('total_sales_revenue', 0.0):,.2f} ({rp.get('sales_count', 0)} sales)",
        f"- **COGS (Cost of Goods Sold)**: ${rp.get('cost_of_goods_sold', 0.0):,.2f}",
        f"- **Gross Profit**: ${rp.get('gross_profit', 0.0):,.2f} ({rp.get('gross_margin_pct', 0.0)}% margin)",
        f"- **Cash Collected**: ${lr.get('cash_collected', 0.0):,.2f}",
        f"- **Outstanding Receivables**: ${lr.get('outstanding_receivables', 0.0):,.2f} ({len(debtors)} unpaid)",
        f"- **Current Inventory**: {inv.get('in_stock_count', 0)} units | ${inv.get('stock_cost_basis', 0.0):,.2f} cost basis | ${inv.get('stock_market_value', 0.0):,.2f} market value",
        f"- **Fixed Assets Value**: ${fa.get('total_asset_value', 0.0):,.2f}",
        f"- **Business Net Worth**: Conservative **${val.get('conservative_min_worth', 0.0):,.2f}** | Optimistic **${val.get('optimistic_max_worth', 0.0):,.2f}**",
    ]

    if debtors:
        lines.append("- **⚠️ Pending Debtors**:")
        for d in debtors[:5]:
            lines.append(f"  - **{d['customer']}**: Owe ${d['balance_due']:,.2f} (Paid ${d['amount_paid']:,.2f} of ${d['total_amount']:,.2f})")

    return "\n".join(lines)


def add_inventory_item(
    db: Session,
    brand: str,
    model: str,
    serial: str,
    purchase_price: float,
    profit: str = "20%",
    batch_id: Optional[int] = None,
    selling_price: Optional[float] = None,
    description: Optional[str] = None,
) -> Dict[str, Any]:
    """Adds a new inventory item with auto-calculated selling price."""
    if not batch_id:
        batch = db.query(Batch).first()
        if not batch:
            batch = Batch(description="General Intake", supplier_name="Direct Sourcing", date=date.today())
            db.add(batch)
            db.commit()
            db.refresh(batch)
        batch_id = batch.id

    if selling_price is None or selling_price <= 0:
        calc_profit = 0.0
        try:
            p_str = str(profit).strip()
            if p_str.endswith("%"):
                pct = float(p_str.replace("%", "")) / 100.0
                calc_profit = purchase_price * pct
            else:
                calc_profit = float(p_str)
        except Exception:
            calc_profit = purchase_price * 0.20
        selling_price = round(purchase_price + calc_profit, 2)

    # Check for existing serial to remain idempotent
    existing = db.query(Inventory).filter(Inventory.serial == serial.strip()).first()
    if existing:
        existing.purchase_price = round(float(purchase_price), 2)
        existing.intended_profit = str(profit)
        existing.selling_price = round(float(selling_price), 2)
        if description:
            existing.description_for_ecommerce = description
        db.commit()
        db.refresh(existing)
        return {
            "status": "success",
            "inventory_id": existing.inventory_id,
            "brand": existing.brand,
            "model": existing.model,
            "purchase_price": existing.purchase_price,
            "selling_price": existing.selling_price,
            "updated": True,
        }

    item = Inventory(
        batch_id=batch_id,
        brand=brand.strip(),
        model=model.strip(),
        serial=serial.strip(),
        purchase_price=round(float(purchase_price), 2),
        intended_profit=str(profit),
        selling_price=round(float(selling_price), 2),
        description_for_ecommerce=description,
        status="In-Stock",
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return {
        "status": "success",
        "inventory_id": item.inventory_id,
        "brand": item.brand,
        "model": item.model,
        "purchase_price": item.purchase_price,
        "selling_price": item.selling_price,
    }


def record_sale(
    db: Session,
    customer_name: str,
    paid: float,
    inventory_ids: Optional[List[int]] = None,
    item_ids: Optional[List[int]] = None,
    sale_price: Optional[float] = None,
    service_description: Optional[str] = None,
    sale_date: Optional[date] = None,
) -> Dict[str, Any]:
    """Records a sale (either physical inventory or pure service/repair) and updates ledger."""
    target_ids = inventory_ids if inventory_ids is not None else (item_ids or [])
    clean_name = customer_name.strip()
    all_customers = db.query(Customer).all()
    customer = next((c for c in all_customers if c.name.lower() == clean_name.lower()), None)
    if not customer:
        customer = Customer(vcard=build_vcard(clean_name))
        db.add(customer)
        db.commit()
        db.refresh(customer)

    selected_items = db.query(Inventory).filter(Inventory.inventory_id.in_(target_ids)).all() if target_ids else []
    if not selected_items and not service_description:
        return {"status": "error", "message": "Either inventory items or a service description must be provided"}

    if sale_price is not None:
        total_bill = float(sale_price)
    else:
        total_bill = sum(item.selling_price for item in selected_items if item.selling_price) if selected_items else 0.0

    new_sale = Sale(
        customer_id=customer.id,
        sale_date=sale_date or date.today(),
        service_description=service_description,
        total_amount=round(float(total_bill), 2),
        amount_paid=round(float(paid), 2),
    )
    db.add(new_sale)
    db.commit()
    db.refresh(new_sale)

    for item in selected_items:
        item.status = "Sold"
        item.sale_id = new_sale.id
        if sale_price is not None and len(selected_items) == 1:
            item.selling_price = round(float(sale_price), 2)

    if paid > 0:
        log = PaymentLog(
            sale_id=new_sale.id,
            amount_received=round(float(paid), 2),
            payment_date=sale_date or date.today(),
            note="Initial payment on sale",
        )
        db.add(log)

    db.commit()

    return {
        "status": "success",
        "sale_id": new_sale.id,
        "customer": customer.name,
        "total_amount": new_sale.total_amount,
        "amount_paid": new_sale.amount_paid,
        "balance_remaining": round(new_sale.total_amount - new_sale.amount_paid, 2),
        "items_sold_count": len(selected_items),
    }


def record_payment(
    db: Session,
    sale_id: int,
    amount: float,
    note: str = "Part Payment",
    payment_date: Optional[date] = None,
) -> Dict[str, Any]:
    """Records an installment payment on an existing sale."""
    sale = db.query(Sale).filter(Sale.id == sale_id).first()
    if not sale:
        return {"status": "error", "message": f"Sale ID {sale_id} not found"}

    sale.amount_paid = round(sale.amount_paid + float(amount), 2)
    log = PaymentLog(
        sale_id=sale.id,
        amount_received=round(float(amount), 2),
        payment_date=payment_date or date.today(),
        note=note,
    )
    db.add(log)
    db.commit()

    return {
        "status": "success",
        "sale_id": sale.id,
        "new_amount_paid": sale.amount_paid,
        "remaining_balance": round(sale.total_amount - sale.amount_paid, 2),
        "note": note,
    }


def add_fixed_asset(
    db: Session,
    name: str,
    cost: float,
    purchase_date: Optional[date] = None,
) -> Dict[str, Any]:
    """Adds a fixed asset/equipment entry."""
    new_asset = Asset(
        name=name.strip(),
        cost=round(float(cost), 2),
        purchase_date=purchase_date or date.today(),
    )
    db.add(new_asset)
    db.commit()
    db.refresh(new_asset)
    return {
        "status": "success",
        "asset_id": new_asset.id,
        "name": new_asset.name,
        "cost": new_asset.cost,
        "purchase_date": str(new_asset.purchase_date),
    }


def seed_sample_data_if_empty(db: Session) -> bool:
    """Disabled: Do not auto-seed dummy records. Respect real user data."""
    return False
