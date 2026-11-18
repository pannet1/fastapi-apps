import io
import json
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd
from fastapi import FastAPI, File, Form, HTTPException, Query, Request, UploadFile
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
MASTER_FILE = str((BASE_DIR.parent / "data" / "master_transactions.csv").resolve())
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

    df["_parsed_date"] = pd.to_datetime(df["Tran Date"], dayfirst=True, errors="coerce")
    df["_row_index"] = df.index
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

    filtered_df = filtered_df.sort_values(by=["_parsed_date", "_row_index"], ascending=[False, False])

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
async def view_transactions(
    request: Request,
    page: int = 1,
    size: int = 20,
    category: Optional[str] = Query(None),
    period: Optional[str] = Query(None),
    month: Optional[int] = Query(None),
    year: Optional[int] = Query(None),
    q: Optional[str] = Query(None),
):
    initialize_master()
    df = pd.read_csv(MASTER_FILE)

    # Retain the exact original row index in master CSV file for updates
    df["_row_index"] = df.index

    # Parse dates for filtering and period grouping
    df["_parsed_date"] = pd.to_datetime(df["Tran Date"], dayfirst=True, errors="coerce")

    # Handle combined period string (e.g. "2026-11") from form dropdown
    if period and str(period).strip():
        try:
            parts = str(period).strip().split("-")
            if len(parts) == 2:
                year = int(parts[0])
                month = int(parts[1])
        except Exception:
            pass

    # Extract available statement periods for filter dropdown
    available_periods = []
    valid_dates = df["_parsed_date"].dropna()
    if not valid_dates.empty:
        for (y, m), grp in df.groupby([df["_parsed_date"].dt.year, df["_parsed_date"].dt.month], sort=False):
            if pd.notna(y) and pd.notna(m):
                available_periods.append({
                    "year": int(y),
                    "month": int(m),
                    "val": f"{int(y)}-{int(m):02d}",
                    "label": datetime(int(y), int(m), 1).strftime("%B %Y"),
                    "count": len(grp),
                })
        available_periods.sort(key=lambda x: (x["year"], x["month"]), reverse=True)

    filtered_df = df.copy()

    # 1. Filter by category
    if category and str(category).strip():
        cat_clean = str(category).strip()
        if cat_clean.lower() == "uncategorized":
            cat_mask = (
                filtered_df["Category"].isna()
                | filtered_df["Category"].astype(str).str.strip().str.lower().isin(["uncategorized", "", "none", "nan"])
            )
        else:
            cat_mask = filtered_df["Category"].astype(str).str.strip().str.lower() == cat_clean.lower()
        filtered_df = filtered_df[cat_mask]

    # 2. Filter by month and year
    if month is not None and year is not None:
        date_mask = (filtered_df["_parsed_date"].dt.month == month) & (filtered_df["_parsed_date"].dt.year == year)
        filtered_df = filtered_df[date_mask]
    elif year is not None:
        date_mask = filtered_df["_parsed_date"].dt.year == year
        filtered_df = filtered_df[date_mask]

    # 3. Filter by search query q
    if q and str(q).strip():
        q_clean = str(q).strip()
        text_mask = filtered_df["Particulars"].astype(str).str.contains(q_clean, case=False, na=False)
        filtered_df = filtered_df[text_mask]

    # Sort everything to latest first
    filtered_df = filtered_df.sort_values(by=["_parsed_date", "_row_index"], ascending=[False, False])

    total_rows = len(filtered_df)

    # Compute net spent / received on the filtered subset
    debit_sum = pd.to_numeric(filtered_df["Debit"], errors="coerce").fillna(0).sum()
    credit_sum = pd.to_numeric(filtered_df["Credit"], errors="coerce").fillna(0).sum()
    if category and str(category).strip().lower() == "income":
        net_spent = credit_sum - debit_sum
    else:
        net_spent = debit_sum - credit_sum

    start = (page - 1) * size
    end = start + size
    paginated_df = filtered_df.iloc[start:end]

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
            "total_rows": total_rows,
            "today_date": datetime.now().strftime("%Y-%m-%d"),
            "current_category": category or "",
            "current_month": month,
            "current_year": year,
            "current_period": f"{year}-{month:02d}" if (year and month) else "",
            "current_q": q or "",
            "filter_debit": debit_sum,
            "filter_credit": credit_sum,
            "filter_net": net_spent,
            "available_periods": available_periods,
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
async def index(
    request: Request,
    month: Optional[int] = Query(None),
    year: Optional[int] = Query(None),
    period: Optional[str] = Query(None),
):
    initialize_master()
    df = pd.read_csv(MASTER_FILE)
    budgets = get_categories()

    df["Tran Date"] = pd.to_datetime(df["Tran Date"], dayfirst=True, errors="coerce")
    valid_dates = df["Tran Date"].dropna()

    # Extract available statement periods for selector
    available_periods = []
    if not valid_dates.empty:
        for (y, m), grp in df.groupby([df["Tran Date"].dt.year, df["Tran Date"].dt.month], sort=False):
            if pd.notna(y) and pd.notna(m):
                available_periods.append({
                    "year": int(y),
                    "month": int(m),
                    "val": f"{int(y)}-{int(m):02d}",
                    "label": datetime(int(y), int(m), 1).strftime("%B %Y"),
                    "count": len(grp),
                })
        available_periods.sort(key=lambda x: (x["year"], x["month"]), reverse=True)

    # Compute all-time totals across all master transactions
    all_time_report = {}
    for cat in budgets.keys():
        cat_all = df[df["Category"].astype(str).str.strip().str.lower() == str(cat).strip().lower()]
        if cat.lower() == "income":
            all_time_report[cat] = float(cat_all["Credit"].sum() - cat_all["Debit"].sum())
        else:
            all_time_report[cat] = float(cat_all["Debit"].sum())

    # Determine period selection:
    # 1. period="all" -> All Time statement total
    # 2. period="YYYY-MM" -> specific statement month
    # 3. month & year explicitly passed -> specific statement month
    # 4. Default: All Time statement total so cards reflect the true cumulative spendings
    is_all_time = False
    if period:
        p_clean = str(period).strip().lower()
        if p_clean in ["all", "all time", "all_time"]:
            is_all_time = True
            month = None
            year = None
        else:
            try:
                parts = p_clean.split("-")
                if len(parts) == 2:
                    year = int(parts[0])
                    month = int(parts[1])
            except Exception:
                pass
    elif month is None and year is None:
        is_all_time = True

    if is_all_time:
        active_df = df.copy()
        current_date = "All Time (Statement Total)"
        current_period = "all"
        current_month = None
        current_year = None
        latest_m = available_periods[0]["month"] if available_periods else 11
        latest_y = available_periods[0]["year"] if available_periods else 2026
        nav = {
            "has_prev": len(available_periods) > 0,
            "prev_url": f"/?month={latest_m}&year={latest_y}",
            "prev_label": f"Latest Month ({available_periods[0]['label']})" if available_periods else "Latest Month",
            "has_next": False,
            "next_url": "#",
            "next_label": "",
            "prev_m": latest_m,
            "prev_y": latest_y,
            "next_m": latest_m,
            "next_y": latest_y,
        }
    else:
        if month is None or year is None:
            if available_periods:
                month = available_periods[0]["month"]
                year = available_periods[0]["year"]
            else:
                now = datetime.now()
                month = now.month
                year = now.year

        current_month = month
        current_year = year
        current_period = f"{year}-{month:02d}"
        current_date = datetime(year, month, 1).strftime("%B %Y")
        active_df = df[
            (df["Tran Date"].dt.month == month) & (df["Tran Date"].dt.year == year)
        ].copy()

        # Step through available periods sorted latest-first [2026-11, 2026-10, ...]
        cur_idx = None
        for i, p in enumerate(available_periods):
            if p["year"] == year and p["month"] == month:
                cur_idx = i
                break

        if cur_idx is not None:
            # Prev in time (older month) is cur_idx + 1
            has_prev = (cur_idx + 1) < len(available_periods)
            prev_p = available_periods[cur_idx + 1] if has_prev else None
            prev_url = f"/?month={prev_p['month']}&year={prev_p['year']}" if prev_p else "#"
            prev_label = prev_p["label"] if prev_p else ""
            prev_m = prev_p["month"] if prev_p else month
            prev_y = prev_p["year"] if prev_p else year

            # Next in time (newer month towards latest, or back to All Time if on latest)
            if cur_idx == 0:
                has_next = True
                next_url = "/?period=all"
                next_label = "All Time"
                next_m = month
                next_y = year
            else:
                has_next = (cur_idx - 1) >= 0
                next_p = available_periods[cur_idx - 1] if has_next else None
                next_url = f"/?month={next_p['month']}&year={next_p['year']}" if next_p else "#"
                next_label = next_p["label"] if next_p else ""
                next_m = next_p["month"] if next_p else month
                next_y = next_p["year"] if next_p else year
        else:
            prev_m = month - 1 if month > 1 else 12
            prev_y = year if month > 1 else year - 1
            next_m = month + 1 if month < 12 else 1
            next_y = year if month < 12 else year + 1
            has_prev = True
            has_next = True
            prev_url = f"/?month={prev_m}&year={prev_y}"
            next_url = f"/?month={next_m}&year={next_y}"
            prev_label = f"{prev_m}/{prev_y}"
            next_label = f"{next_m}/{next_y}"

        nav = {
            "has_prev": has_prev,
            "prev_url": prev_url,
            "prev_label": prev_label,
            "has_next": has_next,
            "next_url": next_url,
            "next_label": next_label,
            "prev_m": prev_m,
            "prev_y": prev_y,
            "next_m": next_m,
            "next_y": next_y,
        }

    active_df["Debit"] = pd.to_numeric(active_df["Debit"], errors="coerce").fillna(0)
    active_df["Credit"] = pd.to_numeric(active_df["Credit"], errors="coerce").fillna(0)

    actual_report = {}
    for cat in budgets.keys():
        cat_df = active_df[active_df["Category"].astype(str).str.strip().str.lower() == str(cat).strip().lower()]

        if cat.lower() == "income":
            # For Income envelope, net earned = Inflow Credit - Outflow Debit
            actual_report[cat] = float(cat_df["Credit"].sum() - cat_df["Debit"].sum())
        else:
            # For Expense envelopes (Business, Home, etc.), spendings are Debits
            actual_report[cat] = float(cat_df["Debit"].sum())

    # Uncategorized spending check for this active view
    uncat_mask = (
        active_df["Category"].isna()
        | active_df["Category"].astype(str).str.strip().str.lower().isin(["uncategorized", "", "none", "nan"])
    )
    uncat_df = active_df[uncat_mask]
    uncat_spent = float(uncat_df["Debit"].sum())
    uncat_count = len(uncat_df)

    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "report": actual_report,
            "all_time_report": all_time_report,
            "budgets": budgets,
            "current_date": current_date,
            "current_month": current_month,
            "current_year": current_year,
            "current_period": current_period,
            "is_all_time": is_all_time,
            "available_periods": available_periods,
            "uncat_spent": uncat_spent,
            "uncat_count": uncat_count,
            "categories": list(budgets.keys()),
            "today_date": datetime.now().strftime("%Y-%m-%d"),
            "nav": nav,
        },
    )


