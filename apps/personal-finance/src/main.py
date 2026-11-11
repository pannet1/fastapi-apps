import json
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd
from fastapi import FastAPI, File, Form, Query, Request, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

from pf_agent_service import (
    add_transaction as agent_add_transaction,
    get_categories as agent_get_categories,
    get_personal_finance_summary,
    update_category as agent_update_category,
)

BASE_DIR = Path(__file__).resolve().parent
MASTER_FILE = str((BASE_DIR / "master_transactions.csv").resolve())
CATEGORIES_FILE = str((BASE_DIR / "categories.json").resolve())

app = FastAPI(title="Personal Finance & Envelope Budget", description="Agent-ready personal finance & envelope budget manager")
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")


def get_categories():
    return agent_get_categories(CATEGORIES_FILE)


def initialize_master():
    if not os.path.exists(MASTER_FILE):
        df = pd.DataFrame(
            columns=[
                "Tran Date",
                "Particulars",
                "Debit",
                "Credit",
                "Balance",
                "Category",
            ]
        )
        df.to_csv(MASTER_FILE, index=False)


# -------------------------------------------------------------
# Agent & Machine-Readable API Routes
# -------------------------------------------------------------
@app.get("/agent")
def redirect_agent_hub():
    return RedirectResponse(url="/agent", status_code=303)


@app.get("/api/agent/summary")
def agent_summary(
    month: Optional[int] = Query(None, description="Month (1-12). If omitted, defaults to latest month with data."),
    year: Optional[int] = Query(None, description="Year (e.g. 2026). If omitted, defaults to latest year with data."),
    format: str = Query("json", description="Output format: 'json' or 'markdown'"),
):
    """
    Agent endpoint: Extracts structured or markdown summary of personal finance envelopes,
    cashflow, top expenses, and uncategorized items.
    """
    initialize_master()
    res = get_personal_finance_summary(MASTER_FILE, CATEGORIES_FILE, month=month, year=year, fmt=format)
    if format == "markdown":
        return res["markdown"]
    return res


@app.get("/api/agent/categories")
def agent_categories():
    """Agent endpoint: Returns all envelope categories and budgeted targets."""
    return {"categories": get_categories()}


@app.get("/api/agent/transactions")
def agent_transactions(
    category: Optional[str] = Query(None, description="Filter by category"),
    uncategorized_only: bool = Query(False, description="Filter only uncategorized transactions"),
    q: Optional[str] = Query(None, description="Search term in particulars"),
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=500),
):
    """Agent endpoint: Search and filter raw personal finance transactions."""
    initialize_master()
    df = pd.read_csv(MASTER_FILE)
    if df.empty:
        return {"total": 0, "transactions": []}

    filtered_df = df.copy()
    if uncategorized_only:
        mask = (
            filtered_df["Category"].isna()
            | filtered_df["Category"].astype(str).str.strip().str.lower().isin(["uncategorized", "", "none", "nan"])
        )
        filtered_df = filtered_df[mask]
    elif category:
        filtered_df = filtered_df[filtered_df["Category"].astype(str).str.lower() == category.lower()]

    if q:
        filtered_df = filtered_df[filtered_df["Particulars"].astype(str).str.contains(re.escape(q), case=False, na=False)]

    total = len(filtered_df)
    start = (page - 1) * limit
    paginated = filtered_df.iloc[start:start + limit]

    records = []
    for idx, row in paginated.iterrows():
        records.append({
            "row_index": int(idx),
            "date": str(row["Tran Date"]),
            "particulars": str(row["Particulars"]),
            "debit": float(row["Debit"]) if pd.notnull(row["Debit"]) and row["Debit"] != "" else 0.0,
            "credit": float(row["Credit"]) if pd.notnull(row["Credit"]) and row["Credit"] != "" else 0.0,
            "balance": float(row["Balance"]) if pd.notnull(row["Balance"]) and row["Balance"] != "" else 0.0,
            "category": str(row["Category"]),
        })

    return {
        "total": total,
        "page": page,
        "limit": limit,
        "transactions": records,
    }


class TransactionInput(BaseModel):
    tran_date: str
    particulars: str
    debit: Optional[float] = 0.0
    credit: Optional[float] = 0.0
    category: Optional[str] = "Uncategorized"
    balance: Optional[float] = None


@app.post("/api/agent/transactions")
def api_add_transaction(payload: TransactionInput):
    """Agent/API endpoint: Quickly record a new income or expense transaction."""
    initialize_master()
    res = agent_add_transaction(
        MASTER_FILE,
        tran_date=payload.tran_date,
        particulars=payload.particulars,
        debit=payload.debit or 0.0,
        credit=payload.credit or 0.0,
        category=payload.category or "Uncategorized",
        balance=payload.balance,
    )
    return res


class CategorizeInput(BaseModel):
    row_index: int
    category: str
    forward: bool = True


@app.post("/api/agent/categorize")
def api_categorize(payload: CategorizeInput):
    """Agent/API endpoint: Assign category to an uncategorized transaction."""
    initialize_master()
    res = agent_update_category(
        MASTER_FILE,
        row_index=payload.row_index,
        category=payload.category,
        forward=payload.forward,
    )
    return res


