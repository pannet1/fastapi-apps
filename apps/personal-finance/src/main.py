import json
import os
import re
from datetime import datetime

import pandas as pd
from fastapi import FastAPI, File, Form, Request, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

MASTER_FILE = "master_transactions.csv"
# Define your envelope budget categories

CATEGORIES_FILE = "categories.json"


@app.get("/settings", response_class=HTMLResponse)
async def settings_page(request: Request):
    categories = get_categories()
    return templates.TemplateResponse(
        "settings.html", {"request": request, "categories": categories}
    )


@app.post("/add-category")
async def add_category(request: Request):
    # Parse form data manually since we have dynamic fields
    form_data = await request.form()
    categories = {}

    # 1. Rebuild categories from the existing inputs
    for key, value in form_data.items():
        if key.startswith("budget_"):
            cat_name = key.replace("budget_", "")
            categories[cat_name] = float(value) if value else 0.0

    # 2. Add the new envelope if provided
    new_name = form_data.get("new_name")
    new_budget = form_data.get("new_budget")
    if new_name and new_name.strip():
        categories[new_name.strip()] = float(new_budget) if new_budget else 0.0

    # 3. Save to JSON
    with open(CATEGORIES_FILE, "w") as f:
        json.dump(categories, f)

    # Redirect back to settings page
    return RedirectResponse(url="/settings", status_code=303)


def get_categories():
    if not os.path.exists(CATEGORIES_FILE):
        return {"Uncategorized": 0}
    with open(CATEGORIES_FILE, "r") as f:
        return json.load(f)


@app.get("/transactions", response_class=HTMLResponse)
async def view_transactions(request: Request, page: int = 1, size: int = 20):
    df = pd.read_csv(MASTER_FILE)

    # Pagination logic
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
            "total_pages": (total_rows // size) + 1,
            "start_index": start,
        },
    )


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


@app.get("/", response_class=HTMLResponse)
async def index(request: Request, month: int = None, year: int = None):
    initialize_master()
    df = pd.read_csv(MASTER_FILE)
    budgets = get_categories()

    now = datetime.now()
    month = month or now.month
    year = year or now.year

    df["Tran Date"] = pd.to_datetime(df["Tran Date"], dayfirst=True, errors="coerce")
    month_df = df[
        (df["Tran Date"].dt.month == month) & (df["Tran Date"].dt.year == year)
    ].copy()

    # Fill NaNs with 0 for calculation
    month_df["Debit"] = month_df["Debit"].fillna(0)
    month_df["Credit"] = month_df["Credit"].fillna(0)

    actual_report = {}
    for cat in budgets.keys():
        cat_df = month_df[month_df["Category"] == cat]

        if cat.lower() == "income":
            # Income = Credits - Debits
            actual_report[cat] = cat_df["Credit"].sum() - cat_df["Debit"].sum()
        else:
            # Expenses = Debits - Credits
            actual_report[cat] = cat_df["Debit"].sum() - cat_df["Credit"].sum()

    # Prepare navigation dates
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
            "nav": {
                "prev_m": prev_month,
                "prev_y": prev_year,
                "next_m": next_month,
                "next_y": next_year,
            },
        },
    )

    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "report": actual_report,
            "budgets": budgets,
            "current_date": datetime(year, month, 1).strftime("%B %Y"),
            "nav": nav_dict,
        },
    )


@app.post("/upload")
async def upload_csv(file: UploadFile = File(...)):
    # Read the incoming raw CSV
    new_data = pd.read_csv(file.file)

    # 1. Remove unnecessary columns as requested
    # These match the headers in your statement: "Chq No" and "Init. Br"
    cols_to_remove = ["Chq No", "Init. Br"]
    new_data = new_data.drop(
        columns=[c for c in cols_to_remove if c in new_data.columns]
    )

    # 2. Prepare for merging
    if os.path.exists(MASTER_FILE):
        master_df = pd.read_csv(MASTER_FILE)
    else:
        master_df = pd.DataFrame()

    # 3. Add Category column if it's a new master file
    if "Category" not in new_data.columns:
        new_data["Category"] = "Uncategorized"

    # 4. Merge and remove duplicates
    # We use Tran Date and Particulars to identify unique transactions
    updated_master = pd.concat([master_df, new_data]).drop_duplicates(
        subset=["Tran Date", "Particulars"], keep="first"
    )

    updated_master.to_csv(MASTER_FILE, index=False)
    return {"message": "Master file updated successfully"}


def extract_vendor(particulars):
    """
    Extracts the vendor name from UPI strings.
    Example: 'UPI/P2M/532510885855/SVS DAILY FRESH /UPI/YES BANK' -> 'SVS DAILY FRESH'
    """
    parts = particulars.split("/")
    if len(parts) > 3:
        # Usually the 4th element in these strings is the vendor name
        return parts[3].strip()
    return particulars.strip()


@app.post("/update-category")
async def update_category(row_index: int = Form(...), category: str = Form(...)):
    df = pd.read_csv(MASTER_FILE)

    # Get the details of the row being manually updated
    target_row = df.iloc[row_index]
    target_vendor = extract_vendor(target_row["Particulars"])
    target_date = pd.to_datetime(target_row["Tran Date"], dayfirst=True)

    # Convert the date column to datetime for comparison
    df["temp_date"] = pd.to_datetime(df["Tran Date"], dayfirst=True)

    # Rule: Forward only (date >= target_date) AND similar vendor
    # We use a simple lambda to check if the vendor name exists in the particulars
    mask = (df["temp_date"] >= target_date) & (
        df["Particulars"].str.contains(re.escape(target_vendor), case=False, na=False)
    )

    # Update the category for all matches
    df.loc[mask, "Category"] = category

    # Clean up and save
    df = df.drop(columns=["temp_date"])
    df.to_csv(MASTER_FILE, index=False)

    return {
        "message": f"Updated {mask.sum()} similar transactions forward from {target_row['Tran Date']}"
    }
