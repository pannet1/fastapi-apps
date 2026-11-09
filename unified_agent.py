from datetime import date, datetime
from pathlib import Path
import sys
from typing import Any, Dict, List, Optional

# Ensure apps directories are importable
BASE_DIR = Path(__file__).resolve().parent
PF_SRC = BASE_DIR / "apps" / "personal-finance" / "src"
AM_SRC = BASE_DIR / "apps" / "asset-manager" / "src"

for p in [str(PF_SRC), str(AM_SRC), str(BASE_DIR)]:
    if p not in sys.path:
        sys.path.insert(0, p)

try:
    from pf_agent_service import (
        get_personal_finance_summary,
        add_transaction as pf_add_transaction,
        update_category as pf_update_category,
        get_categories as pf_get_categories,
    )
except ImportError:
    import importlib.util
    spec = importlib.util.spec_from_file_location("pf_agent_service", str(PF_SRC / "pf_agent_service.py"))
    pf_mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(pf_mod)
    get_personal_finance_summary = pf_mod.get_personal_finance_summary
    pf_add_transaction = pf_mod.add_transaction
    pf_update_category = pf_mod.update_category
    pf_get_categories = pf_mod.get_categories

try:
    import database as am_db
    from am_agent_service import (
        get_business_performance_summary,
        add_inventory_item as am_add_inventory,
        record_sale as am_record_sale,
        record_payment as am_record_payment,
        seed_sample_data_if_empty,
    )
except ImportError:
    import importlib.util
    spec_db = importlib.util.spec_from_file_location("am_database", str(AM_SRC / "database.py"))
    am_db = importlib.util.module_from_spec(spec_db)
    spec_db.loader.exec_module(am_db)

    spec_am = importlib.util.spec_from_file_location("am_agent_service", str(AM_SRC / "am_agent_service.py"))
    am_mod = importlib.util.module_from_spec(spec_am)
    spec_am.loader.exec_module(am_mod)
    get_business_performance_summary = am_mod.get_business_performance_summary
    am_add_inventory = am_mod.add_inventory_item
    am_record_sale = am_mod.record_sale
    am_record_payment = am_mod.record_payment
    seed_sample_data_if_empty = am_mod.seed_sample_data_if_empty


PF_MASTER_FILE = str(PF_SRC / "master_transactions.csv")
PF_CATEGORIES_FILE = str(PF_SRC / "categories.json")


def get_unified_summary(month: Optional[int] = None, year: Optional[int] = None, fmt: str = "json") -> Dict[str, Any]:
    """
    Unified summary combining Personal Finance and Business Performance
    into a single machine-readable or markdown response.
    """
    # 1. Personal Finance Summary
    pf_summary = get_personal_finance_summary(
        PF_MASTER_FILE, PF_CATEGORIES_FILE, month=month, year=year, fmt="json"
    )

    # 2. Business Performance Summary
    db = am_db.SessionLocal()
    try:
        seed_sample_data_if_empty(db)
        biz_summary = get_business_performance_summary(db, fmt="json")
    finally:
        db.close()

    # 3. Combined Financial Overview
    pf_cf = pf_summary.get("cashflow", {})
    biz_rp = biz_summary.get("revenue_and_profit", {})
    biz_lr = biz_summary.get("liquidity_and_receivables", {})
    biz_val = biz_summary.get("business_valuation", {})
    biz_inv = biz_summary.get("inventory_health", {})

    personal_net_savings = pf_cf.get("net_savings", 0.0)
    business_cash = biz_lr.get("cash_collected", 0.0)
    business_receivables = biz_lr.get("outstanding_receivables", 0.0)
    business_min_worth = biz_val.get("conservative_min_worth", 0.0)
    business_max_worth = biz_val.get("optimistic_max_worth", 0.0)

    combined_liquid_cash = round(personal_net_savings + business_cash, 2)
    combined_net_worth_min = round(business_min_worth + personal_net_savings, 2)
    combined_net_worth_max = round(business_max_worth + personal_net_savings, 2)

    # Alerts & Action Items
    alerts = []
    for over in pf_summary.get("over_budget_envelopes", []):
        alerts.append({
            "type": "personal_budget_overrun",
            "severity": "warning",
            "message": f"Personal Envelope '{over['category']}' is over budget by ${over['over_by']:,.2f} (Spent ${over['actual']:,.2f} / Budget ${over['budgeted']:,.2f})",
        })

    cat_health = pf_summary.get("categorization_health", {})
    if cat_health.get("uncategorized_count", 0) > 0:
        alerts.append({
            "type": "uncategorized_transactions",
            "severity": "info",
            "message": f"{cat_health['uncategorized_count']} personal transactions (${cat_health['uncategorized_amount']:,.2f}) need category classification.",
        })

    for debtor in biz_lr.get("unpaid_debtors", []):
        alerts.append({
            "type": "unpaid_business_receivable",
            "severity": "warning",
            "message": f"Customer '{debtor['customer']}' has pending balance due of ${debtor['balance_due']:,.2f} from sale on {debtor['sale_date']}.",
        })

    if biz_inv.get("in_stock_count", 0) < 3:
        alerts.append({
            "type": "low_inventory",
            "severity": "info",
            "message": f"Low business inventory: only {biz_inv.get('in_stock_count', 0)} items in stock.",
        })

    result = {
        "timestamp": datetime.now().isoformat(),
        "combined_financial_overview": {
            "combined_liquid_cash": combined_liquid_cash,
            "combined_net_worth_range": {
                "conservative_min": combined_net_worth_min,
                "optimistic_max": combined_net_worth_max,
            },
            "key_ratios": {
                "personal_savings_rate_pct": pf_cf.get("savings_rate_pct", 0.0),
                "business_gross_margin_pct": biz_rp.get("gross_margin_pct", 0.0),
                "business_collection_rate_pct": biz_lr.get("collection_rate_pct", 0.0),
            },
            "alerts_count": len(alerts),
            "alerts": alerts,
        },
        "personal_finance": pf_summary,
        "business_performance": biz_summary,
    }

    if fmt == "markdown":
        return {"markdown": _format_unified_markdown(result), "data": result}
    return result


