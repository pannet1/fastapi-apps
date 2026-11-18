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
    # 1. Home page envelope cards
    fin = client.get("/personal-finance/")
    assert fin.status_code == 200
    # Link for Business must point directly to transactions filtered by Business without month lock
    assert 'href="/personal-finance/transactions?category=Business"' in fin.text
    # Spent amount for Business is counted from actual debits (> 0)
    assert "Business" in fin.text
    assert "₹10,000.00" in fin.text  # Budget

    # 2. View Business transactions
    biz_resp = client.get("/personal-finance/transactions?category=Business")
    assert biz_resp.status_code == 200
    assert "Page 1 of" in biz_resp.text
    assert "49 transactions" in biz_resp.text
    assert '<option value="Business" selected>Business</option>' in biz_resp.text

    # 3. Monthly period filtering
    m_resp = client.get("/personal-finance/?period=2025-11")
    assert m_resp.status_code == 200
    assert "November 2025" in m_resp.text
