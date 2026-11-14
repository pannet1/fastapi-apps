# Sales & Marketing — Commercial Execution Engine

> **Scope**: `private-telemetry`  
> **Persona Alignment**: `Business Automation Expert`  
> **Mission**: Enforce daily commercial discovery execution, eliminate unmonetized engineering rabbit holes, and track the cash sprint to break the zero-income freeze.

---

## 🎯 Architecture & Design Intent

`sales-marketing` is the **inter-agent commercial memory and campaign dispatch plane**.

- **Agent Role**: AI agents read commercial states, query 8 canonical Breadwinner Personas, bind actions to repositories with integer values, propose revenue campaigns, and dynamically populate the human's daily physical task schedule (`active_actions` exported to `~/tasks.json`).
- **Human Role**: Strictly the real-world field executor—making calls, visiting repair shops, delivering completed hardware, and collecting physical cash. The human also reviews AI-proposed campaigns via a one-click Agree/Disagree decision gate.
- **Live Repo Context**: Repository descriptions and statuses are extracted dynamically at runtime from each project's live `AGENTS.md` and `README.md`, eliminating stale static markdown caches.

---

## 🤖 Agent API Endpoints

All endpoints return machine-readable JSON and are fully described via OpenAPI (`/docs` & `/openapi.json`).

| Endpoint | Method | Description |
|---|---|---|
| `/.well-known/agent.json` | `GET` | Machine-readable capability specification and tool discovery manifest |
| `/api/agent/summary` | `GET` | Snapshot of active campaign, 8 personas, values, bottlenecks, repo actions, and pending tasks |
| `/api/agent/repos/{repo}` | `GET` | Dynamic disk extraction of project overview from live repository |
| `/api/personas` | `GET` | List 8 Breadwinner Personas with values, speed to cash, revenue model, and bottlenecks |
| `/api/personas/{slug}` | `GET`, `PUT` | Persona details with bound repo actions, or update commercial value and attributes |
| `/api/persona-actions` | `GET`, `POST` | Query or bind repo actions and commercial objectives to personas |
| `/api/campaigns` | `GET` | Commercial campaigns with human decision gate states (`proposed`, `active`, `disagreed`) |
| `/api/campaigns/{slug}/agree` | `POST` | Human decision gate: agree and activate campaign |
| `/api/campaigns/{slug}/disagree` | `POST` | Human decision gate: disagree / reject campaign |
| `/api/actions` | `GET`, `POST` | List or append to today's chronological field action queue |
| `/api/actions/{id}` | `PUT` | Mark status (`done`/`pending`) or edit field task details |

---

## 🖥️ Human Dashboard (`/dashboard`)

The dashboard provides a WCAG AAA compliant, high-contrast visual interface for the human operator:
- **Field Actions Tab**: Chronological field schedule with inline "+ Add Field Action" form and one-click Done/Reopen toggles.
- **Campaigns Tab (Decision Gate)**: Review AI-proposed commercial sprints with one-click "Agree & Activate" or "Disagree" buttons.
- **Personas Tab**: All 8 Breadwinner Personas displayed with integer commercial values (`₹X,XXX`), monetization models, current bottlenecks, and live-extracted repo actions and objectives.

---

## 📊 Database Schema (`data/sales.db`)

1. **`personas`**: Canonical commercial identities with `value` (`INTEGER`), speed to cash, revenue model, and active bottlenecks.
2. **`persona_repo_actions`**: Relational actions `(persona_slug, repo, action, objective)`.
3. **`campaigns`**: Time-bound commercial drives with target revenue and human decision gate status.
4. **`active_actions`**: Chronological real-world task schedule executed by the human.
5. **`plan_meta`**: Key-value metadata table (`mission`, `updated`).

---

## 🚀 Quickstart

### 1. Seed Database
```bash
python seed.py
```

### 2. Run API & Dashboard
```bash
uvicorn main:app --port 11174 --reload
# View dashboard at: http://localhost:11174/dashboard
# Agent discovery manifest: http://localhost:11174/.well-known/agent.json
# OpenAPI docs: http://localhost:11174/docs
```
