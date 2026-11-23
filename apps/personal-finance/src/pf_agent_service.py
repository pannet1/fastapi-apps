import json
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
import pandas as pd

from pf_database import (
    add_category_rule as db_add_category_rule,
    add_single_transaction,
    apply_category_rules as db_apply_category_rules,
    delete_category_rule as db_delete_category_rule,
    get_category_rules as db_get_category_rules,
    get_transaction_details as db_get_transaction_details,
    get_opening_balance as db_get_opening_balance,
    get_transactions_df,
    init_db,
    set_opening_balance as db_set_opening_balance,
    update_category_rule as db_update_category_rule,
    update_transaction_category,
)


def resolve_file(file_path: str, default_name: str) -> Path:
    if not file_path:
        return Path(__file__).resolve().parent / default_name
    p = Path(file_path)
    if p.exists():
        return p.resolve()
    # Check relative to __file__.parent
    cand = Path(__file__).resolve().parent / file_path
    if cand.exists():
        return cand.resolve()
    # Check just the filename in __file__.parent
    cand2 = Path(__file__).resolve().parent / p.name
    if cand2.exists():
        return cand2.resolve()
    return cand.resolve()


def get_categories(categories_file: str) -> Dict[str, float]:
    path = resolve_file(categories_file, "categories.json")
    if not path.exists():
        return {"Uncategorized": 0.0}
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {"Uncategorized": 0.0}