def parse_bank_statement_csv(content: bytes) -> pd.DataFrame:
    """
    Parses bank statement CSV uploads (including raw Axis Bank statements with metadata headers,
    disclaimer footers, and varying column names) as well as pre-cleaned CSVs.
    Returns normalized DataFrame with columns:
    ['Tran Date', 'Particulars', 'Debit', 'Credit', 'Balance', 'Category']
    """
    text = None
    for enc in ["utf-8", "utf-8-sig", "latin1", "cp1252"]:
        try:
            text = content.decode(enc)
            break
        except UnicodeDecodeError:
            continue
    if text is None:
        text = content.decode("utf-8", errors="ignore")

    lines = text.splitlines()

    # Search for the table header row
    header_idx = None
    for i, line in enumerate(lines[:60]):
        low = line.lower()
        if "tran date" in low or ("date" in low and any(k in low for k in ["particular", "narration", "description", "dr", "cr", "debit"])):
            header_idx = i
            break

    if header_idx is not None:
        table_lines = [lines[header_idx]]
        for line in lines[header_idx + 1:]:
            s = line.strip()
            if not s:
                break
            if s.startswith('"') and not ("," in s and not s.endswith('"')):
                # Bank disclaimer or legend quote line
                break
            if "statement of account" in s.lower() or "registered office" in s.lower():
                break
            table_lines.append(line)
        csv_str = "\n".join(table_lines)
    else:
        csv_str = text

    try:
        df = pd.read_csv(io.StringIO(csv_str))
    except Exception as e:
        raise ValueError(f"Could not parse CSV content: {e}")

    # Map column variations
    col_map = {}
    for col in df.columns:
        c_clean = str(col).strip().lower()
        if c_clean in ["tran date", "transaction date", "txn date", "date", "value date"]:
            col_map[col] = "Tran Date"
        elif c_clean in ["particulars", "particular", "description", "narration", "details", "remarks"]:
            col_map[col] = "Particulars"
        elif c_clean in ["dr", "debit", "debit amount", "withdrawal", "dr amount"]:
            col_map[col] = "Debit"
        elif c_clean in ["cr", "credit", "credit amount", "deposit", "cr amount"]:
            col_map[col] = "Credit"
        elif c_clean in ["bal", "balance", "closing balance", "net balance"]:
            col_map[col] = "Balance"
        elif c_clean in ["category"]:
            col_map[col] = "Category"

    df = df.rename(columns=col_map)

    if "Tran Date" not in df.columns or "Particulars" not in df.columns:
        raise ValueError("Uploaded CSV must contain Tran Date and Particulars columns")

    for req in ["Debit", "Credit", "Balance"]:
        if req not in df.columns:
            df[req] = None

    if "Category" not in df.columns:
        df["Category"] = "Uncategorized"

    # Filter out empty or repeated header rows
    df = df[df["Tran Date"].notna() & df["Particulars"].notna()]
    df = df[~df["Tran Date"].astype(str).str.lower().str.contains("date")]

    # Normalize fields
    df["Tran Date"] = df["Tran Date"].astype(str).str.strip()
    df["Particulars"] = df["Particulars"].apply(lambda v: re.sub(r"\s+", " ", str(v)).strip() if pd.notna(v) else "")
    df["Debit"] = pd.to_numeric(df["Debit"].astype(str).str.replace(",", "").str.strip(), errors="coerce")
    df["Credit"] = pd.to_numeric(df["Credit"].astype(str).str.replace(",", "").str.strip(), errors="coerce")
    df["Balance"] = pd.to_numeric(df["Balance"].astype(str).str.replace(",", "").str.strip(), errors="coerce")

    return df[["Tran Date", "Particulars", "Debit", "Credit", "Balance", "Category"]]


