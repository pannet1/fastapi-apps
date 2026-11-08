# routes/asset.py
from fastapi import APIRouter, Request, Form, Depends
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from datetime import datetime
from database import get_db, Asset

router = APIRouter()
templates = Jinja2Templates(directory="templates")

@router.get("/assets-list", response_class=HTMLResponse)
async def assets_page(request: Request, db: Session = Depends(get_db)):
    # Fetch all assets sorted by date
    assets = db.query(Asset).order_by(Asset.purchase_date.desc()).all()
    total_value = sum(a.cost for a in assets)
    return templates.TemplateResponse("assets.html", {
        "request": request, 
        "assets": assets, 
        "total_value": total_value
    })

@router.post("/add-asset")
async def handle_add_asset(
    name: str = Form(...), 
    cost: float = Form(...), 
    p_date: str = Form(...),
    db: Session = Depends(get_db)
):
    date_obj = datetime.strptime(p_date, "%Y-%m-%d").date()
    new_asset = Asset(name=name, cost=cost, purchase_date=date_obj)
    db.add(new_asset)
    db.commit()
    # Redirect back to the dedicated assets page
    return RedirectResponse(url="/assets-list", status_code=303)
