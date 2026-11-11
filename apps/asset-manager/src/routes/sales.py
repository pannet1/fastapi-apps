# path: routes/sales.py
from datetime import date
from typing import Optional, List

from fastapi import APIRouter, Depends, Form, Query, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from starlette.templating import Jinja2Templates

from contacts_service import build_vcard, search_thunderbird_contacts
from database import (
    Customer,
    Inventory,
    PaymentLog,
    Sale,
    get_db,
)

router = APIRouter()
templates = Jinja2Templates(directory="templates")


@router.get("/api/contacts/search")
def api_contact_search(
    q: str = Query("", description="Search term for contacts"),
    db: Session = Depends(get_db),
):
    q_clean = (q or "").strip().lower()
    if not q_clean:
        return {"results": []}

    # 1. Local Database Lookup (filter by python property or vcard)
    all_local = db.query(Customer).all()
    local_matches = [c for c in all_local if q_clean in c.name.lower() or q_clean in c.phone.lower()]
    results_map = {}
    for c in local_matches:
        results_map[c.name.lower()] = {
            "name": c.name,
            "phone": c.phone or "",
            "vcard": c.vcard or "",
            "source": "local",
        }

    # 2. Live Thunderbird Sync
    tb_contacts = search_thunderbird_contacts(q_clean, limit=8)
    for tb in tb_contacts:
        name_key = tb["name"].lower()
        tb_phone = tb.get("phone", "")
        tb_vcard = tb.get("vcard", "")
        if name_key in results_map:
            results_map[name_key]["phone"] = tb_phone or results_map[name_key]["phone"]
            if tb_vcard:
                results_map[name_key]["vcard"] = tb_vcard
        else:
            results_map[name_key] = {
                "name": tb["name"],
                "phone": tb_phone,
                "vcard": tb_vcard,
                "source": "thunderbird",
            }

    return {"results": list(results_map.values())[:8]}


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
    sale_price: float = Form(...),
    paid: float = Form(0.0),
    inventory_id: Optional[int] = Form(None),
    service_description: Optional[str] = Form(None),
    customer_phone: Optional[str] = Form(None),
    customer_vcard: Optional[str] = Form(None),
    payment_note: str = Form("Initial Payment"),
    db: Session = Depends(get_db),
):
    clean_name = customer_name.strip()
    all_customers = db.query(Customer).all()
    customer = next((c for c in all_customers if c.name.lower() == clean_name.lower()), None)

    vcard_payload = (customer_vcard or "").strip()
    if not vcard_payload:
        vcard_payload = build_vcard(clean_name, customer_phone)

    if not customer:
        customer = Customer(vcard=vcard_payload)
        db.add(customer)
        db.commit()
        db.refresh(customer)
    elif customer_vcard and customer_vcard.strip() and customer.vcard != customer_vcard.strip():
        customer.vcard = customer_vcard.strip()
        db.commit()

    total_bill = round(float(sale_price), 2)
    clean_desc = (service_description or "").strip() or None

    new_sale = Sale(
        customer_id=customer.id,
        sale_date=date.today(),
        service_description=clean_desc,
        total_amount=total_bill,
        amount_paid=paid,
    )
    db.add(new_sale)
    db.commit()
    db.refresh(new_sale)

    # 1. If a physical inventory unit was sold, mark as sold and record selling price
    if inventory_id:
        item = db.query(Inventory).filter(Inventory.inventory_id == inventory_id).first()
        if item:
            item.status = "Sold"
            item.sale_id = new_sale.id
            item.selling_price = total_bill

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
