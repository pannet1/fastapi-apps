import uuid
from fastapi.testclient import TestClient
from main import app

client = TestClient(app)


def test_agent_discovery_specs():
    # 1. llms.txt
    resp = client.get("/llms.txt")
    assert resp.status_code == 200
    assert "FastAPI Financial & Business Intelligence API" in resp.text
    assert "/agent/summary" in resp.text
    assert "/agent/brief" in resp.text

    # 2. llms-full.txt
    resp_full = client.get("/llms-full.txt")
    assert resp_full.status_code == 200
    assert "Full Agent Specification" in resp_full.text

    # 3. .well-known/agent.json
    resp_plugin = client.get("/.well-known/agent.json")
    assert resp_plugin.status_code == 200
    plugin_data = resp_plugin.json()
    assert plugin_data["name_for_model"] == "financial_and_business_intelligence"
    assert "/agent/tools.json" in plugin_data["tools_schema"]

    # 4. agent tools schema
    resp_tools = client.get("/agent/tools.json")
    assert resp_tools.status_code == 200
    tools_data = resp_tools.json()
    assert "tools" in tools_data
    tool_names = [t["function"]["name"] for t in tools_data["tools"]]
    assert "get_unified_financial_summary" in tool_names
    assert "get_personal_finance_report" in tool_names
    assert "get_business_performance_report" in tool_names
    assert "record_personal_transaction" in tool_names


def test_agent_unified_summary_json():
    resp = client.get("/agent/summary")
    assert resp.status_code == 200
    data = resp.json()

    # Verify high-level keys
    assert "combined_financial_overview" in data
    assert "personal_finance" in data
    assert "business_performance" in data
    assert "timestamp" in data

    # Verify combined overview
    comb = data["combined_financial_overview"]
    assert "combined_liquid_cash" in comb
    assert "combined_net_worth_range" in comb
    assert "conservative_min" in comb["combined_net_worth_range"]
    assert "optimistic_max" in comb["combined_net_worth_range"]
    assert "key_ratios" in comb
    assert "alerts" in comb

    # Verify personal finance summary
    pf = data["personal_finance"]
    assert "cashflow" in pf
    assert "total_income" in pf["cashflow"]
    assert "total_expenses" in pf["cashflow"]
    assert "net_savings" in pf["cashflow"]
    assert "envelopes" in pf
    assert "categorization_health" in pf

    # Verify business performance summary
    biz = data["business_performance"]
    assert "revenue_and_profit" in biz
    assert "total_sales_revenue" in biz["revenue_and_profit"]
    assert "gross_profit" in biz["revenue_and_profit"]
    assert "gross_margin_pct" in biz["revenue_and_profit"]
    assert "liquidity_and_receivables" in biz
    assert "inventory_health" in biz
    assert "business_valuation" in biz


def test_agent_markdown_brief():
    # Direct endpoint /agent/brief
    resp = client.get("/agent/brief")
    assert resp.status_code == 200
    assert "# 📊 AI Executive Financial Summary" in resp.text
    assert "Combined Net Worth" in resp.text
    assert "Business Performance" in resp.text
    assert "Personal Finance" in resp.text

    # Via format=markdown parameter on /agent/summary
    resp_fmt = client.get("/agent/summary?format=markdown")
    assert resp_fmt.status_code == 200
    assert "AI Executive Financial Summary" in resp_fmt.text


def test_agent_semantic_query_resolver():
    # 1. Net worth query
    nw = client.get("/agent/query?q=net_worth").json()
    assert nw["metric"] == "combined_net_worth"
    assert "conservative_min" in nw
    assert "optimistic_max" in nw

    # 2. Revenue query
    rev = client.get("/agent/query?q=revenue").json()
    assert rev["metric"] == "business_revenue_and_profit"
    assert "revenue" in rev
    assert "gross_profit" in rev

    # 3. Debtors query
    deb = client.get("/agent/query?q=debtors").json()
    assert deb["metric"] == "business_receivables"
    assert "debtors" in deb

    # 4. Budget query
    bud = client.get("/agent/query?q=budget").json()
    assert bud["metric"] == "personal_finance_budget"
    assert "over_budget_envelopes" in bud

    # 5. Inventory query
    inv = client.get("/agent/query?q=inventory").json()
    assert inv["metric"] == "business_inventory"
    assert "in_stock_count" in inv