def _format_unified_markdown(summary: Dict[str, Any]) -> str:
    comb = summary.get("combined_financial_overview", {})
    pf = summary.get("personal_finance", {})
    biz = summary.get("business_performance", {})
    alerts = comb.get("alerts", [])

    pf_p = pf.get("period", {})
    pf_cf = pf.get("cashflow", {})
    biz_rp = biz.get("revenue_and_profit", {})
    biz_lr = biz.get("liquidity_and_receivables", {})
    biz_inv = biz.get("inventory_health", {})
    biz_val = biz.get("business_valuation", {})

    lines = [
        "# 📊 AI Executive Financial Summary",
        f"**Generated**: {summary.get('timestamp', '')[:19].replace('T', ' ')}",
        "",
        "## 🌐 Combined Financial Position",
        f"- **Combined Net Worth**: **${comb.get('combined_net_worth_range', {}).get('conservative_min', 0.0):,.2f}** (Conservative) to **${comb.get('combined_net_worth_range', {}).get('optimistic_max', 0.0):,.2f}** (Optimistic)",
        f"- **Combined Liquid Cash**: **${comb.get('combined_liquid_cash', 0.0):,.2f}**",
        f"- **Health Ratios**: Personal Savings Rate: **{comb.get('key_ratios', {}).get('personal_savings_rate_pct', 0.0)}%** | Business Margin: **{comb.get('key_ratios', {}).get('business_gross_margin_pct', 0.0)}%**",
        "",
        f"## 💰 Personal Finance ({pf_p.get('label', 'Current Period')})",
        f"- **Income**: ${pf_cf.get('total_income', 0.0):,.2f} | **Expenses**: ${pf_cf.get('total_expenses', 0.0):,.2f}",
        f"- **Net Cashflow / Savings**: ${pf_cf.get('net_savings', 0.0):,.2f}",
        "",
        "## 🏢 Business Performance",
        f"- **Revenue**: ${biz_rp.get('total_sales_revenue', 0.0):,.2f} ({biz_rp.get('sales_count', 0)} sales)",
        f"- **COGS & Profit**: ${biz_rp.get('cost_of_goods_sold', 0.0):,.2f} COGS | Gross Profit: **${biz_rp.get('gross_profit', 0.0):,.2f}** ({biz_rp.get('gross_margin_pct', 0.0)}%)",
        f"- **Cash & Receivables**: ${biz_lr.get('cash_collected', 0.0):,.2f} collected | **${biz_lr.get('outstanding_receivables', 0.0):,.2f}** pending receivables",
        f"- **Inventory**: {biz_inv.get('in_stock_count', 0)} units in stock (${biz_inv.get('stock_cost_basis', 0.0):,.2f} cost basis / ${biz_inv.get('stock_market_value', 0.0):,.2f} market value)",
        f"- **Business Valuation**: Conservative ${biz_val.get('conservative_min_worth', 0.0):,.2f} | Optimistic ${biz_val.get('optimistic_max_worth', 0.0):,.2f}",
    ]

    if alerts:
        lines.append("")
        lines.append("## ⚠️ Priority Alerts & Action Items")
        for a in alerts:
            icon = "🚨" if a["severity"] == "warning" else "ℹ️"
            lines.append(f"- {icon} {a['message']}")

    return "\n".join(lines)