def get_personal_finance_summary(
    master_file: str,
    categories_file: str,
    month: Optional[int] = None,
    year: Optional[int] = None,
    fmt: str = "json",
) -> Dict[str, Any]:
    """
    Computes agent-friendly summary of personal finance envelopes, cashflow, and spending.
    If month/year is omitted, automatically finds the most recent active month with data.
    """
    init_db(master_file)
    budgets = get_categories(categories_file)
    df = get_transactions_df()
    opening_balance = db_get_opening_balance()

    if df.empty:
        empty_res = {
            "period": {"month": month or datetime.now().month, "year": year or datetime.now().year, "label": "No Data"},
            "opening_balance": round(opening_balance, 2),
            "current_balance": round(opening_balance, 2),
            "cashflow": {
                "total_income": 0.0,
                "total_expenses": 0.0,
                "net_savings": 0.0,
                "savings_rate_pct": 0.0,
            },
            "envelopes": [],
            "over_budget_envelopes": [],
            "categorization_health": {"uncategorized_count": 0, "uncategorized_amount": 0.0, "pending": []},
            "top_expenses": [],
            "all_time_totals": {
                "total_income": 0.0,
                "total_expenses": 0.0,
                "net_savings": 0.0,
                "total_transactions": 0,
            },
            "available_periods": [],
        }
        if fmt == "markdown":
            return {"markdown": _format_personal_markdown(empty_res), "data": empty_res}
        return empty_res

    # Parse dates
    df["Tran Date Parsed"] = pd.to_datetime(df["Tran Date"], dayfirst=True, errors="coerce")
    valid_dates = df["Tran Date Parsed"].dropna()

    # Determine period
    if month is None or year is None:
        if not valid_dates.empty:
            latest = valid_dates.max()
            month = latest.month
            year = latest.year
        else:
            now = datetime.now()
            month = now.month
            year = now.year

    period_label = datetime(year, month, 1).strftime("%B %Y")

    # Available periods
    periods = []
    if not valid_dates.empty:
        grouped_p = df.groupby([df["Tran Date Parsed"].dt.year, df["Tran Date Parsed"].dt.month]).size()
        for (y, m), cnt in grouped_p.items():
            if pd.notnull(y) and pd.notnull(m):
                dt = datetime(int(y), int(m), 1)
                periods.append({"year": int(y), "month": int(m), "label": dt.strftime("%B %Y"), "transaction_count": int(cnt)})
        periods.sort(key=lambda x: (x["year"], x["month"]), reverse=True)

    # Filter for selected month
    month_df = df[
        (df["Tran Date Parsed"].dt.month == month) & (df["Tran Date Parsed"].dt.year == year)
    ].copy()

    month_df["Debit"] = pd.to_numeric(month_df["Debit"], errors="coerce").fillna(0.0)
    month_df["Credit"] = pd.to_numeric(month_df["Credit"], errors="coerce").fillna(0.0)

    # Category envelope analysis
    # Include all categories defined in budget, plus any extra categories appearing in month_df
    all_cat_names = list(budgets.keys())
    for c in month_df["Category"].dropna().unique():
        if c not in all_cat_names:
            all_cat_names.append(c)

    envelopes = []
    over_budget_envelopes = []
    total_income = 0.0
    total_expenses = 0.0

    for cat in all_cat_names:
        cat_df = month_df[month_df["Category"].astype(str).str.strip().str.lower() == str(cat).strip().lower()]
        budget_val = float(budgets.get(cat, 0.0))

        if cat.lower() == "income":
            # Net Income = Credit - Debit
            actual = float(cat_df["Credit"].sum() - cat_df["Debit"].sum())
            total_income += actual
            envelopes.append({
                "category": cat,
                "type": "income",
                "budgeted": budget_val,
                "actual": round(actual, 2),
                "variance": round(actual - budget_val, 2),
                "status": "above_target" if actual >= budget_val else "below_target",
            })
        else:
            # Expense spending = Debit
            actual = float(cat_df["Debit"].sum())
            if actual > 0:
                total_expenses += actual
            variance = round(budget_val - actual, 2)
            pct_used = round((actual / budget_val * 100), 1) if budget_val > 0 else (100.0 if actual > 0 else 0.0)

            is_over = actual > budget_val if budget_val > 0 else (actual > 0)
            status = "over_budget" if is_over else "under_budget"

            env_item = {
                "category": cat,
                "type": "expense",
                "budgeted": budget_val,
                "actual": round(actual, 2),
                "variance": variance,
                "percent_used": pct_used,
                "status": status,
            }
            envelopes.append(env_item)

            if is_over and actual > 0:
                over_budget_envelopes.append({
                    "category": cat,
                    "budgeted": budget_val,
                    "actual": round(actual, 2),
                    "over_by": round(actual - budget_val if budget_val > 0 else actual, 2),
                })

    net_savings = round(total_income - total_expenses, 2)
    # Guard against division-by-near-zero distortion (e.g. income < 100 yielding -70,000% savings rate)
    savings_rate = round((net_savings / total_income * 100), 1) if total_income >= 100.0 else 0.0

    # Categorization health
    uncat_mask = (
        month_df["Category"].isna()
        | month_df["Category"].astype(str).str.strip().str.lower().isin(["uncategorized", "", "none", "nan"])
    )
    uncat_df = month_df[uncat_mask].sort_values(by=["Tran Date Parsed"], ascending=False)
    uncat_count = int(len(uncat_df))
    uncat_amount = round(float(uncat_df["Debit"].sum() + uncat_df["Credit"].sum()), 2)

    pending_items = []
    for idx, row in uncat_df.head(10).iterrows():
        pending_items.append({
            "row_index": int(idx),
            "date": str(row["Tran Date"]),
            "particulars": str(row["Particulars"]),
            "debit": float(row["Debit"]),
            "credit": float(row["Credit"]),
        })

    # Top expenses
    top_exp_df = month_df[month_df["Debit"] > 0].sort_values("Debit", ascending=False).head(5)
    top_expenses = [
        {
            "date": str(row["Tran Date"]),
            "particulars": str(row["Particulars"]),
            "amount": float(row["Debit"]),
            "category": str(row["Category"]),
        }
        for _, row in top_exp_df.iterrows()
    ]

    # All-time totals
    all_income = float(
        df[df["Category"].astype(str).str.lower() == "income"]["Credit"].fillna(0).sum()
        - df[df["Category"].astype(str).str.lower() == "income"]["Debit"].fillna(0).sum()
    )
    all_expenses = float(
        df[df["Category"].astype(str).str.lower() != "income"]["Debit"].fillna(0).sum()
        - df[df["Category"].astype(str).str.lower() != "income"]["Credit"].fillna(0).sum()
    )

    total_credits_all = float(pd.to_numeric(df["Credit"], errors="coerce").fillna(0).sum())
    total_debits_all = float(pd.to_numeric(df["Debit"], errors="coerce").fillna(0).sum())
    net_flow_all = total_credits_all - total_debits_all
    current_balance = round(opening_balance + net_flow_all, 2)

    latest_balance = 0.0
    if "Balance" in df.columns:
        bal_series = pd.to_numeric(df["Balance"], errors="coerce").dropna()
        if not bal_series.empty:
            latest_balance = float(bal_series.iloc[-1])

    result = {
        "period": {
            "month": month,
            "year": year,
            "label": period_label,
        },
        "opening_balance": round(opening_balance, 2),
        "current_balance": current_balance,
        "cashflow": {
            "total_income": round(total_income, 2),
            "total_expenses": round(total_expenses, 2),
            "net_savings": net_savings,
            "savings_rate_pct": savings_rate,
        },
        "envelopes": envelopes,
        "over_budget_envelopes": over_budget_envelopes,
        "categorization_health": {
            "uncategorized_count": uncat_count,
            "uncategorized_amount": uncat_amount,
            "pending": pending_items,
        },
        "top_expenses": top_expenses,
        "all_time_totals": {
            "total_income": round(all_income, 2),
            "total_expenses": round(all_expenses, 2),
            "net_savings": round(all_income - all_expenses, 2),
            "total_transactions": len(df),
        },
        "available_periods": periods,
    }

    if fmt == "markdown":
        return {"markdown": _format_personal_markdown(result), "data": result}
    return result


