import argparse
import importlib.util
import inspect
from pathlib import Path
import re
import sys
from typing import Any, Dict, List, Optional
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, RedirectResponse
import uvicorn

# Guarantee this marketplace root is always at sys.path[0]
BASE_DIR = Path(__file__).resolve().parent
if str(BASE_DIR) not in sys.path or sys.path[0] != str(BASE_DIR):
    sys.path.insert(0, str(BASE_DIR))

APPS_DIR = BASE_DIR / "apps"
APPS_DIR.mkdir(exist_ok=True)


def _enable_fastapi_compatibility_layer():
    """
    Applies non-invasive runtime adaptations so existing FastAPI applications
    can be plugged in without restructuring or code changes:
    1. Resolves relative directories for Jinja2Templates and StaticFiles across caller parent directories.
    2. Adapts legacy Starlette TemplateResponse(name, context) calls to modern Starlette.
    3. Resolves relative SQLite database URLs to the application directory.
    """
    # 1. TemplateResponse legacy compatibility & relative template paths
    try:
        import starlette.templating
        from starlette.templating import Jinja2Templates

        orig_init = Jinja2Templates.__init__

        def compat_init(self, directory=None, *args, **kwargs):
            if directory and isinstance(directory, (str, Path)) and not Path(directory).is_absolute():
                caller = inspect.stack()[1].filename
                caller_path = Path(caller).resolve()
                for parent in [caller_path.parent, caller_path.parent.parent, caller_path.parent.parent.parent]:
                    candidate = parent / directory
                    if candidate.exists():
                        directory = str(candidate)
                        break
            return orig_init(self, directory=directory, *args, **kwargs)

        Jinja2Templates.__init__ = compat_init

        orig_resp = Jinja2Templates.TemplateResponse

        def compat_resp(self, *args, **kwargs):
            if args and isinstance(args[0], str):
                name = args[0]
                context = args[1] if len(args) > 1 and isinstance(args[1], dict) else kwargs.pop("context", {})
                req = context.get("request") if isinstance(context, dict) else kwargs.pop("request", None)
                return orig_resp(self, req, name, context, *args[2:], **kwargs)
            return orig_resp(self, *args, **kwargs)

        Jinja2Templates.TemplateResponse = compat_resp
    except ImportError:
        pass

    # 2. StaticFiles relative path resolution
    try:
        from starlette.staticfiles import StaticFiles

        orig_static_init = StaticFiles.__init__

        def compat_static_init(self, *args, directory=None, **kwargs):
            if directory and isinstance(directory, (str, Path)) and not Path(directory).is_absolute():
                caller = inspect.stack()[1].filename
                caller_path = Path(caller).resolve()
                for parent in [caller_path.parent, caller_path.parent.parent, caller_path.parent.parent.parent]:
                    candidate = parent / directory
                    if candidate.exists():
                        directory = str(candidate)
                        break
            return orig_static_init(self, *args, directory=directory, **kwargs)

        StaticFiles.__init__ = compat_static_init
    except ImportError:
        pass

    # 3. SQLAlchemy relative SQLite path resolution
    try:
        import sqlalchemy

        orig_create_engine = sqlalchemy.create_engine

        def compat_create_engine(url, *args, **kwargs):
            url_str = str(url)
            if url_str.startswith("sqlite:///") and not url_str.startswith("sqlite:////"):
                rel_path = url_str.replace("sqlite:///", "")
                caller = inspect.stack()[1].filename
                abs_db = (Path(caller).parent / rel_path).resolve()
                abs_db.parent.mkdir(parents=True, exist_ok=True)
                url = f"sqlite:///{abs_db}"
            return orig_create_engine(url, *args, **kwargs)

        sqlalchemy.create_engine = compat_create_engine
    except ImportError:
        pass


_enable_fastapi_compatibility_layer()