def test_personal_finance_subapp_agent_api():
    # 1. Summary
    resp = client.get("/personal-finance/api/agent/summary")
    assert resp.status_code == 200
    data = resp.json()
    assert "cashflow" in data
    assert "envelopes" in data

    # 2. Categories
    cats = client.get("/personal-finance/api/agent/categories").json()
    assert "categories" in cats

    # 3. Filterable transactions
    txs = client.get("/personal-finance/api/agent/transactions?limit=10").json()
    assert "transactions" in txs
    assert len(txs["transactions"]) <= 10


def test_business_performance_subapp_agent_api():
    # 1. Summary
    resp = client.get("/asset-manager/api/agent/summary")
    assert resp.status_code == 200
    data = resp.json()
    assert "revenue_and_profit" in data
    assert "business_valuation" in data

    # 2. Inventory
    inv = client.get("/asset-manager/api/agent/inventory").json()
    assert "items" in inv

    # 3. Sales
    sales = client.get("/asset-manager/api/agent/sales").json()
    assert "sales" in sales

    # 4. Debtors
    debtors = client.get("/asset-manager/api/agent/debtors").json()
    assert "debtors" in debtors


def test_human_and_agent_data_entry():
    import shutil
    from pathlib import Path
    pf_csv = Path("apps/personal-finance/src/master_transactions.csv")
    backup = pf_csv.read_text(encoding="utf-8") if pf_csv.exists() else None

    try:
        # 1. Agent records personal transaction
        p_tx = client.post(
            "/personal-finance/api/agent/transactions",
            json={
                "tran_date": "2026-11-09",
                "particulars": "Agent AWS Cloud Services",
                "debit": 85.50,
                "credit": 0.0,
                "category": "Business",
            },
        )
        assert p_tx.status_code == 200
        assert p_tx.json()["status"] == "success"

        # 2. Human records personal transaction via form
        h_tx = client.post(
            "/personal-finance/transactions/add",
            data={
                "tran_date": "2026-11-09",
                "particulars": "Grocery Market Fresh",
                "tran_type": "debit",
                "amount": "45.00",
                "category": "Eatables",
            },
            follow_redirects=False,
        )
        assert h_tx.status_code == 303

        # 3. Agent categorizes an uncategorized item
        cat_res = client.post(
            "/personal-finance/api/agent/categorize",
            json={"row_index": 0, "category": "Business", "forward": False},
        )
        assert cat_res.status_code == 200
    finally:
        if backup is not None:
            pf_csv.write_text(backup, encoding="utf-8")

    # 4. Agent records inventory item
    inv_res = client.post(
        "/asset-manager/api/agent/inventory",
        json={
            "brand": "Lenovo",
            "model": "ThinkPad P1 Gen 4",
            "serial": f"LN-P1G4-TEST-{uuid.uuid4().hex[:6]}",
            "purchase_price": 750.0,
            "profit": "30%",
        },
    )
    assert inv_res.status_code == 200
    assert inv_res.json()["status"] == "success"
    created_inv_id = inv_res.json()["inventory_id"]

    # 5. Agent records a sale with partial payment
    sale_res = client.post(
        "/asset-manager/api/agent/sales",
        json={
            "customer_name": f"Debtor Client {uuid.uuid4().hex[:4]}",
            "paid": 200.0,
            "inventory_id": created_inv_id,
        },
    )
    assert sale_res.status_code == 200
    created_sale_id = sale_res.json()["sale_id"]

    # 6. Agent records debtor payment against the created sale
    pay_res = client.post(
        "/asset-manager/api/agent/payments",
        json={"sale_id": created_sale_id, "amount": 50.0, "note": "Test Installment via Agent"},
    )
    assert pay_res.status_code == 200
    assert pay_res.json()["status"] == "success"


def test_agent_hub_ui_page():
    resp = client.get("/agent")
    assert resp.status_code == 200
    assert "text/html" in resp.headers.get("content-type", "")
    assert "AI Agent" in resp.text
    assert "Combined Net Worth" in resp.text
    assert "Quick Data Entry" in resp.text
    assert "/agent/summary" in resp.text