# -------------------------------------------------------------
# Human-Facing UI Routes
# -------------------------------------------------------------
@app.get("/settings", response_class=HTMLResponse)
async def settings_page(request: Request):
    categories = get_categories()
    return templates.TemplateResponse(
        "settings.html", {"request": request, "categories": categories}
    )


@app.post("/add-category")
async def add_category(request: Request):
    form_data = await request.form()
    categories = {}

    for key, value in form_data.items():
        if key.startswith("budget_"):
            cat_name = key.replace("budget_", "")
            categories[cat_name] = float(value) if value else 0.0

    new_name = form_data.get("new_name")
    new_budget = form_data.get("new_budget")
    if new_name and str(new_name).strip():
        categories[str(new_name).strip()] = float(new_budget) if new_budget else 0.0

    with open(CATEGORIES_FILE, "w", encoding="utf-8") as f:
        json.dump(categories, f)

    return RedirectResponse(url="/settings", status_code=303)


@app.get("/transactions", response_class=HTMLResponse)
async def view_transactions(request: Request, page: int = 1, size: int = 20):
    initialize_master()
    df = pd.read_csv(MASTER_FILE)

    total_rows = len(df)
    start = (page - 1) * size
    end = start + size
    paginated_df = df.iloc[start:end]

    categories = get_categories()

    return templates.TemplateResponse(
        "transactions.html",
        {
            "request": request,
            "transactions": paginated_df.to_dict(orient="records"),
            "categories": list(categories.keys()),
            "page": page,
            "total_pages": max(1, (total_rows // size) + (1 if total_rows % size != 0 else 0)),
            "start_index": start,
            "today_date": datetime.now().strftime("%Y-%m-%d"),
        },
    )


@app.post("/transactions/add")
async def handle_human_add_transaction(
    tran_date: str = Form(...),
    particulars: str = Form(...),
    tran_type: str = Form("debit"),
    amount: float = Form(...),
    category: str = Form("Uncategorized"),
):
    """Allows humans to quickly record single transactions via web form."""
    initialize_master()
    debit = amount if tran_type.lower() == "debit" else 0.0
    credit = amount if tran_type.lower() == "credit" else 0.0

    agent_add_transaction(
        MASTER_FILE,
        tran_date=tran_date,
        particulars=particulars,
        debit=debit,
        credit=credit,
        category=category,
    )
    return RedirectResponse(url="/transactions", status_code=303)


@app.get("/", response_class=HTMLResponse)
async def index(request: Request, month: int = None, year: int = None):
    initialize_master()
    df = pd.read_csv(MASTER_FILE)
    budgets = get_categories()

    df["Tran Date"] = pd.to_datetime(df["Tran Date"], dayfirst=True, errors="coerce")
    valid_dates = df["Tran Date"].dropna()

    if month is None or year is None:
        if not valid_dates.empty:
            latest = valid_dates.max()
            month = latest.month
            year = latest.year
        else:
            now = datetime.now()
            month = now.month
            year = now.year

    month_df = df[
        (df["Tran Date"].dt.month == month) & (df["Tran Date"].dt.year == year)
    ].copy()

    month_df["Debit"] = pd.to_numeric(month_df["Debit"], errors="coerce").fillna(0)
    month_df["Credit"] = pd.to_numeric(month_df["Credit"], errors="coerce").fillna(0)

    actual_report = {}
    for cat in budgets.keys():
        cat_df = month_df[month_df["Category"].astype(str).str.lower() == cat.lower()]

        if cat.lower() == "income":
            actual_report[cat] = cat_df["Credit"].sum() - cat_df["Debit"].sum()
        else:
            actual_report[cat] = cat_df["Debit"].sum() - cat_df["Credit"].sum()

    prev_month = month - 1 if month > 1 else 12
    prev_year = year if month > 1 else year - 1
    next_month = month + 1 if month < 12 else 1
    next_year = year if month < 12 else year + 1

    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "report": actual_report,
            "budgets": budgets,
            "current_date": datetime(year, month, 1).strftime("%B %Y"),
            "categories": list(budgets.keys()),
            "today_date": datetime.now().strftime("%Y-%m-%d"),
            "nav": {
                "prev_m": prev_month,
                "prev_y": prev_year,
                "next_m": next_month,
                "next_y": next_year,
            },
        },
    )


@app.post("/upload")
async def upload_csv(file: UploadFile = File(...)):
    new_data = pd.read_csv(file.file)

    cols_to_remove = ["Chq No", "Init. Br"]
    new_data = new_data.drop(
        columns=[c for c in cols_to_remove if c in new_data.columns]
    )

    if os.path.exists(MASTER_FILE):
        master_df = pd.read_csv(MASTER_FILE)
    else:
        master_df = pd.DataFrame()

    if "Category" not in new_data.columns:
        new_data["Category"] = "Uncategorized"

    updated_master = pd.concat([master_df, new_data]).drop_duplicates(
        subset=["Tran Date", "Particulars"], keep="first"
    )

    updated_master.to_csv(MASTER_FILE, index=False)
    return {"message": "Master file updated successfully"}


@app.post("/update-category")
async def update_category_form(row_index: int = Form(...), category: str = Form(...)):
    res = agent_update_category(MASTER_FILE, row_index=row_index, category=category, forward=True)
    return res