def _rewrite_subapp_html(content: bytes, prefix: str) -> bytes:
    """
    Rewrites root-relative URLs in sub-app HTML (href='/...', action='/...', src='/...')
    so they stay routed inside the mounted sub-application prefix.
    """
    prefix = prefix.rstrip("/")
    text = content.decode("utf-8", errors="ignore")
    # Rewrite href='/...' action='/...' src='/...' except external URLs or already prefixed
    pattern = r'((?:href|action|src)=[\"\'])/(?!/|' + re.escape(prefix.lstrip("/")) + r'/|https?://)([^\"\']*)[\"\']'
    rewritten = re.sub(pattern, lambda m: f'{m.group(1)}{prefix}/{m.group(2)}"', text)

    # Inject a non-intrusive navigation banner back to Marketplace Hub
    banner = f"""<div style="background:#0f172a; border-bottom:1px solid #1e293b; padding:8px 20px; font-size:13px; font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif; display:flex; justify-content:space-between; align-items:center; z-index:999999; position:sticky; top:0;">
        <a href="/" style="color:#38bdf8; text-decoration:none; font-weight:600; display:flex; align-items:center; gap:6px;">← Back to Marketplace Hub</a>
        <span style="color:#94a3b8; font-size:12px;">App: <strong style="color:#f8fafc;">{prefix.strip('/')}</strong></span>
    </div>"""

    if "<body" in rewritten:
        rewritten = re.sub(r"(<body[^>]*>)", r"\1" + banner, rewritten, count=1, flags=re.IGNORECASE)

    return rewritten.encode("utf-8")


class SubAppPathRewriterASGI:
    """
    ASGI middleware wrapping a mounted sub-app.
    Buffers response headers and body so rewritten HTML has the EXACT recalculation
    of content-length (preventing Uvicorn httptools assertion errors), and rewrites
    redirect Location headers.
    """
    def __init__(self, app, prefix: str):
        self.app = app
        self.prefix = prefix.rstrip("/")

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        start_message = None
        body_parts = []

        async def send_wrapper(message):
            nonlocal start_message
            if message["type"] == "http.response.start":
                start_message = message
            elif message["type"] == "http.response.body":
                body_parts.append(message.get("body", b""))
                if not message.get("more_body", False):
                    full_body = b"".join(body_parts)
                    content_type = ""
                    for k, v in start_message.get("headers", []):
                        if k.lower() == b"content-type":
                            content_type = v.decode("latin1")
                            break

                    if "text/html" in content_type:
                        full_body = _rewrite_subapp_html(full_body, self.prefix)

                    new_headers = []
                    for k, v in start_message.get("headers", []):
                        if k.lower() == b"content-length":
                            continue  # Will recalculate exact length
                        elif k.lower() == b"location":
                            loc = v.decode("utf-8", errors="ignore")
                            if loc.startswith("/") and not loc.startswith(self.prefix + "/"):
                                v = f"{self.prefix}{loc}".encode("utf-8")
                        new_headers.append((k, v))

                    # Set accurate content-length matching the actual payload
                    new_headers.append((b"content-length", str(len(full_body)).encode("latin1")))

                    start_message_copy = dict(start_message)
                    start_message_copy["headers"] = new_headers
                    await send(start_message_copy)
                    await send({"type": "http.response.body", "body": full_body, "more_body": False})
            else:
                await send(message)

        await self.app(scope, receive, send_wrapper)


def _get_subapp_paths(app_obj) -> set:
    """Extracts all route paths from an app, including included routers."""
    all_paths = set()
    for r in getattr(app_obj, "routes", []):
        if hasattr(r, "path"):
            all_paths.add(r.path)
        if hasattr(r, "original_router") and hasattr(r.original_router, "routes"):
            for sub_r in r.original_router.routes:
                if hasattr(sub_r, "path"):
                    all_paths.add(sub_r.path)
    return all_paths


