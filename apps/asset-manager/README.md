# Asset Manager — the shop's memory

A simple web tool that remembers what your business buys, sells, and who still owes you money — so you don't have to.

It is a **local-only application**: it runs on your own machine, and you open it in a browser on the same computer (like a private notebook, not a website). Your data stays with you — nothing is uploaded anywhere, no accounts, no internet needed to work (photos and records live on your disk). If you can use email, you can use this.

**📖 [Read the illustrated User Manual →](docs/user-manual.md)** — every screen explained in plain language, with step-by-step "how do I…" walkthroughs.
*Or click 📖 Manual in the app's navigation bar — the manual travels with the tool.*

---

## What it does (in one breath each)

| Page | What it gives you |
|---|---|
| 🏠 **Dashboard** | Where you stand today: your shop's worst-case and best-case worth, stock value, cash received, and money customers owe you |
| 📦 **Batches** | A fresh lot of items from one supplier, on one date — grouped so you always know where each item came from |
| 💻 **Items** | Every item with its cost, serial number, extra expenses, suggested selling price, status, and photos |
| 💰 **Sales** | Sell one or many items to a customer in one bill — payments you receive today are recorded on the spot |
| 🧾 **Ledger** | Everyone who still owes you, and a permanent record of every payment that arrives (with date and mode) |
| 🛠️ **Assets** | The tools and equipment you keep — not for sale, but they count toward what your business is worth |

## How the money math works (no spreadsheets needed)

- Sell price suggestion = purchase price + extra expenses + your profit, where profit can be a plain amount (`5000`) or a percent (`15%`)
- Sold items get marked **Sold** automatically when you make a sale — no double selling
- Every later payment lands in the **Ledger** permanently, so part-payments and history are never mixed up

## For the technically curious

- **Stack:** Python + FastAPI + Jinja2 templates + SQLite (`data/business.db`), serves as plain HTML with `water.css` — no build step, no npm
- **Run locally:**
  ```bash
  cd src
  python -m uvicorn main:app --reload
  # open http://127.0.0.1:8000  (first run creates the database itself)
  ```
- **Install dependencies:** `pip install -r requirements.txt`
- **Where it runs:** your own machine only — there is no hosted deployment, and it is completely separate from the ecomsense.in website. Start it, use it at `http://127.0.0.1:8000`, stop it when done
- **User manual:** served in-app at `/manual` ([source](src/templates/manual.html)); a Markdown copy for offline reading lives at [docs/user-manual.md](docs/user-manual.md)

## Repo structure

```
src/
├── main.py           # FastAPI app, dashboard + /manual routes
├── database.py       # SQLAlchemy models (Batch, Inventory, Customer, Sale, PaymentLog, Asset)
├── routes/
│   ├── inventory.py  # Batches, item add/edit, photo uploads
│   ├── asset.py      # Fixed assets (tools)
│   └── sales.py      # Sales, ledger, payment log
├── templates/        # The screens (Jinja2) — including the manual page
└── static/           # CSS + item photos uploaded in the app
data/
└── business.db       # The SQLite database (created automatically, kept out of git)
```