def query_quick_metric(q: str, month: Optional[int] = None, year: Optional[int] = None) -> Dict[str, Any]:
    """
    Sub-millisecond semantic parameter resolver for specific agent queries.
    """
    q_norm = q.lower().strip()
    data = get_unified_summary(month=month, year=year, fmt="json")
    comb = data["combined_financial_overview"]
    pf = data["personal_finance"]
    biz = data["business_performance"]

    if any(k in q_norm for k in ["net_worth", "net worth", "worth", "valuation"]):
        return {
            "query": q,
            "metric": "combined_net_worth",
            "conservative_min": comb["combined_net_worth_range"]["conservative_min"],
            "optimistic_max": comb["combined_net_worth_range"]["optimistic_max"],
            "business_min": biz["business_valuation"]["conservative_min_worth"],
            "business_max": biz["business_valuation"]["optimistic_max_worth"],
            "personal_net_savings": pf["cashflow"]["net_savings"],
        }
    elif any(k in q_norm for k in ["revenue", "sales", "gross profit", "margin"]):
        return {
            "query": q,
            "metric": "business_revenue_and_profit",
            "revenue": biz["revenue_and_profit"]["total_sales_revenue"],
            "sales_count": biz["revenue_and_profit"]["sales_count"],
            "cogs": biz["revenue_and_profit"]["cost_of_goods_sold"],
            "gross_profit": biz["revenue_and_profit"]["gross_profit"],
            "gross_margin_pct": biz["revenue_and_profit"]["gross_margin_pct"],
        }
    elif any(k in q_norm for k in ["receivable", "debtor", "unpaid", "pending", "owed"]):
        return {
            "query": q,
            "metric": "business_receivables",
            "total_receivables": biz["liquidity_and_receivables"]["outstanding_receivables"],
            "debtors": biz["liquidity_and_receivables"]["unpaid_debtors"],
        }
    elif any(k in q_norm for k in ["personal", "budget", "envelope", "over_budget", "expense", "income"]):
        return {
            "query": q,
            "metric": "personal_finance_budget",
            "period": pf["period"]["label"],
            "income": pf["cashflow"]["total_income"],
            "expenses": pf["cashflow"]["total_expenses"],
            "net_savings": pf["cashflow"]["net_savings"],
            "savings_rate_pct": pf["cashflow"]["savings_rate_pct"],
            "over_budget_envelopes": pf["over_budget_envelopes"],
        }
    elif any(k in q_norm for k in ["inventory", "stock", "hardware", "laptop"]):
        return {
            "query": q,
            "metric": "business_inventory",
            "in_stock_count": biz["inventory_health"]["in_stock_count"],
            "cost_basis": biz["inventory_health"]["stock_cost_basis"],
            "market_value": biz["inventory_health"]["stock_market_value"],
            "unrealized_profit": biz["inventory_health"]["unrealized_potential_profit"],
            "brand_summary": biz["inventory_health"]["brand_summary"],
        }
    elif any(k in q_norm for k in ["alert", "action", "warning"]):
        return {
            "query": q,
            "metric": "priority_alerts",
            "alerts": comb["alerts"],
        }
    else:
        return {
            "query": q,
            "metric": "executive_summary",
            "combined_net_worth_min": comb["combined_net_worth_range"]["conservative_min"],
            "combined_net_worth_max": comb["combined_net_worth_range"]["optimistic_max"],
            "liquid_cash": comb["combined_liquid_cash"],
            "alerts_count": comb["alerts_count"],
        }


