# FastAPI App Marketplace

A lightweight marketplace platform that mounts and orchestrates full-blown FastAPI applications.

## Run with `uv`

Pass any port via `--port` or `-p`:

```bash
uv run python main.py --port 10011
```

Open [http://localhost:10011](http://localhost:10011) to view the marketplace storefront.

## Integrating Any Full-Blown FastAPI App

You can integrate any existing FastAPI application in two ways:

### Option 1: Drop-in Directory (`apps/`)
Drop your existing application directory inside `apps/<app_name>/` containing an `app.py` or `main.py` that exports `app`. The marketplace will automatically discover and mount it at `/<app_name>/`.

### Option 2: Programmatic Mount in `main.py`
Import and register your existing application instance:

```python
from my_existing_app import app as my_app

marketplace.register(my_app, path="/my-app", icon="🚀")
```