def _format_personal_markdown(summary: Dict[str, Any]) -> str:
    p = summary.get("period", {})
    cf = summary.get("cashflow", {})
    over = summary.get("over_budget_envelopes", [])
    cat_health = summary.get("categorization_health", {})

    lines = [
        f"### 💰 Personal Finance Summary — {p.get('label', 'Current')}",
        f"- **Income**: ₹{cf.get('total_income', 0.0):,.2f}",
        f"- **Expenses**: ₹{cf.get('total_expenses', 0.0):,.2f}",
        f"- **Net Savings**: ₹{cf.get('net_savings', 0.0):,.2f} ({cf.get('savings_rate_pct', 0.0)}% savings rate)",
        f"- **Opening Balance**: ₹{summary.get('opening_balance', 0.0):,.2f}",
        f"- **Current Balance**: ₹{summary.get('current_balance', 0.0):,.2f}",
    ]

    if over:
        lines.append("- **⚠️ Over Budget Envelopes**:")
        for item in over:
            lines.append(f"  - **{item['category']}**: Spent ₹{item['actual']:,.2f} vs Budget ₹{item['budgeted']:,.2f} (+₹{item['over_by']:,.2f} over)")
    else:
        lines.append("- **✅ Budget Status**: All envelopes are within allocated limits.")

    if cat_health.get("uncategorized_count", 0) > 0:
        lines.append(f"- **⚠️ Categorization Needed**: {cat_health['uncategorized_count']} transactions (₹{cat_health['uncategorized_amount']:,.2f}) are uncategorized.")

    return "\n".join(lines)


def add_transaction(
    master_file: str,
    tran_date: str,
    particulars: str,
    debit: float = 0.0,
    credit: float = 0.0,
    category: str = "Uncategorized",
    balance: Optional[float] = None,
) -> Dict[str, Any]:
    """Adds a single transaction row to SQLite database and synchronizes master CSV."""
    init_db(master_file)
    return add_single_transaction(
        tran_date=tran_date,
        particulars=particulars,
        debit=debit,
        credit=credit,
        category=category,
        balance=balance,
    )


def update_category(
    master_file: str,
    row_index: int,
    category: str,
    forward: bool = False,
    amount: Optional[float] = None,
) -> Dict[str, Any]:
    """Updates category for a transaction in SQLite."""
    init_db(master_file)
    return update_transaction_category(row_index=row_index, category=category, forward=forward, amount=amount)


def get_opening_balance(master_file: str) -> float:
    """Returns the configured opening balance."""
    init_db(master_file)
    return db_get_opening_balance()


def set_opening_balance(master_file: str, amount: float, as_of_date: Optional[str] = None) -> Dict[str, Any]:
    """Stores/updates the opening balance used to compute the real account balance."""
    init_db(master_file)
    return db_set_opening_balance(amount, as_of_date)


def get_transaction_details(master_file: str, row_index: int) -> Optional[Dict[str, Any]]:
    init_db(master_file)
    return db_get_transaction_details(row_index)


def _extract_vendor(parts_str: str) -> str:
    parts = str(parts_str).split("/")
    return parts[3].strip() if len(parts) > 3 else str(parts_str).strip()


def create_rule_from_transaction(master_file: str, row_index: int, category: Optional[str] = None) -> Dict[str, Any]:
    init_db(master_file)
    details = db_get_transaction_details(row_index)
    if not details:
        return {"status": "error", "message": "Transaction not found."}
    # Fetch full category from DB
    conn = None
    import sqlite3
    from pf_database import get_connection as _gc
    conn = _gc()
    try:
        cur = conn.cursor()
        cur.execute("SELECT category FROM transactions WHERE id = ?", (details["id"],))
        row = cur.fetchone()
        cat = category or (row["category"] if row else None) or "Uncategorized"
    finally:
        conn.close()
    if cat == "Uncategorized":
        return {"status": "error", "message": "Transaction is not categorized."}
    vendor = _extract_vendor(details["particulars"])
    debit = details["debit"]
    credit = details["credit"]
    amount = debit if debit else credit
    res = db_add_category_rule(vendor, cat, amount if amount else None)
    db_apply_category_rules()
    return {"status": "success", "vendor": vendor, "amount": amount, "category": cat, "rule": res}

def get_category_rules(master_file: str) -> List[Dict[str, Any]]:
    init_db(master_file)
    return db_get_category_rules()


def add_category_rule(master_file: str, vendor: str, category: str, amount: Optional[float] = None) -> Dict[str, Any]:
    init_db(master_file)
    return db_add_category_rule(vendor, category, amount)


def update_category_rule(master_file: str, rule_id: int, vendor: str, category: str, amount: Optional[float] = None) -> Dict[str, Any]:
    init_db(master_file)
    return db_update_category_rule(rule_id, vendor, category, amount)


def delete_category_rule(master_file: str, rule_id: int) -> Dict[str, Any]:
    init_db(master_file)
    return db_delete_category_rule(rule_id)


def apply_category_rules(master_file: str) -> Dict[str, Any]:
    init_db(master_file)
    return db_apply_category_rules()
