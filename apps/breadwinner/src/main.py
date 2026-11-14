from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from pydantic import BaseModel
from typing import Optional, List
import datetime
import sqlite3
import os
import re
from sm_database import get_connection, init_db

def extract_live_repo_description(repo_name: str) -> str:
    base_path = f"/home/pannet1/programs/github.com/pannet1/{repo_name}"
    for fname in ["README.md", "AGENTS.md"]:
        fpath = os.path.join(base_path, fname)
        if not os.path.exists(fpath):
            continue
        try:
            with open(fpath, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()
            desc = ""
            m = re.search(r"##\s*(?:Project\s+)?Overview\s*\n+([^#\n][^\n]+)", content, re.IGNORECASE)
            if m:
                desc = m.group(1).strip()
            else:
                lines = [l.strip() for l in content.splitlines()]
                for l in lines:
                    if not l or l.startswith("#") or l.startswith(">") or l.startswith("<") or l.startswith("!["):
                        continue
                    if len(l) > 20:
                        desc = l
                        break
            if desc:
                desc = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', desc)
                desc = re.sub(r'[*_`]', '', desc)
                return desc.strip()
        except Exception:
            pass
    return ""

app = FastAPI(
    title="Breadwinner",
    description="Commercial execution engine & breadwinner persona tracker.",
    version="1.0.0"
)

# ---------------------------------------------------------
# Lifecycle / DB Init
# ---------------------------------------------------------
@app.on_event("startup")
def startup():
    init_db()

# ---------------------------------------------------------
# API Routes
# ---------------------------------------------------------
@app.get("/api/personas", tags=["Personas"], summary="List all 8 Breadwinner Personas")
def list_personas():
    """Returns the 8 canonical Breadwinner Personas with speed to cash, revenue model, and bottlenecks."""
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT * FROM personas ORDER BY slug")
    rows = [dict(r) for r in c.fetchall()]
    conn.close()
    return rows

@app.get("/api/personas/{slug}", tags=["Personas"], summary="Get persona by slug with actions")
def get_persona(slug: str):
    """Returns a single Breadwinner Persona along with all its repo actions and commercial objectives."""
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT * FROM personas WHERE slug = ?", (slug,))
    row = c.fetchone()
    if not row:
        conn.close()
        raise HTTPException(status_code=404, detail=f"Persona '{slug}' not found")
    data = dict(row)
    c.execute("SELECT * FROM persona_repo_actions WHERE persona_slug = ?", (slug,))
    data["repo_actions"] = [dict(r) for r in c.fetchall()]
    conn.close()
    return data

class PersonaUpdate(BaseModel):
    value: Optional[int] = None
    bottleneck: Optional[str] = None
    revenue_model: Optional[str] = None
    speed_to_cash: Optional[str] = None
    what_you_do: Optional[str] = None
    active_lead_summary: Optional[str] = None

@app.put("/api/personas/{slug}", tags=["Personas"], summary="Update persona attributes and value")
def update_persona(slug: str, update: PersonaUpdate):
    """Updates a persona's attributes including commercial value, revenue model, or bottleneck."""
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT * FROM personas WHERE slug = ?", (slug,))
    row = c.fetchone()
    if not row:
        conn.close()
        raise HTTPException(status_code=404, detail=f"Persona '{slug}' not found")
    cur = dict(row)
    c.execute("""
    UPDATE personas SET value = ?, bottleneck = ?, revenue_model = ?, speed_to_cash = ?, what_you_do = ?, active_lead_summary = ?
    WHERE slug = ?
    """, (
        update.value if update.value is not None else cur.get("value", 0),
        update.bottleneck if update.bottleneck is not None else cur.get("bottleneck"),
        update.revenue_model if update.revenue_model is not None else cur.get("revenue_model"),
        update.speed_to_cash if update.speed_to_cash is not None else cur.get("speed_to_cash"),
        update.what_you_do if update.what_you_do is not None else cur.get("what_you_do"),
        update.active_lead_summary if update.active_lead_summary is not None else cur.get("active_lead_summary"),
        slug
    ))
    conn.commit()
    conn.close()
    return {"status": "updated", "persona_slug": slug}

# ---------------------------------------------------------
# Persona Repo Actions API (Persona -> Repo -> Action -> Objective)
# ---------------------------------------------------------
class PersonaActionCreate(BaseModel):
    persona_slug: str
    repo: str
    action: str
    objective: str

@app.get("/api/persona-actions", tags=["Persona Actions"], summary="List persona repo actions")
def list_persona_actions(persona_slug: Optional[str] = None, repo: Optional[str] = None):
    """List persona-repo actions and commercial objectives. Filterable by persona_slug or repo."""
    conn = get_connection()
    c = conn.cursor()
    query = "SELECT * FROM persona_repo_actions WHERE 1=1"
    params = []
    if persona_slug:
        query += " AND persona_slug = ?"
        params.append(persona_slug)
    if repo:
        query += " AND repo = ?"
        params.append(repo)
    query += " ORDER BY id"
    c.execute(query, params)
    rows = [dict(r) for r in c.fetchall()]
    conn.close()
    return rows

@app.post("/api/persona-actions", tags=["Persona Actions"], summary="Add or update persona repo action")
def create_or_update_persona_action(item: PersonaActionCreate):
    """Bind or update an action on a repo to a persona with commercial objective."""
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT slug FROM personas WHERE slug = ?", (item.persona_slug,))
    if not c.fetchone():
        conn.close()
        raise HTTPException(status_code=400, detail=f"Persona '{item.persona_slug}' not found")
    c.execute("""
    INSERT INTO persona_repo_actions (persona_slug, repo, action, objective)
    VALUES (?, ?, ?, ?)
    ON CONFLICT(persona_slug, repo, action) DO UPDATE SET
        objective = excluded.objective
    """, (item.persona_slug, item.repo, item.action, item.objective))
    conn.commit()
    conn.close()
    return {"status": "saved", "persona_slug": item.persona_slug, "repo": item.repo}

@app.get("/api/agent/repos/{repo_name}", tags=["Agent Intelligence"], summary="Dynamic live repo description")
def get_live_repo(repo_name: str):
    """Inspects local workspace for repo_name and dynamically extracts overview from AGENTS.md / README.md."""
    desc = extract_live_repo_description(repo_name)
    base_path = f"/home/pannet1/programs/github.com/pannet1/{repo_name}"
    exists = os.path.exists(base_path)
    return {
        "repo": repo_name,
        "exists_locally": exists,
        "path": base_path if exists else None,
        "live_description": desc
    }

# ---------------------------------------------------------
# Agent Intelligence Endpoints (.well-known / agent spec)
# ---------------------------------------------------------
@app.get("/.well-known/agent.json", tags=["Agent Intelligence"], summary="Machine-readable agent capability spec")
def agent_spec():
    return {
        "schema_version": "v1",
        "name_for_model": "breadwinner_engine",
        "name_for_human": "Breadwinner Commercial Execution Engine",
        "description_for_model": (
            "Autonomous commercial execution and memory engine for AI agents. Governs 8 Breadwinner Personas, "
            "monetization models, bottlenecks, persona integer values, repo actions and objectives, commercial campaigns "
            "with human decision gates, and chronological real-world field actions for the human executor."
        ),
        "description_for_human": "Autonomous commercial memory, persona registry, and field action schedule.",
        "api": {"type": "openapi", "url": "/openapi.json"},
        "endpoints": {
            "summary": {"method": "GET", "path": "/api/agent/summary", "description": "Unified commercial snapshot (personas, values, bottlenecks, repo actions, pending tasks, active campaign)"},
            "personas": {"method": "GET", "path": "/api/personas", "description": "List all 8 personas with bottlenecks, revenue models, and integer commercial values"},
            "persona_detail": {"method": "GET", "path": "/api/personas/{slug}", "description": "Get persona detail and its bound repo actions"},
            "update_persona": {"method": "PUT", "path": "/api/personas/{slug}", "description": "Update persona commercial value, bottleneck, or revenue model"},
            "persona_actions": {"method": "GET", "path": "/api/persona-actions", "description": "List all persona-repo actions and objectives"},
            "save_persona_action": {"method": "POST", "path": "/api/persona-actions", "description": "Create or update a persona repo action with objective"},
            "repo_overview": {"method": "GET", "path": "/api/agent/repos/{repo_name}", "description": "Dynamically inspect live README/AGENTS.md for a given repo"},
            "campaigns": {"method": "GET", "path": "/api/campaigns", "description": "List commercial campaigns and decision gate states"},
            "agree_campaign": {"method": "POST", "path": "/api/campaigns/{slug}/agree", "description": "Human decision gate: agree and activate campaign"},
            "disagree_campaign": {"method": "POST", "path": "/api/campaigns/{slug}/disagree", "description": "Human decision gate: reject campaign"},
            "actions": {"method": "GET", "path": "/api/actions", "description": "List today's chronological field schedule"},
            "create_action": {"method": "POST", "path": "/api/actions", "description": "Add new field action to human queue"},
            "update_action": {"method": "PUT", "path": "/api/actions/{action_id}", "description": "Update status or details of a field action"}
        }
    }

@app.get("/api/agent/summary", tags=["Agent Intelligence"], summary="Snapshot of all commercial memory")
def agent_summary():
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT * FROM campaigns WHERE status = 'active' LIMIT 1")
    camp = c.fetchone()
    c.execute("SELECT * FROM personas ORDER BY slug")
    personas = [dict(r) for r in c.fetchall()]
    c.execute("SELECT * FROM persona_repo_actions ORDER BY id")
    actions = [dict(r) for r in c.fetchall()]
    c.execute("SELECT * FROM active_actions ORDER BY time, id")
    daily = [dict(r) for r in c.fetchall()]
    conn.close()
    return {
        "active_campaign": dict(camp) if camp else None,
        "personas_count": len(personas),
        "personas": personas,
        "repo_actions": actions,
        "pending_field_actions": [a for a in daily if a.get("status") != "done"]
    }

# ---------------------------------------------------------
# Active Actions API (replaces data/REBOOT_PLAN.yaml active_actions)
# ---------------------------------------------------------
@app.get("/api/actions", tags=["Field Actions"], summary="List today's field actions")
def get_actions():
    conn = get_connection()
    c = conn.cursor()
    rows = [dict(r) for r in c.execute("SELECT * FROM active_actions ORDER BY time, id")]
    meta = {r["key"]: r["value"] for r in c.execute("SELECT key, value FROM plan_meta")}
    conn.close()
    return {"mission": meta.get("mission"), "updated": meta.get("updated"), "actions": rows}

class ActionCreate(BaseModel):
    task: str
    action: str
    time: Optional[str] = None
    repo: Optional[str] = None
    persona_slug: Optional[str] = None
    campaign_slug: Optional[str] = None

@app.post("/api/actions", tags=["Field Actions"], summary="Create a new field action")
def create_action(item: ActionCreate):
    conn = get_connection()
    c = conn.cursor()
    c.execute("""
    INSERT INTO active_actions (task, action, time, status, repo, persona_slug, campaign_slug)
    VALUES (?, ?, ?, 'pending', ?, ?, ?)
    """, (item.task, item.action, item.time, item.repo, item.persona_slug, item.campaign_slug))
    new_id = c.lastrowid
    conn.commit()
    conn.close()
    return {"status": "created", "action_id": new_id}

class ActionUpdate(BaseModel):
    status: Optional[str] = None
    task: Optional[str] = None
    action: Optional[str] = None
    time: Optional[str] = None
    repo: Optional[str] = None
    persona_slug: Optional[str] = None
    campaign_slug: Optional[str] = None

@app.put("/api/actions/{action_id}", tags=["Field Actions"], summary="Update a field action")
def update_action(action_id: int, update: ActionUpdate):
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT * FROM active_actions WHERE id = ?", (action_id,))
    row = c.fetchone()
    if not row:
        conn.close()
        raise HTTPException(status_code=404, detail="Action not found")
    cur = dict(row)
    c.execute("""
    UPDATE active_actions SET task = ?, action = ?, time = ?, status = ?, repo = ?, persona_slug = ?, campaign_slug = ? WHERE id = ?
    """, (
        update.task if update.task is not None else cur["task"],
        update.action if update.action is not None else cur["action"],
        update.time if update.time is not None else cur["time"],
        update.status if update.status is not None else cur["status"],
        update.repo if update.repo is not None else cur.get("repo"),
        update.persona_slug if update.persona_slug is not None else cur.get("persona_slug"),
        update.campaign_slug if update.campaign_slug is not None else cur.get("campaign_slug"),
        action_id,
    ))
    conn.commit()
    conn.close()
    return {"status": "updated", "action_id": action_id}

@app.post("/api/actions/export")
def export_actions():
    from migrate_yaml import export_tasks_json
    path, n = export_tasks_json()
    return {"status": "exported", "count": n, "path": path}

# ---------------------------------------------------------
# Campaigns API (Decision Gate: AI Proposes Campaigns -> Human Agrees/Disagrees)
# ---------------------------------------------------------
@app.get("/api/campaigns")
def list_campaigns():
    conn = get_connection()
    c = conn.cursor()
    rows = [dict(r) for r in c.execute("""
        SELECT * FROM campaigns
        ORDER BY CASE status WHEN 'proposed' THEN 1 WHEN 'active' THEN 2 ELSE 3 END, slug
    """)]
    conn.close()
    return {"campaigns": rows}

@app.post("/api/campaigns/{slug}/agree")
def agree_campaign(slug: str):
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT * FROM campaigns WHERE slug = ?", (slug,))
    row = c.fetchone()
    if not row:
        conn.close()
        raise HTTPException(status_code=404, detail="Campaign not found")
    c.execute("UPDATE campaigns SET status = 'active' WHERE slug = ?", (slug,))
    conn.commit()
    conn.close()
    return {"status": "active", "campaign_slug": slug}

@app.post("/api/campaigns/{slug}/disagree")
def disagree_campaign(slug: str):
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT * FROM campaigns WHERE slug = ?", (slug,))
    row = c.fetchone()
    if not row:
        conn.close()
        raise HTTPException(status_code=404, detail="Campaign not found")
    c.execute("UPDATE campaigns SET status = 'disagreed' WHERE slug = ?", (slug,))
    conn.commit()
    conn.close()
    return {"status": "disagreed", "campaign_slug": slug}

# ---------------------------------------------------------
# Visual Dashboard UI
# ---------------------------------------------------------
@app.get("/", response_class=HTMLResponse)
@app.get("/dashboard", response_class=HTMLResponse)
def dashboard(request: Request = None):
    if request:
        accept = request.headers.get("accept", "")
        if "application/json" in accept and "text/html" not in accept:
            conn = get_connection()
            c = conn.cursor()
            c.execute("SELECT * FROM campaigns WHERE status = 'active' LIMIT 1")
            active_campaign = c.fetchone()
            conn.close()
            return JSONResponse({
                "status": "online",
                "app": "breadwinner",
                "system_time": datetime.datetime.now().isoformat(),
                "active_campaign": dict(active_campaign) if active_campaign else None,
                "dashboard": "/breadwinner/"
            })

    resp_headers = {
        "Cache-Control": "no-cache, no-store, must-revalidate",
        "Pragma": "no-cache",
        "Expires": "0"
    }
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT * FROM campaigns WHERE status = 'active' LIMIT 1")
    campaign = c.fetchone()
    c.execute("SELECT * FROM personas ORDER BY slug")
    db_personas = [dict(p) for p in c.fetchall()]
    persona_titles = {p["slug"]: p["title"] for p in db_personas}
    today = datetime.date.today().isoformat()
    actions = [dict(r) for r in c.execute("SELECT * FROM active_actions ORDER BY time, id")]
    num_pending_actions = len([a for a in actions if a.get("status") != "done"])
    action_count_html = f'<span class="tab-count">{num_pending_actions}</span>' if num_pending_actions > 0 else ''
    mission = c.execute("SELECT value FROM plan_meta WHERE key = 'mission'").fetchone()

    c.execute("SELECT * FROM persona_repo_actions ORDER BY id")
    all_repo_actions = [dict(r) for r in c.fetchall()]

    c.execute("""
        SELECT * FROM campaigns
        ORDER BY CASE status WHEN 'proposed' THEN 1 WHEN 'active' THEN 2 ELSE 3 END, slug
    """)
    campaigns = [dict(r) for r in c.fetchall()]
    conn.close()

    inr = lambda v: f"₹{v:,.0f}"

    timeline_html = ""
    for a in actions:
        done = a.get("status") == "done"
        timeline_html += f"""
        <div class="row{' done' if done else ''}">
          <span class="timechip">{a['time'] or '--:--'}</span>
          <div class="what"><div class="task">{a['task']}</div><div class="detail">{a['action']}</div></div>
          <button class="ok{' do' if not done else ''}" onclick="markAction({a['id']}, {'true' if not done else 'false'})">{'Done' if not done else 'Reopen'}</button>
        </div>"""
    if not timeline_html:
        timeline_html = '<div style="padding:14px;color:#94a3b8;font-size:13px">No active actions logged.</div>'

    # Build Campaigns Tab (AI Proposed Campaigns vs Active)
    num_proposed = len([c for c in campaigns if c["status"] == "proposed"])
    num_active = len([c for c in campaigns if c["status"] == "active"])
    
    camp_cards_html = ""
    for camp in campaigns:
        st = camp.get("status") or "proposed"
        c_slug = camp["slug"]
        c_name = camp["name"]
        repo_info = f"{camp['repo']}{' / ' + camp['module'] if camp.get('module') else ''}" if camp.get('repo') else "Commercial Sprint"
        p_slug = camp.get("persona_slug") or ""
        p_title = persona_titles.get(p_slug, p_slug)
        target_disp = inr(camp.get("target_revenue") or 0)
        rat = camp.get("rationale") or camp.get("module_role") or "Commercial revenue generation drive"
        dates = f"{camp.get('start_date', '')} to {camp.get('end_date', '')}"
        
        if st == "proposed":
            btn_markup = f"""
            <div class="prop-btns">
              <button class="btn-agree" onclick="agreeCampaign('{c_slug}')">✓ Agree &amp; Activate Campaign</button>
              <button class="btn-disagree" onclick="disagreeCampaign('{c_slug}')">✗ Disagree</button>
            </div>
            """
        elif st == "active":
            btn_markup = '<span class="badge-agreed">✓ Active Campaign</span>'
        else:
            btn_markup = '<span class="badge-disagreed">✗ Disagreed</span>'

        camp_cards_html += f"""
        <div class="prop-card {st}">
          <div class="prop-top">
            <div>
              <div class="prop-sys">
                <span class="dot"></span>
                <span>{repo_info}</span>
              </div>
              <div class="prop-task">{c_name}</div>
            </div>
          </div>
          <div class="prop-action">{rat}</div>
          <div class="prop-footer">
            <div class="prop-meta">
              <span>Financial Target: <b style="color:var(--accent-ink)">{target_disp}</b></span>
            </div>
            {btn_markup}
          </div>
        </div>
        """
    if not camp_cards_html:
        camp_cards_html = '<div style="padding:20px;color:#94a3b8;font-size:13px">No campaigns currently available.</div>'

    campaigns_tab_html = f"""
    <section id="tab-campaigns" class="tab-pane">
      <div class="sec-head">
        <div>
          <h2>Campaigns &amp; Decision Gate</h2>
          <span class="note">AI-proposed commercial campaigns mapped to financial goals. Agree to activate and drive the daily field pipeline.</span>
        </div>
        <div style="font-size:12.5px;color:var(--muted)">
          <b style="color:var(--warn)">{num_proposed}</b> proposed · <b style="color:var(--accent-ink)">{num_active}</b> active in flight
        </div>
      </div>
      <div class="prop-grid">{camp_cards_html}</div>
    </section>
    """

    # Build Personas Tab Cards
    p_cards_html = ""
    for p in db_personas:
        slug = p["slug"]
        title = p["title"]
        what_you_do = p.get("what_you_do") or ""
        speed = p.get("speed_to_cash") or "—"
        model = p.get("revenue_model") or ""
        lead_summary = p.get("active_lead_summary") or ""

        spd_low = speed.lower()
        if "immediate" in spd_low or "fast" in spd_low:
            spd_class = "fast"
        elif "retainer" in spd_low:
            spd_class = "retainer"
        elif "frozen" in spd_low:
            spd_class = "frozen"
        else:
            spd_class = "med"

        lead_html = f"""<div class="pcard-lead-box"><b>Commercial Focus:</b> {lead_summary}</div>""" if lead_summary else ""

        # Dynamic Repo Actions & Objectives
        p_repo_actions = [ra for ra in all_repo_actions if ra["persona_slug"] == slug]
        repo_actions_html = ""
        if p_repo_actions:
            items = []
            for ra in p_repo_actions:
                r_name = ra["repo"]
                live_desc = extract_live_repo_description(r_name)
                desc_line = f'<div style="font-size:12px;color:var(--ink-dim);margin:3px 0 4px;line-height:1.4">{live_desc}</div>' if live_desc else ''
                items.append(f"""
                <div style="padding:8px 0;border-bottom:1px dashed var(--line)">
                  <div style="font-size:13px;color:var(--ink)"><b>{r_name}</b> — <span style="color:var(--ink-dim)">{ra['action']}</span></div>
                  {desc_line}
                  <div style="font-size:12.5px;color:var(--accent-ink);margin-top:3px"><b>Objective:</b> {ra['objective']}</div>
                </div>
                """)
            repo_actions_html = f"""
            <div style="background:#f8fafc;border:1px solid var(--line);border-radius:8px;padding:12px 14px;margin-top:6px">
              <div style="font-size:11px;font-weight:800;text-transform:uppercase;color:var(--muted);letter-spacing:.05em;margin-bottom:6px">Repo Actions &amp; Objectives:</div>
              {''.join(items)}
            </div>
            """

        bneck = p.get("bottleneck") or ""
        bneck_html = f"""<div class="pcard-bneck"><b>Current Bottleneck:</b> {bneck}</div>""" if bneck else ""

        p_val = p.get("value") or 0
        val_badge = f'<span class="pcard-val-badge">₹{p_val:,}</span>' if p_val > 0 else '<span class="pcard-val-badge zero">₹0</span>'

        p_cards_html += f"""
        <div class="pcard">
          <div class="pcard-head">
            <div class="pcard-title"><span class="dot"></span>{title}</div>
            <div style="display:flex;gap:8px;align-items:center">
              {val_badge}
              <span class="pcard-badge {spd_class}">{speed}</span>
            </div>
          </div>
          <div class="pcard-desc">{what_you_do}</div>
          <div class="pcard-model"><b>Revenue Model:</b> {model}</div>
          {bneck_html}
          {lead_html}
          {repo_actions_html}
        </div>"""

    personas_tab_html = f"""
    <section id="tab-personas" class="tab-pane">
      <div class="sec-head">
        <div>
          <h2>Breadwinner Personas</h2>
          <span class="note">Commercial roles, revenue models, and active client initiatives</span>
        </div>
      </div>
      <div class="persona-grid">{p_cards_html}</div>
    </section>
    """

    mission_line = mission["value"] if mission else "Commercial revenue first."
    html = f"""<!DOCTYPE html>
<html lang="en" class="dark">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Breadwinner — Commercial Execution Engine</title>
  <script src="https://cdn.tailwindcss.com"></script>
  <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css" />
  <link rel="stylesheet" href="/static/styles.css" />
</head>
<body class="min-h-screen flex flex-col bg-[#0b0f19] text-slate-100">
  <!-- Primary App Navigation Bar -->
  <header class="sticky top-0 z-40 bg-slate-900/90 backdrop-blur-md border-b border-slate-800">
    <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
      <div class="flex items-center justify-between h-16">
        <div class="flex items-center gap-6">
          <a href="/" class="flex items-center gap-3 group">
            <span class="w-10 h-10 rounded-xl bg-gradient-to-tr from-cyan-600 to-indigo-500 flex items-center justify-center text-xl shadow-lg shadow-cyan-500/20 group-hover:scale-105 transition-transform">
              🎯
            </span>
            <div>
              <span class="text-base font-extrabold text-white tracking-tight block">Bread<span class="text-cyan-400">winner</span></span>
              <span class="text-[10px] text-slate-400 font-mono block -mt-1">Commercial Execution Engine</span>
            </div>
          </a>

          <nav class="flex items-center gap-1">
            <a data-tab="actions" class="active px-3 py-1.5 rounded-lg text-xs font-semibold text-slate-300 hover:text-white hover:bg-slate-800/80 transition flex items-center gap-1.5 cursor-pointer" onclick="showTab('actions')">
              <i class="fa-solid fa-list-check text-cyan-400 text-xs"></i> Field Actions {action_count_html}
            </a>
            <a data-tab="campaigns" class="px-3 py-1.5 rounded-lg text-xs font-semibold text-slate-300 hover:text-white hover:bg-slate-800/80 transition flex items-center gap-1.5 cursor-pointer" onclick="showTab('campaigns')">
              <i class="fa-solid fa-bullhorn text-amber-400 text-xs"></i> Campaigns
            </a>
            <a data-tab="personas" class="px-3 py-1.5 rounded-lg text-xs font-semibold text-slate-300 hover:text-white hover:bg-slate-800/80 transition flex items-center gap-1.5 cursor-pointer" onclick="showTab('personas')">
              <i class="fa-solid fa-users text-emerald-400 text-xs"></i> Personas
            </a>
          </nav>
        </div>
        <div class="flex items-center gap-3">
          <a href="/breadwinner/docs" target="_blank" class="px-3 py-1.5 text-xs font-semibold text-slate-300 bg-slate-800 hover:bg-slate-700 rounded-lg border border-slate-700 transition flex items-center gap-1.5">
            <i class="fa-solid fa-code text-cyan-400"></i> API Docs
          </a>
        </div>
      </div>
    </div>
  </header>

  <main class="flex-1 max-w-7xl w-full mx-auto px-4 sm:px-6 lg:px-8 py-8">
    <section id="tab-actions" class="tab-pane active">
      <div class="sec-head">
        <div>
          <h2>Today's Field Actions</h2>
          <span class="note">The human executes these; the engine only records</span>
        </div>
        <button class="px-3.5 py-2 bg-emerald-600 hover:bg-emerald-500 text-white rounded-lg text-xs font-bold transition cursor-pointer flex items-center gap-1.5" onclick="toggleAddAction()">
          <i class="fa-solid fa-plus text-xs"></i> Add Field Action
        </button>
      </div>

      <!-- Quick Add Action Form -->
      <div id="add-action-box" class="glass-card p-5 mb-6" style="display:none;">
        <div class="text-sm font-bold text-white mb-3">Add Real-World Field Action</div>
        <div class="grid grid-cols-1 sm:grid-cols-[100px_1fr_2fr_auto] gap-3 items-center">
          <input id="new-action-time" type="text" placeholder="10:00" class="px-3 py-2 bg-slate-900 border border-slate-700 rounded-lg text-xs text-slate-100 placeholder-slate-500 focus:outline-none focus:border-cyan-500" />
          <input id="new-action-task" type="text" placeholder="Task name / Client" class="px-3 py-2 bg-slate-900 border border-slate-700 rounded-lg text-xs text-slate-100 placeholder-slate-500 focus:outline-none focus:border-cyan-500" />
          <input id="new-action-detail" type="text" placeholder="Specific action / visit / call detail" class="px-3 py-2 bg-slate-900 border border-slate-700 rounded-lg text-xs text-slate-100 placeholder-slate-500 focus:outline-none focus:border-cyan-500" />
          <div class="flex gap-2">
            <button class="px-4 py-2 bg-emerald-600 hover:bg-emerald-500 text-white rounded-lg text-xs font-bold transition cursor-pointer" onclick="submitNewAction()">Save</button>
            <button class="px-3 py-2 bg-slate-800 hover:bg-slate-700 text-slate-300 border border-slate-700 rounded-lg text-xs font-semibold transition cursor-pointer" onclick="toggleAddAction()">Cancel</button>
          </div>
        </div>
      </div>

      <div class="timeline">{timeline_html}</div>
    </section>

    {campaigns_tab_html}

    {personas_tab_html}
  </main>

  <footer class="border-t border-slate-800/80 bg-slate-950/60 py-6 mt-12 text-center text-xs text-slate-500">
    <div class="max-w-7xl mx-auto px-4 flex flex-col sm:flex-row items-center justify-between gap-3">
      <p>Breadwinner Execution Engine • Database-First</p>
      <div class="flex items-center gap-4">
        <span class="font-mono text-cyan-400">Commercial Cash Flow First</span>
      </div>
    </div>
  </footer>
<script>
function showTab(name) {{
  document.querySelectorAll('.tab-pane').forEach(el => el.classList.remove('active'));
  document.querySelectorAll('header nav a').forEach(el => {{
    el.classList.remove('active', 'bg-cyan-500/10', 'text-cyan-400', 'border', 'border-cyan-500/30');
    el.classList.add('text-slate-300');
  }});
  const target = document.getElementById('tab-' + name);
  if (target) target.classList.add('active');
  const btn = document.querySelector('header nav a[data-tab="' + name + '"]');
  if (btn) {{
    btn.classList.add('active', 'bg-cyan-500/10', 'text-cyan-400', 'border', 'border-cyan-500/30');
    btn.classList.remove('text-slate-300');
  }}
  history.replaceState(null, null, '#' + name);
}}
window.addEventListener('DOMContentLoaded', () => {{
  let hash = (location.hash || '#actions').replace('#', '');
  if (!['actions', 'campaigns', 'personas'].includes(hash)) {{
    hash = 'actions';
  }}
  showTab(hash);
}});
window.addEventListener('hashchange', () => {{
  let hash = (location.hash || '#actions').replace('#', '');
  if (['actions', 'campaigns', 'personas'].includes(hash)) {{
    showTab(hash);
  }}
}});

const API_BASE = window.location.pathname.startsWith('/breadwinner') ? '/breadwinner' : (window.location.pathname.startsWith('/sales-marketing') ? '/sales-marketing' : '');

async function agreeCampaign(slug) {{
  const r = await fetch(API_BASE + '/api/campaigns/' + slug + '/agree', {{method: 'POST'}});
  if (r.ok) {{
    location.hash = '#campaigns';
    location.reload();
  }}
}}
async function disagreeCampaign(slug) {{
  const r = await fetch(API_BASE + '/api/campaigns/' + slug + '/disagree', {{method: 'POST'}});
  if (r.ok) {{
    location.hash = '#campaigns';
    location.reload();
  }}
}}

async function markAction(id, done) {{
  await fetch(API_BASE + '/api/actions/' + id, {{method: 'PUT', headers: {{'Content-Type': 'application/json'}},
    body: JSON.stringify({{status: done ? 'done' : 'pending'}})}});
  location.reload();
}}
function toggleAddAction() {{
  const el = document.getElementById('add-action-box');
  if (el) {{
    el.style.display = el.style.display === 'none' ? 'block' : 'none';
    if (el.style.display === 'block') document.getElementById('new-action-task').focus();
  }}
}}
async function submitNewAction() {{
  const time = document.getElementById('new-action-time').value.trim() || '10:00';
  const task = document.getElementById('new-action-task').value.trim();
  const detail = document.getElementById('new-action-detail').value.trim();
  if (!task || !detail) {{
    alert('Please enter both a task name and action details.');
    return;
  }}
  const r = await fetch(API_BASE + '/api/actions', {{
    method: 'POST',
    headers: {{'Content-Type': 'application/json'}},
    body: JSON.stringify({{time: time, task: task, action: detail}})
  }});
  if (r.ok) {{
    location.reload();
  }}
}}
async function exportTasks() {{
  const r = await fetch(API_BASE + '/api/actions/export', {{method: 'POST'}});
  const j = await r.json();
  alert(j.status + ': ' + j.count + ' tasks → ' + j.path);
}}
</script>
</body></html>"""
    return HTMLResponse(content=html, headers=resp_headers)
