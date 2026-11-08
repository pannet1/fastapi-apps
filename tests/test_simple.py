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