@app.post("/upload")
async def upload_csv(file: UploadFile = File(...)):
    initialize_master()
    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")

    try:
        new_data = parse_bank_statement_csv(content)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to parse bank statement: {str(e)}")

    if new_data.empty:
        raise HTTPException(status_code=400, detail="No valid transactions found in the CSV file.")

    if os.path.exists(MASTER_FILE):
        master_df = pd.read_csv(MASTER_FILE)
        if not master_df.empty and "Particulars" in master_df.columns:
            master_df["Particulars"] = master_df["Particulars"].apply(
                lambda v: re.sub(r"\s+", " ", str(v)).strip() if pd.notna(v) else ""
            )
    else:
        master_df = pd.DataFrame(columns=["Tran Date", "Particulars", "Debit", "Credit", "Balance", "Category"])

    existing_count = len(master_df)
    updated_master = pd.concat([master_df, new_data]).drop_duplicates(
        subset=["Tran Date", "Particulars"], keep="first"
    )
    added_count = len(updated_master) - existing_count

    updated_master.to_csv(MASTER_FILE, index=False)
    return {
        "message": f"Successfully imported bank statement. {added_count} new transactions merged.",
        "added": added_count,
        "total": len(updated_master),
    }


@app.post("/update-category")
async def update_category_form(row_index: int = Form(...), category: str = Form(...)):
    res = agent_update_category(MASTER_FILE, row_index=row_index, category=category, forward=True)
    return res
