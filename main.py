import argparse
import importlib.util
import inspect
from pathlib import Path
import re
import sys
from typing import Any, Dict, List, Optional
from fastapi import FastAPI, Query, Request
from fastapi.responses import HTMLResponse, JSONResponse, PlainTextResponse, RedirectResponse
import uvicorn

import unified_agent
from agent_hub_ui import render_agent_hub_html

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
    # Rewrite href='/...' action='/...' src='/...' except external URLs, already prefixed, or root /agent routes
    pattern = r'((?:href|action|src)=[\"\'])/(?!/|agent(?:/|[\"\'])|' + re.escape(prefix.lstrip("/")) + r'/|https?://)([^\"\']*)[\"\']'
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
                            if loc.startswith("/") and not loc.startswith(self.prefix + "/") and not loc.startswith("/agent") and loc != "/":
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

        # -------------------------------------------------------------
        # AI Agent & Machine-Readable Intelligence Gateway
        # -------------------------------------------------------------
        @self.main_app.get("/llms.txt", response_class=PlainTextResponse)
        def get_llms_txt():
            """Standard llms.txt discovery index for AI Agents and LLMs."""
            return unified_agent.LLMS_TXT_CONTENT

        @self.main_app.get("/llms-full.txt", response_class=PlainTextResponse)
        def get_llms_full_txt():
            """Comprehensive agent instructions and schema definitions."""
            return unified_agent.LLMS_FULL_TXT_CONTENT

        @self.main_app.get("/.well-known/agent.json")
        def get_agent_plugin_manifest():
            """Plugin manifest for AI agent discovery."""
            return {
                "schema_version": "v1",
                "name_for_model": "financial_and_business_intelligence",
                "name_for_human": "FastAPI Financial & Business Intelligence",
                "description_for_model": "Extracts summaries on personal finance (envelopes, cashflow, budgets) and business performance (revenue, COGS, margin, inventory, receivables, valuation).",
                "description_for_human": "Personal Finance and Business Performance intelligence for AI agents.",
                "api": {"type": "openapi", "url": "/openapi.json"},
                "llms_txt": "/llms.txt",
                "tools_schema": "/agent/tools.json",
            }

        @self.main_app.get("/agent/tools.json")
        def get_agent_tools():
            """Pre-built function calling schemas (OpenAI / Anthropic / Gemini format)."""
            return {"tools": unified_agent.AGENT_TOOLS_SCHEMA}

        @self.main_app.get("/agent/summary")
        @self.main_app.get("/api/agent/summary")
        def get_agent_summary(
            month: Optional[int] = Query(None, description="Personal finance month (1-12)"),
            year: Optional[int] = Query(None, description="Personal finance year"),
            format: str = Query("json", description="Format: 'json' or 'markdown'"),
        ):
            """
            Unified Agent Endpoint: Returns combined Personal Finance and Business Performance summary.
            Sub-5ms response time, high-density machine-readable format.
            """
            res = unified_agent.get_unified_summary(month=month, year=year, fmt=format)
            if format == "markdown":
                return PlainTextResponse(res["markdown"])
            return res

        @self.main_app.get("/agent/brief", response_class=PlainTextResponse)
        def get_agent_brief(
            month: Optional[int] = Query(None, description="Personal finance month"),
            year: Optional[int] = Query(None, description="Personal finance year"),
        ):
            """Returns token-optimized Markdown briefing ready for LLM context injection."""
            res = unified_agent.get_unified_summary(month=month, year=year, fmt="markdown")
            return res["markdown"]

        @self.main_app.get("/agent/personal-finance")
        def get_agent_personal_finance(
            month: Optional[int] = Query(None),
            year: Optional[int] = Query(None),
            format: str = Query("json"),
        ):
            """Dedicated personal finance breakdown (cashflow, envelopes, budget vs actual)."""
            res = unified_agent.get_personal_finance_summary(
                unified_agent.PF_MASTER_FILE,
                unified_agent.PF_CATEGORIES_FILE,
                month=month,
                year=year,
                fmt=format,
            )
            if format == "markdown":
                return PlainTextResponse(res["markdown"])
            return res

        @self.main_app.get("/agent/business-performance")
        def get_agent_business_performance(format: str = Query("json")):
            """Dedicated business performance breakdown (revenue, COGS, receivables, inventory, valuation)."""
            db = unified_agent.am_db.SessionLocal()
            try:
                res = unified_agent.get_business_performance_summary(db, fmt=format)
            finally:
                db.close()
            if format == "markdown":
                return PlainTextResponse(res["markdown"])
            return res

        @self.main_app.get("/agent/query")
        def get_agent_query(
            q: str = Query(..., description="Query keyword: net_worth, revenue, debtors, budget, inventory, alerts"),
            month: Optional[int] = Query(None),
            year: Optional[int] = Query(None),
        ):
            """Sub-millisecond parameter resolver for targeted agent questions."""
            return unified_agent.query_quick_metric(q=q, month=month, year=year)

        @self.main_app.get("/agent", response_class=HTMLResponse)
        def agent_hub_page(request: Request):
            """Interactive Human & AI Agent Intelligence Portal."""
            summary_data = unified_agent.get_unified_summary()
            markdown_brief = unified_agent.get_unified_summary(fmt="markdown")["markdown"]
            return render_agent_hub_html(summary_data, markdown_brief)

        # Marketplace Storefront UI
        @self.main_app.get("/", response_class=HTMLResponse)
        def marketplace_home(request: Request):
            cards_html = ""
            if not self.registry:
                cards_html = """
                <div class="col-span-full text-center py-16 px-6 bg-slate-900 border border-dashed border-slate-800 rounded-3xl">
                    <div class="text-4xl mb-3">🧩</div>
                    <h3 class="text-lg font-bold text-white mb-2">No Applications Integrated Yet</h3>
                    <p class="text-slate-400 text-xs max-w-md mx-auto leading-relaxed">
                        To integrate any existing FastAPI app, drop its folder into <code class="text-indigo-400 font-mono">apps/&lt;app_name&gt;</code>, or register it programmatically via <code class="text-indigo-400 font-mono">marketplace.register(app, path="/your-path")</code>.
                    </p>
                </div>
                """
            else:
                for item in self.registry:
                    cards_html += f"""
                    <div class="glass-card rounded-2xl p-6 border border-slate-800 flex flex-col justify-between transition-all duration-200 hover:-translate-y-1 hover:shadow-2xl hover:border-indigo-500/40">
                        <div>
                            <div class="w-14 h-14 rounded-2xl bg-slate-800/90 border border-slate-700/80 flex items-center justify-center text-3xl mb-4 shadow-inner">
                                {item['icon']}
                            </div>
                            <h2 class="text-xl font-bold text-white tracking-tight mb-1">{item['name']}</h2>
                            <p class="text-xs text-slate-400 leading-relaxed mb-4 line-clamp-3">{item['description']}</p>
                            <div class="mb-6">
                                <span class="bg-slate-950 text-cyan-400 px-3 py-1 rounded-lg text-xs font-mono border border-slate-800">
                                    Mount: {item['path']}
                                </span>
                            </div>
                        </div>
                        <div class="flex items-center gap-3 pt-4 border-t border-slate-800/80">
                            <a href="{item['path']}" class="flex-1 py-2.5 text-center bg-indigo-600 hover:bg-indigo-500 text-white rounded-xl text-xs font-bold transition shadow-lg shadow-indigo-600/20 flex items-center justify-center gap-2">
                                <span>Launch App</span>
                                <i class="fa-solid fa-arrow-up-right-from-square text-[10px]"></i>
                            </a>
                            <a href="{item['docs_url']}" target="_blank" class="px-3.5 py-2.5 bg-slate-800 hover:bg-slate-700 text-slate-300 rounded-xl text-xs font-bold transition border border-slate-700">
                                Docs
                            </a>
                        </div>
                    </div>
                    """

            return f"""<!doctype html>
            <html lang="en" class="dark">
            <head>
                <meta charset="UTF-8" />
                <meta name="viewport" content="width=device-width, initial-scale=1.0" />
                <title>{title}</title>
                <script src="https://cdn.tailwindcss.com"></script>
                <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css" />
                <style>
                    body {{ background-color: #0b0f19; color: #f1f5f9; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; }}
                    .glass-card {{ background: rgba(30, 41, 59, 0.7); backdrop-filter: blur(8px); border: 1px solid rgba(255, 255, 255, 0.08); }}
                    .glass-card:hover {{ border-color: rgba(99, 102, 241, 0.3); }}
                </style>
            </head>
            <body class="min-h-screen flex flex-col bg-[#0b0f19] text-slate-100">
                <!-- Navigation -->
                <header class="sticky top-0 z-40 bg-slate-900/90 backdrop-blur-md border-b border-slate-800">
                    <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
                        <div class="flex items-center justify-between h-16">
                            <div class="flex items-center gap-3">
                                <span class="w-10 h-10 rounded-xl bg-gradient-to-tr from-indigo-600 to-cyan-500 flex items-center justify-center text-xl shadow-lg shadow-indigo-500/20">
                                    ⚡
                                </span>
                                <div>
                                    <span class="text-base font-extrabold text-white tracking-tight block">FastAPI <span class="text-indigo-400">Marketplace</span></span>
                                    <span class="text-[10px] text-slate-400 font-mono block -mt-1">Application Hub</span>
                                </div>
                            </div>
                            <div class="flex items-center gap-3">
                                <a href="/agent" class="px-3 py-1.5 text-xs font-semibold text-indigo-400 bg-indigo-500/10 hover:bg-indigo-500/20 rounded-lg border border-indigo-500/30 transition flex items-center gap-1.5">
                                    <i class="fa-solid fa-robot text-indigo-400"></i> AI Agent Hub
                                </a>
                                <a href="/docs" target="_blank" class="px-3 py-1.5 text-xs font-semibold text-slate-300 bg-slate-800 hover:bg-slate-700 rounded-lg border border-slate-700 transition flex items-center gap-1.5">
                                    <i class="fa-solid fa-code text-cyan-400"></i> Core API Docs
                                </a>
                            </div>
                        </div>
                    </div>
                </header>

                <!-- Hero Section -->
                <main class="flex-1 max-w-7xl w-full mx-auto px-4 sm:px-6 lg:px-8 py-8">
                    <div class="mb-10 bg-gradient-to-r from-slate-900 via-indigo-950/40 to-slate-900 p-8 rounded-3xl border border-slate-800 shadow-xl">
                        <div class="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-indigo-500/10 border border-indigo-500/20 text-indigo-400 text-xs font-semibold mb-3">
                            <i class="fa-solid fa-rocket text-xs"></i> Pluggable Multi-App Ecosystem
                        </div>
                        <h1 class="text-3xl sm:text-4xl font-extrabold text-white tracking-tight">
                            FastAPI App <span class="text-transparent bg-clip-text bg-gradient-to-r from-indigo-400 to-cyan-400">Marketplace</span>
                        </h1>
                        <p class="text-slate-400 text-sm max-w-2xl mt-2 leading-relaxed">
                            Seamlessly integrate, discover, and launch independent full-blown FastAPI applications under a unified domain.
                        </p>
                    </div>

                    <!-- AI Agent Intelligence Featured Banner -->
                    <div class="mb-8 p-6 rounded-3xl bg-gradient-to-r from-indigo-950/80 via-purple-950/50 to-slate-900 border border-indigo-500/30 flex flex-col md:flex-row md:items-center justify-between gap-6 shadow-2xl">
                        <div>
                            <div class="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-indigo-500/20 text-indigo-300 text-[11px] font-mono font-bold mb-2.5">
                                🤖 AI AGENT & FINANCIAL INTELLIGENCE LAYER
                            </div>
                            <h2 class="text-xl font-bold text-white tracking-tight">Extract Instant Personal Finance & Business Performance</h2>
                            <p class="text-xs text-slate-400 mt-1.5 max-w-2xl leading-relaxed">
                                Token-optimized summaries, net worth synthesis, envelope budget tracking, and sales ledger analysis designed specifically for autonomous AI agents and pair-programming LLMs.
                            </p>
                        </div>
                        <div class="flex flex-wrap items-center gap-2.5 shrink-0">
                            <a href="/agent" class="px-4 py-2.5 bg-indigo-600 hover:bg-indigo-500 text-white rounded-xl text-xs font-bold transition shadow-lg shadow-indigo-600/30 flex items-center gap-2">
                                <i class="fa-solid fa-robot"></i>
                                <span>Open Agent Hub</span>
                            </a>
                            <a href="/agent/summary" target="_blank" class="px-3.5 py-2.5 bg-slate-800 hover:bg-slate-700 text-cyan-300 rounded-xl text-xs font-mono font-semibold border border-slate-700 transition">
                                /agent/summary
                            </a>
                            <a href="/agent/brief" target="_blank" class="px-3.5 py-2.5 bg-slate-800 hover:bg-slate-700 text-emerald-300 rounded-xl text-xs font-mono font-semibold border border-slate-700 transition">
                                /agent/brief
                            </a>
                            <a href="/llms.txt" target="_blank" class="px-3.5 py-2.5 bg-slate-800 hover:bg-slate-700 text-amber-300 rounded-xl text-xs font-mono font-semibold border border-slate-700 transition">
                                /llms.txt
                            </a>
                        </div>
                    </div>

                    <!-- App Cards Grid -->
                    <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                        {cards_html}
                    </div>
                </main>

                <!-- Footer -->
                <footer class="border-t border-slate-800/80 bg-slate-950/60 py-6 mt-12 text-center text-xs text-slate-500">
                    <div class="max-w-7xl mx-auto px-4 flex flex-col sm:flex-row items-center justify-between gap-3">
                        <p>FastAPI App Marketplace • Unified Architecture</p>
                        <div class="flex items-center gap-4">
                            <span class="font-mono text-indigo-400">{len(self.registry)} Applications Mounted</span>
                        </div>
                    </div>
                </footer>
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

                        # Auto-resolve relative data file paths if defined in the module
                        for var_name in ["MASTER_FILE", "CATEGORIES_FILE", "DATA_FILE", "DB_FILE"]:
                            if hasattr(module, var_name):
                                val = getattr(module, var_name)
                                if isinstance(val, str) and not Path(val).is_absolute():
                                    setattr(module, var_name, str((src_dir / val).resolve()))

                        sub_app = getattr(module, "app", None)
                        if isinstance(sub_app, FastAPI):
                            icon = "📊" if "asset" in item.name.lower() else ("💰" if "finance" in item.name.lower() else "📦")
                            self.register(sub_app, path=f"/{item.name}", icon=icon)


# -------------------------------------------------------------
# Initialize Marketplace Platform
# -------------------------------------------------------------
marketplace = FastAPIMarketplace()

# Auto-discover any real FastAPI applications placed in the `apps/` directory
marketplace.auto_discover(APPS_DIR)

app = marketplace.main_app


PORT = 11173

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="FastAPI App Marketplace")
    parser.add_argument("--port", "-p", type=int, default=PORT, help=f"Port to run on (default: {PORT})")
    parser.add_argument("--host", "-H", type=str, default="0.0.0.0", help="Host to bind (default: 0.0.0.0)")
    parser.add_argument("--reload", action="store_true", default=False, help="Enable auto-reload")
    args = parser.parse_args()

    print(f"🚀 Starting FastAPI Marketplace at http://{args.host}:{args.port}")
    uvicorn.run("main:app", host=args.host, port=args.port, reload=args.reload)
