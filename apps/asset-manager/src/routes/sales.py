# path: routes/sales.py
from datetime import date
from typing import Optional, List

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from starlette.templating import Jinja2Templates

from database import (
    Customer,
    Inventory,
    PaymentLog,
    Sale,
    get_db,
)

router = APIRouter()
templates = Jinja2Templates(directory="templates")


@router.get("/sales")
def sales_page(request: Request, db: Session = Depends(get_db)):
    available_items = (
        db.query(Inventory).filter(Inventory.status.in_(["In-Stock", "Ready"])).all()
    )
    customers = db.query(Customer).all()
    return templates.TemplateResponse(
        "sales.html",
        {
            "request": request,
            "available_items": available_items,
            "customers": customers,
        },
    )


@router.get("/ledger")
def view_ledger(request: Request, db: Session = Depends(get_db)):
    # Fetch sales where there is a remaining balance
    pending_sales = db.query(Sale).all()
    # Filter in Python to handle the balance calculation easily
    unpaid = [s for s in pending_sales if (s.total_amount - s.amount_paid) > 0.01]
    return templates.TemplateResponse(
        "ledger.html", {"request": request, "pending_sales": unpaid}
    )


@router.post("/process-sale")
def process_sale(
    customer_name: str = Form(...),
    paid: float = Form(0.0),
    inventory_id: int = Form(...),
    payment_note: str = Form("Initial Payment"),
    db: Session = Depends(get_db),
):
    customer = db.query(Customer).filter(Customer.name == customer_name).first()
    if not customer:
        customer = Customer(name=customer_name)
        db.add(customer)
        db.commit()
        db.refresh(customer)

    item = db.query(Inventory).filter(Inventory.inventory_id == inventory_id).first()
    if not item:
        return RedirectResponse(url="/sales", status_code=303)

    total_bill = item.selling_price or 0.0

    new_sale = Sale(
        customer_id=customer.id,
        sale_date=date.today(),
        total_amount=total_bill,
        amount_paid=paid,
    )
    db.add(new_sale)
    db.commit()
    db.refresh(new_sale)

    # 1. Mark inventory item as sold
    item.status = "Sold"
    item.sale_id = new_sale.id

    # 2. Log initial deposit into permanent PaymentLog audit trail
    if paid > 0:
        initial_log = PaymentLog(
            sale_id=new_sale.id,
            amount_received=paid,
            payment_date=date.today(),
            note=payment_note,
        )
        db.add(initial_log)

    db.commit()
    return RedirectResponse(url="/ledger" if (total_bill - paid) > 0.01 else "/", status_code=303)


@router.post("/update-payment")
def update_payment(
    sale_id: int = Form(...),
    new_payment: float = Form(...),
    payment_note: str = Form("Part Payment"),
    db: Session = Depends(get_db),
):
    sale = db.query(Sale).filter(Sale.id == sale_id).first()
    if sale:
        # 1. Update the running total for the Dashboard
        sale.amount_paid += new_payment

        # 2. Create the permanent log entry
        log_entry = PaymentLog(
            sale_id=sale.id,
            amount_received=new_payment,
            payment_date=date.today(),
            note=payment_note,
        )
        db.add(log_entry)
        db.commit()

    return RedirectResponse(url="/ledger", status_code=303)
