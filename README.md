# FastAPI App Marketplace & AI Agent Intelligence Platform

A lightweight, modular marketplace platform that mounts full-blown FastAPI applications and provides an **AI Agent-Friendly Financial & Business Intelligence Gateway**.

Humans enter financial and inventory data via streamlined web interfaces or statement imports, while autonomous AI agents and pair-programming LLMs extract instant, token-optimized executive summaries.

---

## 🚀 Quick Start with `uv`

Run the platform (hardcoded to port `11173`):

```bash
uv run python main.py
```

- **Marketplace Hub**: [http://localhost:11173](http://localhost:11173)
- **AI Agent Intelligence Hub**: [http://localhost:11173/agent](http://localhost:11173/agent)
- **Agent Discovery (llms.txt)**: [http://localhost:11173/llms.txt](http://localhost:11173/llms.txt)
- **Core API Documentation**: [http://localhost:11173/docs](http://localhost:11173/docs)

---

## 🤖 AI Agent Gateway (`/agent`)

The platform exposes dedicated machine-readable endpoints designed for sub-5ms response times and minimal token usage:

| Endpoint | Method | Format | Description |
| :--- | :--- | :--- | :--- |
| `/agent/summary` | `GET` | JSON | **Unified Executive Brief**: Combines Personal Finance (cashflow, envelope budgets) + Business Performance (revenue, COGS, margins, receivables, net worth). |
| `/agent/brief` | `GET` | Markdown | **Token-Optimized Markdown**: ~230 tokens, formatted for direct injection into LLM prompts or chat responses. |
| `/agent/personal-finance` | `GET` | JSON / MD | Personal finance envelopes, cashflow, top expenses, and uncategorized transactions. Supports `?month=X&year=Y`. |
| `/agent/business-performance` | `GET` | JSON / MD | Business sales, COGS, gross margin, cash collected, debtors, inventory valuation, and conservative/optimistic net worth. |
| `/agent/query?q=<term>` | `GET` | JSON | Semantic parameter resolver for targeted lookups (`net_worth`, `revenue`, `debtors`, `budget`, `inventory`, `alerts`). |
| `/agent/tools.json` | `GET` | JSON | Pre-built function calling schemas (OpenAI / Anthropic / Gemini format). |
| `/llms.txt` | `GET` | Plain Text | Standard `llms.txt` specification index for agent discovery. |
| `/llms-full.txt` | `GET` | Plain Text | Comprehensive agent documentation and endpoint schema guide. |

---

## ✍️ Human Data Entry

Humans can input data through multiple convenient interfaces:

### 1. Personal Finance (`/personal-finance/`)
- **Quick Single Entry**: Add individual transactions on the fly via `/transactions` or the `/agent` hub.
- **Statement CSV Upload**: Drop raw bank/UPI statements into `/personal-finance/upload` (automatically strips statement noise and deduplicates).
- **Envelope Budgeting**: Configure category monthly limits at `/personal-finance/settings`.
- **Categorization**: Classify transactions with forward-matching rules.

### 2. Business Performance (`/asset-manager/`)
- **Inventory Batches**: Group inventory by supplier at `/asset-manager/batch`.
- **Item Cataloguing**: Log purchase price, intended markup/profit %, and serial numbers.
- **Sales & Customer Ledger**: Record sales, track credit, and log installment payments at `/asset-manager/sales` and `/asset-manager/ledger`.
- **Fixed Assets**: Track equipment and workshop tooling at `/asset-manager/assets-list`.

---

## 🛠️ Agent Function Calling / Tool Integration

Agents can import the function schema directly from `/agent/tools.json` or call the REST APIs directly:

### 1. Fetch Unified Summary (cURL)
```bash
curl http://localhost:11173/agent/summary
```

### 2. Fetch Prompt-Ready Markdown Brief
```bash
curl http://localhost:11173/agent/brief
```

### 3. Record Personal Transaction via Agent API
```bash
curl -X POST http://localhost:11173/personal-finance/api/agent/transactions \
  -H "Content-Type: application/json" \
  -d '{
    "tran_date": "2026-11-09",
    "particulars": "Stripe Merchant Payout",
    "credit": 1250.00,
    "category": "Income"
  }'
```

### 4. Record Debtor Installment Payment
```bash
curl -X POST http://localhost:11173/asset-manager/api/agent/payments \
  -H "Content-Type: application/json" \
  -d '{
    "sale_id": 2,
    "amount": 200.00,
    "note": "Bank Transfer Installment"
  }'
```

---

## 📊 Key Formulas & Metrics

- **Personal Net Savings**: $\text{Total Income} - \text{Total Expenses}$
- **Business Gross Profit**: $\text{Sales Revenue} - \text{Cost of Goods Sold (COGS)}$
- **Conservative Net Worth**: $\text{Unsold Stock Cost Basis} + \text{Cash Collected}$
- **Optimistic Net Worth**: $\text{Fixed Assets} + \text{Unsold Stock Market Value} + \text{Outstanding Receivables} + \text{Cash Collected}$
- **Combined Liquid Cash**: $\text{Personal Net Savings} + \text{Business Cash Collected}$

---

## 🧪 Testing

Run the test suite with `uv`:

```bash
uv run pytest
```
