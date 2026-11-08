# AGENTS.md - Asset Manager Project

FastAPI inventory/asset management system with sales tracking. Local-only application.

## Project Structure

```
src/
├── main.py           # FastAPI app, dashboard route
├── database.py       # SQLAlchemy models
├── routes/
│   ├── inventory.py # Batch/inventory CRUD, photo uploads
│   ├── asset.py     # Fixed assets (tools)
│   └── sales.py     # Sales, ledger, payment tracking
├── templates/        # Jinja2 HTML templates
└── static/          # CSS, JS, inventory_photos/
data/
└── business.db       # SQLite database
```

## All Paths Are Relative

Code uses relative paths - works from any working directory:
- DB: `sqlite:///data/business.db`
- Templates: `templates/`
- Static: `static/`
- Uploads: `static/inventory_photos/`

## Git Commits

- `97edc0c` - add AGENTS.md with local run notes
- `c2e7321` - use relative db path for portability

## Quick Commands

```bash
# Run locally
cd src && python -m uvicorn main:app --reload

# Fresh clone: install deps first
pip install -r requirements.txt
```

## Package Versions (Python 3.13)

```
fastapi==0.100.0
starlette==0.27.0
jinja2==3.1.2
uvicorn==0.23.0
sqlalchemy
python-multipart
```

## Local-only application

This runs on the local machine only. It is **not** part of the ecomsense.in
website — don't confuse it with that site or its service, even though the
folder lives nearby. There is no hosted deployment: `git pull` on any machine,
start uvicorn, use the app in a browser at `http://127.0.0.1:8000`.

## Key Features

- **Dashboard** (`/`): Net worth calculation, stock value, receivables
- **Batches** (`/batch`): Group inventory by supplier
- **Inventory** (`/add-items/{id}`, `/edit-item/{id}`, `/all-items`): Full CRUD with photo uploads
- **Assets** (`/assets-list`): Fixed assets/tools tracking
- **Sales** (`/sales`): Process sales with customer selection
- **Ledger** (`/ledger`): Track pending payments
