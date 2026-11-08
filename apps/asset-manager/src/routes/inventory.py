# routes/inventory.py
import os
import shutil
from typing import List
from fastapi import APIRouter, Request, Form, Depends, File, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from datetime import datetime
from database import get_db, Batch, Inventory

router = APIRouter()
templates = Jinja2Templates(directory="templates")

# Path configuration
UPLOAD_BASE = "static/inventory_photos"

# --- UTILITY ---

def calculate_price_logic(pp, te, ps):
    """Core math for the selling price"""
    pp = pp or 0.0
    te = te or 0.0
    ps = str(ps or "0").strip()
    
    calc_profit = 0
    try:
        if ps.endswith('%'):
            percentage = float(ps.replace('%', '')) / 100
            calc_profit = pp * percentage
        else:
            calc_profit = float(ps)
    except:
        calc_profit = 0
    return round(pp + te + calc_profit, 2)

# --- BATCH ROUTES ---

@router.get("/batch", response_class=HTMLResponse)
async def batch_view(request: Request, db: Session = Depends(get_db)):
    batches = db.query(Batch).order_by(Batch.id.desc()).all()
    current_date = datetime.now().strftime("%Y-%m-%d")
    return templates.TemplateResponse("batch.html", {
        "request": request, 
        "batches": batches, 
        "current_date": current_date
    })

@router.post("/create-batch")
async def create_batch(
    supplier: str = Form(...), 
    desc: str = Form(...), 
    date_str: str = Form(...), 
    db: Session = Depends(get_db)
):
    date_obj = datetime.strptime(date_str, "%Y-%m-%d").date()
    new_batch = Batch(description=desc, supplier_name=supplier, date=date_obj)
    db.add(new_batch)
    db.commit()
    return RedirectResponse(url="/batch", status_code=303)

# --- INVENTORY LIST & FAST ADD ---

@router.get("/add-items/{batch_pk}", response_class=HTMLResponse)
async def add_items_view(batch_pk: int, request: Request, db: Session = Depends(get_db)):
    batch = db.query(Batch).filter(Batch.id == batch_pk).first()
    items = db.query(Inventory).filter(Inventory.batch_id == batch_pk).all()
    return templates.TemplateResponse("add_items.html", {
        "request": request, 
        "batch": batch, 
        "items": items
    })

@router.post("/save-inventory")
async def save_inventory(
    batch_pk: int = Form(...), 
    brand: str = Form(...), 
    model: str = Form(...),
    serial: str = Form(...), 
    purchase_price: float = Form(...), 
    profit: str = Form(...), 
    db: Session = Depends(get_db)
):
    new_item = Inventory(
        batch_id=batch_pk, 
        brand=brand, 
        model=model,
        serial=serial, 
        purchase_price=purchase_price, 
        intended_profit=profit
    )
    db.add(new_item)
    db.commit()
    return RedirectResponse(url=f"/add-items/{batch_pk}", status_code=303)

# --- ITEM EDIT & PHOTO MANAGEMENT ---

@router.get("/edit-item/{item_id}", response_class=HTMLResponse)
async def edit_item_view(item_id: int, request: Request, db: Session = Depends(get_db)):
    item = db.query(Inventory).filter(Inventory.inventory_id == item_id).first()
    
    # Filesystem check for photos
    item_dir = os.path.join(UPLOAD_BASE, str(item_id))
    photos = []
    if os.path.exists(item_dir):
        # Sort files numerically: 1.jpg, 2.jpg...
        photos = sorted(os.listdir(item_dir), key=lambda x: int(os.path.splitext(x)[0]) if x.split('.')[0].isdigit() else x)
    
    suggested_price = item.selling_price if item.selling_price is not None else \
                      calculate_price_logic(item.purchase_price, item.total_expenses, item.intended_profit)
    
    return templates.TemplateResponse("edit_item.html", {
        "request": request, 
        "item": item, 
        "suggested_price": suggested_price,
        "photos": photos
    })

@router.post("/update-item")
async def update_item(
    item_id: int = Form(...),
    brand: str = Form(...),
    model: str = Form(...),
    serial: str = Form(...),
    purchase_price: float = Form(...),
    total_expenses: float = Form(...),
    profit: str = Form(...),
    selling_price: float = Form(...),
    status: str = Form(...),
    description: str = Form(None),
    photos: List[UploadFile] = File(None),
    db: Session = Depends(get_db)
):
    item = db.query(Inventory).filter(Inventory.inventory_id == item_id).first()
    
    # Update Database Fields
    item.brand = brand
    item.model = model
    item.serial = serial
    item.purchase_price = purchase_price
    item.total_expenses = total_expenses
    item.intended_profit = profit
    item.selling_price = selling_price
    item.status = status
    item.description_for_ecommerce = description

    # Handle Multi-Photo Upload to Filesystem
    if photos:
        item_dir = os.path.join(UPLOAD_BASE, str(item_id))
        os.makedirs(item_dir, exist_ok=True)
        
        for photo in photos:
            if photo.filename:
                # Count current files to determine the next number
                current_files = os.listdir(item_dir)
                next_num = len(current_files) + 1
                
                ext = os.path.splitext(photo.filename)[1]
                file_path = os.path.join(item_dir, f"{next_num}{ext}")
                
                with open(file_path, "wb") as buffer:
                    shutil.copyfileobj(photo.file, buffer)
    
    db.commit()
    return RedirectResponse(url=f"/edit-item/{item_id}", status_code=303)

@router.post("/delete-photo/{item_id}/{filename}")
async def delete_photo(item_id: int, filename: str):
    """Deletes a specific photo from the item's folder"""
    file_path = os.path.join(UPLOAD_BASE, str(item_id), filename)
    if os.path.exists(file_path):
        os.remove(file_path)
    
    # Optional: Logic to 're-gap' files (e.g., if you delete 2.jpg, rename 3.jpg to 2.jpg)
    # can be added here if you want to keep the sequence strictly gapless.
    
    return RedirectResponse(url=f"/edit-item/{item_id}", status_code=303)

@router.get("/all-items", response_class=HTMLResponse)
async def all_items_view(request: Request, db: Session = Depends(get_db)):
    # Query all inventory, latest first (highest ID)
    # We order by inventory_id desc to show latest added items first
    items = db.query(Inventory).order_by(Inventory.inventory_id.desc()).all()
    
    return templates.TemplateResponse("all_items.html", {
        "request": request,
        "items": items
    })   