class FastAPIMarketplace:
    """
    FastAPI Marketplace Platform.
    Mounts and orchestrates full-blown FastAPI applications at runtime.
    """
    def __init__(self, title: str = "FastAPI App Marketplace", description: str = "Host and integrate any FastAPI application"):
        self.main_app = FastAPI(title=title, description=description)
        self.registry: List[Dict[str, Any]] = []

        # Catch-all middleware: If an unnamespaced link (e.g. /batch) hits the marketplace root,
        # redirect it transparently to the correct sub-application mount.
        @self.main_app.middleware("http")
        async def fallback_subapp_redirect(request: Request, call_next):
            response = await call_next(request)
            if response.status_code == 404 and self.registry:
                path = request.url.path
                if path != "/":
                    for item in self.registry:
                        sub_app = item.get("raw_app")
                        if sub_app:
                            paths = _get_subapp_paths(sub_app)
                            if path in paths or any(path.startswith(p.split('{')[0]) for p in paths if '{' in p):
                                target = f"{item['path'].rstrip('/')}{path}"
                                if request.url.query:
                                    target = f"{target}?{request.url.query}"
                                return RedirectResponse(url=target, status_code=307)
            return response

        # Marketplace Storefront UI
        @self.main_app.get("/", response_class=HTMLResponse)
        def marketplace_home(request: Request):
            cards_html = ""
            if not self.registry:
                cards_html = """
                <div style="grid-column: 1 / -1; text-align: center; padding: 60px 20px; background: #1e293b; border: 1px dashed #334155; border-radius: 16px;">
                    <div style="font-size: 2.5rem; margin-bottom: 12px;">🧩</div>
                    <h3 style="margin: 0 0 8px 0; color: #f8fafc; font-size: 1.25rem;">No Applications Integrated Yet</h3>
                    <p style="margin: 0 auto; color: #94a3b8; font-size: 0.9rem; max-width: 500px; line-height: 1.5;">
                        To integrate any existing FastAPI app, drop its folder into <code>apps/&lt;app_name&gt;</code>, or register it programmatically via <code>marketplace.register(app, path="/your-path")</code>.
                    </p>
                </div>
                """
            else:
                for item in self.registry:
                    cards_html += f"""
                    <div style="background:#1e293b; border:1px solid #334155; border-radius:12px; padding:24px; display:flex; flex-direction:column; justify-content:space-between; box-shadow:0 4px 6px -1px rgba(0,0,0,0.3);">
                        <div>
                            <div style="font-size:2.2rem; margin-bottom:10px;">{item['icon']}</div>
                            <h2 style="margin:0 0 8px 0; color:#f8fafc; font-size:1.3rem; font-weight:700;">{item['name']}</h2>
                            <p style="margin:0 0 16px 0; color:#94a3b8; font-size:0.9rem; line-height:1.5;">{item['description']}</p>
                            <div style="margin-bottom:20px;">
                                <span style="background:#0f172a; color:#38bdf8; padding:4px 10px; border-radius:6px; font-size:0.8rem; font-family:monospace; border:1px solid #1e293b;">
                                    Mount: {item['path']}
                                </span>
                            </div>
                        </div>
                        <div style="display:flex; gap:10px;">
                            <a href="{item['path']}" style="flex:1; text-align:center; background:#4f46e5; hover:background:#4338ca; color:white; padding:10px 14px; border-radius:8px; text-decoration:none; font-size:0.9rem; font-weight:600;">Launch App</a>
                            <a href="{item['docs_url']}" target="_blank" style="background:#334155; color:#cbd5e1; padding:10px 14px; border-radius:8px; text-decoration:none; font-size:0.9rem;">Docs</a>
                        </div>
                    </div>
                    """

            return f"""<!DOCTYPE html>
            <html>
            <head>
                <title>{title}</title>
                <meta name="viewport" content="width=device-width, initial-scale=1">
                <style>
                    body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; background:#0b0f19; color:#f1f5f9; margin:0; padding:40px 20px; }}
                    .container {{ max-width: 1000px; margin: 0 auto; }}
                    .grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(300px, 1fr)); gap: 24px; margin-top: 30px; }}
                </style>
            </head>
            <body>
                <div class="container">
                    <div style="display:flex; justify-content:space-between; align-items:center; border-bottom:1px solid #1e293b; padding-bottom:24px;">
                        <div>
                            <h1 style="margin:0; font-size:2rem; color:#fff; display:flex; align-items:center; gap:10px;">⚡ {title}</h1>
                            <p style="margin:8px 0 0 0; color:#94a3b8; font-size:1rem;">{description}</p>
                        </div>
                        <a href="/docs" target="_blank" style="background:#1e293b; color:#38bdf8; padding:8px 16px; border-radius:8px; text-decoration:none; font-size:0.85rem; border:1px solid #334155;">Marketplace API Docs</a>
                    </div>
                    <div class="grid">
                        {cards_html}
                    </div>
                </div>
            </body>
            </html>"""

        @self.main_app.get("/api/apps")
        def list_apps():
            """Returns JSON metadata of all mounted applications."""
            return [{k: v for k, v in item.items() if k != "raw_app"} for item in self.registry]

    def register(
        self,
        app: FastAPI,
        path: str,
        name: Optional[str] = None,
        description: Optional[str] = None,
        icon: str = "📦"
    ):
        """
        Mounts any full-blown FastAPI application onto the marketplace.
        """
        prefix = path if path.startswith("/") else f"/{path}"
        prefix = prefix.rstrip("/")

        if not name:
            app_title = getattr(app, "title", "")
            if app_title and app_title != "FastAPI":
                app_name = app_title
            else:
                app_name = prefix.strip("/").replace("-", " ").title()
        else:
            app_name = name

        app_desc = description or getattr(app, "description", "") or f"{app_name} Application"

        # Wrap app with the sub-app path rewriter
        wrapped_sub_app = SubAppPathRewriterASGI(app, prefix=prefix)

        # Mount app instance
        self.main_app.mount(prefix, wrapped_sub_app)

        self.registry.append({
            "name": app_name,
            "description": app_desc,
            "path": f"{prefix}/",
            "icon": icon,
            "docs_url": f"{prefix}/docs",
            "raw_app": app
        })
        return self

    def auto_discover(self, apps_dir: Path = APPS_DIR):
        """
        Scans apps_dir for any full-blown FastAPI application and mounts it automatically.
        Checks for:
          - <app>/main.py or <app>/app.py
          - <app>/src/main.py or <app>/src/app.py
        """
        if not apps_dir.exists():
            return

        for item in sorted(apps_dir.iterdir()):
            if not item.name.startswith((".", "_")):
                candidates = [
                    item / "src" / "main.py",
                    item / "src" / "app.py",
                    item / "main.py",
                    item / "app.py",
                ]
                entrypoint = next((c for c in candidates if c.exists()), None)

                if entrypoint:
                    src_dir = entrypoint.parent
                    # Append (never insert at index 0) to avoid shadowing marketplace main.py
                    if str(src_dir) not in sys.path:
                        sys.path.append(str(src_dir))
                    if str(item) not in sys.path:
                        sys.path.append(str(item))

                    module_name = f"apps_{item.name.replace('-', '_')}"
                    spec = importlib.util.spec_from_file_location(module_name, str(entrypoint))
                    if spec and spec.loader:
                        module = importlib.util.module_from_spec(spec)
                        sys.modules[module_name] = module
                        spec.loader.exec_module(module)
                        sub_app = getattr(module, "app", None)
                        if isinstance(sub_app, FastAPI):
                            icon = "📊" if "asset" in item.name.lower() else "📦"
                            self.register(sub_app, path=f"/{item.name}", icon=icon)


# -------------------------------------------------------------
# Initialize Marketplace Platform
# -------------------------------------------------------------
marketplace = FastAPIMarketplace()

# Auto-discover any real FastAPI applications placed in the `apps/` directory
marketplace.auto_discover(APPS_DIR)

app = marketplace.main_app


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="FastAPI App Marketplace")
    parser.add_argument("--port", "-p", type=int, default=8080, help="Port to run on (default: 8080)")
    parser.add_argument("--host", "-H", type=str, default="0.0.0.0", help="Host to bind (default: 0.0.0.0)")
    parser.add_argument("--reload", action="store_true", default=True, help="Enable auto-reload")
    args = parser.parse_args()

    print(f"🚀 Starting FastAPI Marketplace at http://{args.host}:{args.port}")
    uvicorn.run("main:app", host=args.host, port=args.port, reload=args.reload)