AGENT_TOOLS_SCHEMA = [
    {
        "type": "function",
        "function": {
            "name": "get_unified_financial_summary",
            "description": "Fetch high-density unified executive financial summary combining personal finance and business performance metrics.",
            "parameters": {
                "type": "object",
                "properties": {
                    "month": {"type": "integer", "description": "Optional month (1-12) for personal finance. Defaults to latest month with data."},
                    "year": {"type": "integer", "description": "Optional year (e.g. 2026). Defaults to latest year with data."},
                    "format": {"type": "string", "enum": ["json", "markdown"], "description": "Output format: 'json' or 'markdown'."}
                }
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_personal_finance_report",
            "description": "Fetch detailed personal envelope budget analysis, cashflow, top expenses, and uncategorized items.",
            "parameters": {
                "type": "object",
                "properties": {
                    "month": {"type": "integer", "description": "Month (1-12). Defaults to latest active month."},
                    "year": {"type": "integer", "description": "Year (e.g. 2026). Defaults to latest active year."},
                    "format": {"type": "string", "enum": ["json", "markdown"]}
                }
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_business_performance_report",
            "description": "Fetch business metrics: sales revenue, COGS, gross margin, cash collected, debtors/receivables, inventory valuation, and net worth.",
            "parameters": {
                "type": "object",
                "properties": {
                    "format": {"type": "string", "enum": ["json", "markdown"]}
                }
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "record_personal_transaction",
            "description": "Record a new personal finance expense or income transaction.",
            "parameters": {
                "type": "object",
                "properties": {
                    "tran_date": {"type": "string", "description": "Transaction date (YYYY-MM-DD or DD-MM-YYYY)"},
                    "particulars": {"type": "string", "description": "Vendor or transaction description"},
                    "debit": {"type": "number", "description": "Expense amount (if expense)"},
                    "credit": {"type": "number", "description": "Income amount (if income)"},
                    "category": {"type": "string", "description": "Envelope category name"}
                },
                "required": ["tran_date", "particulars"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "categorize_transaction",
            "description": "Assign an envelope category to an uncategorized personal finance transaction.",
            "parameters": {
                "type": "object",
                "properties": {
                    "row_index": {"type": "integer", "description": "Row index of the transaction in the master dataset"},
                    "category": {"type": "string", "description": "Target category name"},
                    "forward": {"type": "boolean", "description": "Whether to also classify all future similar vendor transactions"}
                },
                "required": ["row_index", "category"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "record_business_sale",
            "description": "Record a customer sale of inventory items with initial payment amount.",
            "parameters": {
                "type": "object",
                "properties": {
                    "customer_name": {"type": "string", "description": "Name of the customer"},
                    "paid": {"type": "number", "description": "Initial amount paid"},
                    "item_ids": {"type": "array", "items": {"type": "integer"}, "description": "List of inventory IDs being purchased"},
                    "sale_date": {"type": "string", "description": "Date of sale (YYYY-MM-DD)"}
                },
                "required": ["customer_name", "paid", "item_ids"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "record_payment_installment",
            "description": "Record an installment payment for an outstanding business receivable sale.",
            "parameters": {
                "type": "object",
                "properties": {
                    "sale_id": {"type": "integer", "description": "ID of the sale record"},
                    "amount": {"type": "number", "description": "Payment amount collected"},
                    "note": {"type": "string", "description": "Payment note, e.g. 'Bank Wire', 'Cash'"}
                },
                "required": ["sale_id", "amount"]
            }
        }
    }
]


LLMS_TXT_CONTENT = """# FastAPI Financial & Business Intelligence API (Agent-Friendly)

> Machine-readable executive intelligence system combining Personal Finance (envelope budgeting & statement categorization) and Business Performance (sales, COGS, inventory valuation, receivables, net worth).

## Core Agent Endpoints

- `GET /agent/summary`: Unified executive summary combining Personal Finance and Business Performance in JSON. (Fast, token-efficient, < 5ms).
- `GET /agent/brief`: Natural-language markdown executive brief ready for direct injection into LLM context.
- `GET /agent/personal-finance`: Deep-dive envelope budget analysis, cashflow, top expenses, and uncategorized transactions.
  - Query params: `month` (1-12), `year` (e.g. 2026), `format` (`json` or `markdown`).
- `GET /agent/business-performance`: Deep-dive business revenue, COGS, gross margins, debtors/receivables, inventory health, and net worth.
  - Query params: `format` (`json` or `markdown`).
- `GET /agent/query?q=<term>`: Semantic query resolver for quick lookups (`net_worth`, `revenue`, `receivables`, `budget`, `alerts`, `inventory`).
- `GET /agent/tools.json`: OpenAI / Anthropic / Gemini compatible tool/function calling schemas.

## Data Ingestion & Action Endpoints

- `POST /personal-finance/api/agent/transactions`: Record personal expense or income transaction.
- `POST /personal-finance/api/agent/categorize`: Classify uncategorized transactions.
- `POST /asset-manager/api/agent/inventory`: Ingest new inventory items.
- `POST /asset-manager/api/agent/sales`: Process customer sales.
- `POST /asset-manager/api/agent/payments`: Log receivable payment installments.

## Key Formulas

- Personal Net Savings = Total Income - Total Expenses
- Business Gross Profit = Sales Revenue - Cost of Goods Sold (COGS)
- Business Min Net Worth (Conservative) = Stock Cost Basis + Cash Collected
- Business Max Net Worth (Optimistic) = Fixed Assets + Stock Market Value + Outstanding Receivables + Cash Collected
- Combined Liquid Cash = Personal Net Savings + Business Cash Collected
"""


LLMS_FULL_TXT_CONTENT = """# FastAPI Financial & Business Intelligence API — Full Agent Specification

## Overview
This platform exposes high-performance, low-latency API endpoints optimized for AI agents, LLMs, and autonomous workflows. Humans enter data via intuitive web interfaces or CSV uploads, while AI agents can extract structured summaries, compute valuations, or execute data mutations.

## 1. Unified Agent Summary
Endpoint: `GET /agent/summary`
Accepts:
- `month`: (Optional int) Month number (1-12). If omitted, defaults to the latest month with data.
- `year`: (Optional int) Year (e.g. 2026).
- `format`: (Optional string) "json" (default) or "markdown".

Response Schema (JSON):
```json
{
  "timestamp": "2026-11-09T13:00:00",
  "combined_financial_overview": {
    "combined_liquid_cash": 12500.0,
    "combined_net_worth_range": {
      "conservative_min": 15000.0,
      "optimistic_max": 28000.0
    },
    "key_ratios": {
      "personal_savings_rate_pct": 25.4,
      "business_gross_margin_pct": 28.5,
      "business_collection_rate_pct": 82.0
    },
    "alerts_count": 2,
    "alerts": [
      {
        "type": "personal_budget_overrun",
        "severity": "warning",
        "message": "Envelope 'Entertainment' exceeded budget by $1,200."
      }
    ]
  },
  "personal_finance": {
    "period": {"month": 2, "year": 2026, "label": "February 2026"},
    "cashflow": {
      "total_income": 5000.0,
      "total_expenses": 39094.62,
      "net_savings": -34094.62,
      "savings_rate_pct": -681.9
    },
    "envelopes": [ ... ],
    "over_budget_envelopes": [ ... ],
    "categorization_health": {
      "uncategorized_count": 0,
      "uncategorized_amount": 0.0,
      "pending": []
    },
    "top_expenses": [ ... ]
  },
  "business_performance": {
    "revenue_and_profit": {
      "total_sales_revenue": 1239.0,
      "sales_count": 2,
      "cost_of_goods_sold": 910.0,
      "gross_profit": 329.0,
      "gross_margin_pct": 26.6
    },
    "liquidity_and_receivables": {
      "cash_collected": 972.0,
      "outstanding_receivables": 267.0,
      "collection_rate_pct": 78.5,
      "unpaid_debtors": [ ... ]
    },
    "inventory_health": {
      "in_stock_count": 4,
      "stock_cost_basis": 2140.0,
      "stock_market_value": 2726.0,
      "unrealized_potential_profit": 586.0
    },
    "fixed_assets": {
      "total_asset_value": 2050.0,
      "asset_count": 2
    },
    "business_valuation": {
      "conservative_min_worth": 3112.0,
      "optimistic_max_worth": 6015.0
    }
  }
}
```

## 2. Fast Markdown Brief
Endpoint: `GET /agent/brief`
Returns a compact, token-efficient Markdown briefing suitable for embedding directly into an LLM system prompt or user chat response.

## 3. Tool Function Calling Schemas
Endpoint: `GET /agent/tools.json`
Provides OpenAI, Gemini, and Anthropic tool definitions for immediate programmatic invocation.
"""
