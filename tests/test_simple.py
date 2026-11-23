from fastapi.testclient import TestClient
from main import app

client = TestClient(app)

def test_marketplace_home():
    resp = client.get("/")
    assert resp.status_code == 200
    assert "FastAPI App Marketplace" in resp.text
    assert "Asset Manager" in resp.text
    assert "Personal Finance" in resp.text


def test_asset_manager_mounted():
    # Asset Manager Dashboard HTML
    dash = client.get("/asset-manager/")
    assert dash.status_code == 200
    assert "text/html" in dash.headers.get("content-type", "")
    assert "Back to Marketplace Hub" in dash.text
    assert "/asset-manager/batch" in dash.text

    # Batches page
    batch = client.get("/asset-manager/batch")
    assert batch.status_code == 200

    # Manual page
    manual = client.get("/asset-manager/manual")
    assert manual.status_code == 200

    # All items page
    items = client.get("/asset-manager/all-items")
    assert items.status_code == 200

    # Sales page
    sales = client.get("/asset-manager/sales")
    assert sales.status_code == 200

    # Ledger page
    ledger = client.get("/asset-manager/ledger")
    assert ledger.status_code == 200

    # Assets list page
    assets = client.get("/asset-manager/assets-list")
    assert assets.status_code == 200


def test_personal_finance_mounted():
    # Personal Finance Dashboard HTML
    fin = client.get("/personal-finance/")
    assert fin.status_code == 200
    assert "text/html" in fin.headers.get("content-type", "")
    assert "Back to Marketplace Hub" in fin.text

    # Settings page
    settings = client.get("/personal-finance/settings")
    assert settings.status_code == 200

    # Transactions page
    txs = client.get("/personal-finance/transactions")
    assert txs.status_code == 200

    # Verify home page envelope view links include category filter parameters
    assert "/personal-finance/transactions?category=" in fin.text

    # Category filtered transactions page
    cat_txs = client.get("/personal-finance/transactions?category=Beverages&month=1&year=2026")
    assert cat_txs.status_code == 200
    assert "Beverages" in cat_txs.text
    assert "Active Filter:" in cat_txs.text

    # Uncategorized filter
    uncat_txs = client.get("/personal-finance/transactions?category=Uncategorized")
    assert uncat_txs.status_code == 200
    assert "Uncategorized" in uncat_txs.text


def test_personal_finance_envelope_budget_and_category_filtering():
    # 1. Home page envelope cards default to latest month (November 2026)
    fin = client.get("/personal-finance/")
    assert fin.status_code == 200
    assert "November 2026" in fin.text
    # Link for Business is scoped to the active monthly period
    assert 'href="/personal-finance/transactions?category=Business&period=2026-11"' in fin.text
    # Spent amount for Business is monthly debit (₹816.50) vs monthly budget (₹10,000.00)
    assert "Business" in fin.text
    assert "₹10,000.00" in fin.text  # Budget
    assert "remaining" in fin.text  # Under budget for the month

    # 2. Uncategorized spending alert card links to filtered month
    assert "Uncategorized Spending (November 2026)" in fin.text
    assert "13 Transactions" in fin.text
    assert "₹4,388.00" in fin.text
    assert 'href="/personal-finance/transactions?category=Uncategorized&period=2026-11"' in fin.text

    # 3. View filtered uncategorized transactions directly
    uncat_nov = client.get("/personal-finance/transactions?category=Uncategorized&period=2026-11")
    assert uncat_nov.status_code == 200
    assert "13 matched" in uncat_nov.text
    assert 'id="tx-total-rows-num">13</span> transactions' in uncat_nov.text
    assert "Total Net Spending:" in uncat_nov.text

    # 4. View Business transactions scoped to month
    biz_nov = client.get("/personal-finance/transactions?category=Business&period=2026-11")
    assert biz_nov.status_code == 200
    assert '<option value="Business" selected>Business</option>' in biz_nov.text

    # 5. All Time statement view via ?period=all
    all_time = client.get("/personal-finance/?period=all")
    assert all_time.status_code == 200
    assert "All Time (Statement Total)" in all_time.text
    assert 'href="/personal-finance/transactions?category=Business"' in all_time.text


def test_personal_finance_latest_first_sorting():
    # 1. Home page defaults to latest active monthly period
    fin = client.get("/personal-finance/")
    assert fin.status_code == 200
    assert "November 2026" in fin.text
    assert "Business" in fin.text
    assert "remaining" in fin.text

    # 2. All Time view reflects statement cumulative total
    all_resp = client.get("/personal-finance/?period=all")
    assert all_resp.status_code == 200
    assert "All Time (Statement Total)" in all_resp.text
    assert "Over by" in all_resp.text

    # 2. Monthly period view (e.g. November 2026)
    m_nov = client.get("/personal-finance/?period=2026-11")
    assert m_nov.status_code == 200
    assert "November 2026" in m_nov.text
    assert "month=10&amp;year=2026" in m_nov.text or "month=10&year=2026" in m_nov.text
    assert "Statement Total:" in m_nov.text

    # 2. Transactions table displays latest date first (November 2026 transactions at the top)
    tx_resp = client.get("/personal-finance/transactions")
    assert tx_resp.status_code == 200
    assert "18-11-2026" in tx_resp.text
    # 18-11-2026 appears before older transactions
    idx_latest = tx_resp.text.find("18-11-2026")
    idx_old = tx_resp.text.find("05-11-2025")
    assert idx_latest != -1
    # 05-11-2025 should not be on page 1 of latest-first transactions
    assert idx_old == -1

    # 3. Business filtered transactions display latest Business transaction first (sorted latest first)
    biz_resp = client.get("/personal-finance/transactions?category=Business")
    assert biz_resp.status_code == 200
    assert "10-11-2026" in biz_resp.text
    # Oldest 05-11-2025 is not on page 1 of Business transactions
    assert biz_resp.text.find("05-11-2025") == -1


def test_personal_finance_category_update_and_dom_elements():
    # 1. Verify Uncategorized transactions page contains the necessary DOM attributes for instant row removal
    uncat_resp = client.get("/personal-finance/transactions?category=Uncategorized")
    assert uncat_resp.status_code == 200
    assert 'id="tx-tbody"' in uncat_resp.text
    assert 'id="tx-row-' in uncat_resp.text
    assert 'updateCat(' in uncat_resp.text
    assert 'this.value, this)' in uncat_resp.text
    assert 'data-current-cat="Uncategorized"' in uncat_resp.text
    assert 'id="tx-total-matched"' in uncat_resp.text
    assert 'id="tx-total-rows-num"' in uncat_resp.text
    assert 'id="no-tx-row"' in uncat_resp.text

    # 2. Test update-category API response structure and clean up
    import sqlite3
    from pathlib import Path
    db_path = Path(__file__).parent.parent / "apps" / "personal-finance" / "data" / "finance.db"
    assert db_path.exists()
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute("SELECT id, category FROM transactions ORDER BY id ASC LIMIT 1")
    row = cur.fetchone()
    test_id = row[0] if row else 1
    orig_cat = row[1] if row else "Uncategorized"
    conn.close()
    try:
        res = client.post("/personal-finance/update-category", data={"row_index": test_id, "category": "TestingTemp"})
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "success"
        assert "updated_count" in data
        assert "updated_indices" in data
        assert isinstance(data["updated_indices"], list)
        assert test_id in data["updated_indices"]
        assert "vendor" in data
    finally:
        client.post("/personal-finance/update-category", data={"row_index": test_id, "category": orig_cat})