def test_process_sale_and_initial_payment_log():
    # 1. Add an inventory item to sell
    sn = f"TEST-LAPTOP-{uuid.uuid4().hex[:6]}"
    inv_res = client.post(
        "/asset-manager/api/agent/inventory",
        json={
            "brand": "Dell",
            "model": "Latitude 7490",
            "serial": sn,
            "purchase_price": 18000.0,
            "profit": "20%",
        },
    )
    assert inv_res.status_code == 200
    inventory_id = inv_res.json()["inventory_id"]

    # 2. Process sale with single inventory_id and partial payment
    cust_name = f"Test Buyer {uuid.uuid4().hex[:4]}"
    sale_resp = client.post(
        "/asset-manager/process-sale",
        data={
            "customer_name": cust_name,
            "sale_price": 21600.0,
            "paid": 10000.0,
            "inventory_id": inventory_id,
            "payment_note": "Advance via UPI",
        },
        follow_redirects=False,
    )
    # Redirects to /ledger because balance remains
    assert sale_resp.status_code == 303
    assert "/ledger" in sale_resp.headers["location"]

    # 3. Check debtors list shows remaining balance
    debtors_resp = client.get("/asset-manager/api/agent/debtors")
    assert debtors_resp.status_code == 200
    debtors = debtors_resp.json()["debtors"]
    matched = [d for d in debtors if d["customer"] == cust_name]
    assert len(matched) == 1
    assert matched[0]["amount_paid"] == 10000.0
    assert matched[0]["balance_due"] > 0


def test_contact_search_api_and_phone_save():
    # 1. Test search endpoint
    search_res = client.get("/asset-manager/api/contacts/search?q=stephan")
    assert search_res.status_code == 200
    results = search_res.json()["results"]
    assert isinstance(results, list)
    if results:
        assert "name" in results[0]
        assert "phone" in results[0]

    # 2. Add inventory and process sale with phone number
    inv_res = client.post(
        "/asset-manager/api/agent/inventory",
        json={
            "brand": "Lenovo",
            "model": "ThinkPad T480",
            "serial": f"T480-TEST-{uuid.uuid4().hex[:6]}",
            "purchase_price": 14000.0,
            "profit": "25%",
        },
    )
    inv_id = inv_res.json()["inventory_id"]

    cust_name = f"Phone Client {uuid.uuid4().hex[:4]}"
    cust_phone = "+919876543210"
    sale_resp = client.post(
        "/asset-manager/process-sale",
        data={
            "customer_name": cust_name,
            "customer_phone": cust_phone,
            "sale_price": 17500.0,
            "paid": 5000.0,
            "inventory_id": inv_id,
            "payment_note": "Advance Deposit",
        },
        follow_redirects=False,
    )
    assert sale_resp.status_code == 303

    # Check ledger HTML renders the phone and whatsapp link
    ledger_page = client.get("/asset-manager/ledger")
    assert ledger_page.status_code == 200
    assert cust_phone in ledger_page.text
    assert "https://wa.me/919876543210" in ledger_page.text


def test_pure_service_sale_and_revenue():
    # Record a repair service sale with zero inventory items
    cust_name = f"Repair Client {uuid.uuid4().hex[:4]}"
    service_desc = "Ideapad 5 hinge standoff rebuild + antenna splice"
    sale_resp = client.post(
        "/asset-manager/process-sale",
        data={
            "customer_name": cust_name,
            "service_description": service_desc,
            "sale_price": 1400.0,
            "paid": 1400.0,
            "payment_note": "Paid in full via Cash",
        },
        follow_redirects=False,
    )
    # Fully paid -> redirects to /
    assert sale_resp.status_code == 303
    assert sale_resp.headers["location"] == "/"

    # Also test partial payment service sale -> appears in ledger with service badge
    cust_partial = f"Partial Client {uuid.uuid4().hex[:4]}"
    sale_resp2 = client.post(
        "/asset-manager/process-sale",
        data={
            "customer_name": cust_partial,
            "service_description": "Motherboard short circuit repair",
            "sale_price": 2500.0,
            "paid": 1000.0,
            "payment_note": "Advance via UPI",
        },
        follow_redirects=False,
    )
    assert sale_resp2.status_code == 303
    assert "/ledger" in sale_resp2.headers["location"]

    ledger_page = client.get("/asset-manager/ledger")
    assert ledger_page.status_code == 200
    assert "Motherboard short circuit repair" in ledger_page.text
