# apps/personal-finance/src/pf_database.py
import re
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
import pandas as pd

BASE_DIR = Path(__file__).resolve().parent
DB_DIR = (BASE_DIR.parent / "data").resolve()
DB_DIR.mkdir(parents=True, exist_ok=True)
DB_PATH = DB_DIR / "finance.db"


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(str(DB_PATH), timeout=15.0)
    conn.row_factory = sqlite3.Row
    return conn


def init_db(*args, **kwargs):
    """Initializes finance.db schema and indexes."""
    conn = get_connection()
    with conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS transactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tran_date TEXT NOT NULL,
                particulars TEXT NOT NULL,
                debit REAL DEFAULT 0.0,
                credit REAL DEFAULT 0.0,
                balance REAL,
                category TEXT DEFAULT 'Uncategorized',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(tran_date, particulars, balance)
            );
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_tx_category ON transactions(category);")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_tx_date ON transactions(tran_date);")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_tx_particulars ON transactions(particulars);")
        conn.execute("""
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT
            );
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS opening_balance (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                amount REAL NOT NULL DEFAULT 0.0,
                as_of_date TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS category_rules (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                vendor TEXT NOT NULL,
                amount REAL,
                category TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
    conn.close()


def get_opening_balance() -> float:
    """Returns the configured opening balance (0.0 if none)."""
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT amount FROM opening_balance ORDER BY id DESC LIMIT 1")
        row = cur.fetchone()
        if row is not None and row["amount"] is not None:
            return float(row["amount"])
        cur.execute("SELECT value FROM settings WHERE key = 'opening_balance'")
        row = cur.fetchone()
        if row is not None and row["value"] is not None:
            try:
                return float(row["value"])
            except (TypeError, ValueError):
                return 0.0
        return 0.0
    finally:
        conn.close()


def set_opening_balance(amount: float, as_of_date: Optional[str] = None) -> Dict[str, Any]:
    """Stores/updates the opening balance used to compute the real account balance."""
    conn = get_connection()
    try:
        with conn:
            conn.execute(
                "INSERT INTO opening_balance (amount, as_of_date) VALUES (?, ?)",
                (round(float(amount), 2), as_of_date),
            )
            conn.execute(
                "INSERT INTO settings (key, value) VALUES ('opening_balance', ?) "
                "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                (str(round(float(amount), 2)),),
            )
            if as_of_date:
                conn.execute(
                    "INSERT INTO settings (key, value) VALUES ('opening_balance_date', ?) "
                    "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                    (str(as_of_date).strip(),),
                )
        return {"status": "success", "opening_balance": round(float(amount), 2), "as_of_date": as_of_date}
    finally:
        conn.close()


def get_category_rules() -> List[Dict[str, Any]]:
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT id, vendor, amount, category, created_at FROM category_rules ORDER BY id ASC")
        rows = cur.fetchall()
        return [
            {
                "id": r["id"],
                "vendor": r["vendor"],
                "amount": (float(r["amount"]) if r["amount"] is not None else None),
                "category": r["category"],
                "created_at": r["created_at"],
            }
            for r in rows
        ]
    finally:
        conn.close()


def add_category_rule(vendor: str, category: str, amount: Optional[float] = None) -> Dict[str, Any]:
    conn = get_connection()
    try:
        with conn:
            cur = conn.cursor()
            cur.execute(
                "INSERT INTO category_rules (vendor, amount, category) VALUES (?, ?, ?)",
                (vendor.strip(), (round(float(amount), 2) if amount is not None else None), category.strip()),
            )
            new_id = cur.lastrowid
        return {"status": "success", "id": new_id, "vendor": vendor.strip(), "amount": amount, "category": category.strip()}
    finally:
        conn.close()


def update_category_rule(rule_id: int, vendor: str, category: str, amount: Optional[float] = None) -> Dict[str, Any]:
    conn = get_connection()
    try:
        with conn:
            conn.execute(
                "UPDATE category_rules SET vendor = ?, amount = ?, category = ? WHERE id = ?",
                (vendor.strip(), (round(float(amount), 2) if amount is not None else None), category.strip(), rule_id),
            )
        return {"status": "success", "id": rule_id, "vendor": vendor.strip(), "amount": amount, "category": category.strip()}
    finally:
        conn.close()


def delete_category_rule(rule_id: int) -> Dict[str, Any]:
    conn = get_connection()
    try:
        with conn:
            conn.execute("DELETE FROM category_rules WHERE id = ?", (rule_id,))
        return {"status": "success", "id": rule_id}
    finally:
        conn.close()


def apply_category_rules() -> Dict[str, Any]:
    """Apply all category rules to currently uncategorized transactions."""
    conn = get_connection()
    try:
        rules = get_category_rules() if False else None
    finally:
        conn.close()
    # Re-open via helper
    rules = get_category_rules()
    updated_total = 0
    for rule in rules:
        vendor = rule["vendor"]
        amount = rule["amount"]
        category = rule["category"]
        conn = get_connection()
        try:
            cur = conn.cursor()
            cur.execute(
                "SELECT id, debit, credit FROM transactions WHERE particulars LIKE ? AND (category IS NULL OR lower(category) IN ('uncategorized','','none','nan'))",
                (f"%{vendor}%",),
            )
            rows = cur.fetchall()
            ids = []
            for r in rows:
                d = float(r["debit"]) if r["debit"] is not None else 0.0
                c = float(r["credit"]) if r["credit"] is not None else 0.0
                amt = d if d else c
                if amount is not None and round(amt, 2) != round(float(amount), 2):
                    continue
                ids.append(r["id"])
            if ids:
                placeholders = ",".join("?" for _ in ids)
                with conn:
                    conn.execute(
                        f"UPDATE transactions SET category = ? WHERE id IN ({placeholders})",
                        [category] + ids,
                    )
                updated_total += len(ids)
        finally:
            conn.close()
    return {"status": "success", "updated_count": updated_total}


def get_transactions_df(conn: Optional[sqlite3.Connection] = None) -> pd.DataFrame:
    """Returns all transactions from SQLite as a DataFrame with standard column names."""
    should_close = False
    if conn is None:
        conn = get_connection()
        should_close = True

    try:
        df = pd.read_sql_query(
            """
            SELECT id, 
                   tran_date AS 'Tran Date', 
                   particulars AS 'Particulars', 
                   debit AS 'Debit', 
                   credit AS 'Credit', 
                   balance AS 'Balance', 
                   category AS 'Category' 
            FROM transactions 
            ORDER BY id ASC
            """,
            conn,
        )
        if df.empty:
            df = pd.DataFrame(columns=["id", "Tran Date", "Particulars", "Debit", "Credit", "Balance", "Category"])
        df["_row_index"] = df["id"]
        return df
    finally:
        if should_close:
            conn.close()


def update_transaction_category(
    row_index: int,
    category: str,
    forward: bool = True,
    amount: Optional[float] = None,
) -> Dict[str, Any]:
    """Updates category for a transaction in SQLite, supporting forward-matching."""
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT id, tran_date, particulars, debit, credit, category FROM transactions WHERE id = ?", (row_index,))
        target = cur.fetchone()

        if target is None:
            # Fallback if 0-based offset was passed
            cur.execute("SELECT id, tran_date, particulars, debit, credit, category FROM transactions LIMIT 1 OFFSET ?", (row_index,))
            target = cur.fetchone()

        if target is None:
            return {"status": "error", "message": f"Transaction with id/index {row_index} not found."}

        target_id = target["id"]
        target_particulars = target["particulars"]
        target_date_str = target["tran_date"]
        target_debit = float(target["debit"]) if target["debit"] is not None else 0.0
        target_credit = float(target["credit"]) if target["credit"] is not None else 0.0
        target_amt = amount if amount is not None else (target_debit if target_debit else target_credit)

        if not forward:
            with conn:
                conn.execute("UPDATE transactions SET category = ? WHERE id = ?", (category, target_id))
            return {
                "status": "success",
                "updated_count": 1,
                "updated_indices": [target_id],
                "category": category,
                "message": f"Updated transaction #{target_id} to {category}",
            }

        def _extract_vendor(parts_str):
            parts = str(parts_str).split("/")
            return parts[3].strip() if len(parts) > 3 else str(parts_str).strip()

        target_vendor = _extract_vendor(target_particulars)
        target_dt = pd.to_datetime(target_date_str, dayfirst=True, errors="coerce")

        cur.execute(
            "SELECT id, tran_date, particulars, debit, credit FROM transactions WHERE particulars LIKE ?",
            (f"%{target_vendor}%",),
        )
        candidates = cur.fetchall()

        # Determine whether this vendor is ambiguous (multiple distinct amounts).
        # If so, an explicitly provided amount narrows the match to that amount.
        distinct_amounts = set()
        for cand in candidates:
            c_debit = float(cand["debit"]) if cand["debit"] is not None else 0.0
            c_credit = float(cand["credit"]) if cand["credit"] is not None else 0.0
            distinct_amounts.add(round(c_debit if c_debit else c_credit, 2))
        amount_filter_active = amount is not None and len(distinct_amounts) > 1

        matched_ids = []
        for cand in candidates:
            cand_debit = float(cand["debit"]) if cand["debit"] is not None else 0.0
            cand_credit = float(cand["credit"]) if cand["credit"] is not None else 0.0
            cand_amt = round(cand_debit if cand_debit else cand_credit, 2)

            if amount_filter_active:
                if round(float(amount), 2) != cand_amt:
                    continue
                # Amount-specific rule applies to all matching transactions (past + future)
                matched_ids.append(cand["id"])
                continue

            cand_dt = pd.to_datetime(cand["tran_date"], dayfirst=True, errors="coerce")
            if pd.notna(target_dt) and pd.notna(cand_dt):
                if cand_dt >= target_dt:
                    matched_ids.append(cand["id"])
            elif cand["id"] == target_id:
                matched_ids.append(cand["id"])

        if not matched_ids:
            matched_ids = [target_id]

        placeholders = ",".join("?" for _ in matched_ids)
        with conn:
            conn.execute(
                f"UPDATE transactions SET category = ? WHERE id IN ({placeholders})",
                [category] + matched_ids,
            )

        return {
            "status": "success",
            "updated_count": len(matched_ids),
            "updated_indices": matched_ids,
            "vendor": target_vendor,
            "category": category,
            "message": f"Updated {len(matched_ids)} transactions matching vendor '{target_vendor}' forward from {target_date_str}",
        }
    finally:
        conn.close()


def add_single_transaction(
    tran_date: str,
    particulars: str,
    debit: float = 0.0,
    credit: float = 0.0,
    category: str = "Uncategorized",
    balance: Optional[float] = None,
) -> Dict[str, Any]:
    """Inserts a single transaction into SQLite."""
    conn = get_connection()
    try:
        cur = conn.cursor()
        if balance is None or pd.isna(balance):
            cur.execute("SELECT balance FROM transactions ORDER BY id DESC LIMIT 1")
            last_row = cur.fetchone()
            last_bal = float(last_row["balance"]) if last_row and last_row["balance"] is not None else 0.0
            balance = round(last_bal + credit - debit, 2)

        try:
            if "-" in tran_date and len(tran_date.split("-")[0]) == 4:
                dt = datetime.strptime(tran_date, "%Y-%m-%d")
                tran_date_str = dt.strftime("%d-%m-%Y")
            else:
                tran_date_str = tran_date
        except Exception:
            tran_date_str = tran_date

        with conn:
            cur.execute(
                """
                INSERT INTO transactions (tran_date, particulars, debit, credit, balance, category)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (tran_date_str.strip(), particulars.strip(), round(float(debit), 2), round(float(credit), 2), round(float(balance), 2), category.strip() if category else "Uncategorized"),
            )
            new_id = cur.lastrowid

        return {
            "status": "success",
            "message": "Transaction added successfully",
            "transaction": {
                "id": new_id,
                "Tran Date": tran_date_str,
                "Particulars": particulars,
                "Debit": debit,
                "Credit": credit,
                "Balance": balance,
                "Category": category,
            },
        }
    finally:
        conn.close()


def bulk_insert_parsed_csv(parsed_df: pd.DataFrame) -> Dict[str, Any]:
    """Bulk inserts transactions from an uploaded statement dataframe directly into SQLite without duplicates."""
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM transactions")
        count_before = cur.fetchone()[0]

        with conn:
            for _, row in parsed_df.iterrows():
                d = float(row["Debit"]) if pd.notna(row.get("Debit")) else 0.0
                c = float(row["Credit"]) if pd.notna(row.get("Credit")) else 0.0
                b = float(row["Balance"]) if pd.notna(row.get("Balance")) else None
                cat = str(row["Category"]).strip() if pd.notna(row.get("Category")) else "Uncategorized"
                cur.execute(
                    """
                    INSERT OR IGNORE INTO transactions (tran_date, particulars, debit, credit, balance, category)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (str(row["Tran Date"]).strip(), str(row["Particulars"]).strip(), d, c, b, cat),
                )

        cur.execute("SELECT COUNT(*) FROM transactions")
        count_after = cur.fetchone()[0]
        added = count_after - count_before
        return {"added": added, "total": count_after}
    finally:
        conn.close()
