"""One-shot import of data/MASTER_INTENT.yaml and data/REBOOT_PLAN.yaml into sales.db.

After this runs, the system reads intent and daily actions from the database only:
the YAML files are no longer needed. Re-run any time to re-import fresh YAML.

Usage:
    python migrate_yaml.py            # import both files if present
    python migrate_yaml.py --strict   # fail if a file is missing
"""
import os
import sys
import yaml
from sm_database import get_connection, init_db

# Where the YAML artifacts are looked up, newest location first.
SEARCH_PATHS = [
    os.path.expanduser("~/firstmate/data"),
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "data"),
    os.path.expanduser("~"),
]


def find_yaml(name):
    for base in SEARCH_PATHS:
        path = os.path.join(base, name)
        if os.path.isfile(path):
            return path
    return None


def import_reboot_plan(conn, doc):
    c = conn.cursor()
    meta = {}
    for key, value in doc.items():
        if key != "active_actions" and isinstance(value, (str, int, float)):
            meta[key] = str(value)
    for key, value in meta.items():
        c.execute("INSERT OR REPLACE INTO plan_meta (key, value) VALUES (?, ?)", (key, value))

    actions = doc.get("active_actions") or []
    if actions:
        c.execute("DELETE FROM active_actions")
    for a in actions:
        c.execute("""
        INSERT INTO active_actions (task, action, time, status)
        VALUES (?, ?, ?, 'pending')
        """, (a.get("task"), a.get("action"), a.get("time")))
    return len(actions), len(meta)


def export_tasks_json(path=None):
    """Write tasks.json for the shutdown routine from active_actions (sorted by time)."""
    import json
    path = path or os.environ.get("TASKS_JSON_PATH") or os.path.expanduser("~/tasks.json")
    conn = get_connection()
    c = conn.cursor()
    rows = [dict(r) for r in c.execute("SELECT task, action, time FROM active_actions ORDER BY time")]
    conn.close()
    out = [{"task": r["task"], "action": r["action"], "time": r["time"]} for r in rows]
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2, ensure_ascii=False)
    # Also write to ~/firstmate/data/tasks.json if directory exists
    fm_path = os.path.expanduser("~/firstmate/data/tasks.json")
    if os.path.exists(os.path.dirname(fm_path)) and fm_path != path:
        try:
            with open(fm_path, "w", encoding="utf-8") as f:
                json.dump(out, f, indent=2, ensure_ascii=False)
        except Exception:
            pass
    return path, len(out)


def main():
    strict = "--strict" in sys.argv
    init_db()
    conn = get_connection()
    path = find_yaml("REBOOT_PLAN.yaml")
    if not path:
        msg = f"REBOOT_PLAN.yaml not found in {SEARCH_PATHS}"
        if strict:
            sys.exit(msg)
        print(f"skip: {msg}")
    else:
        with open(path) as f:
            doc = yaml.safe_load(f) or {}
        imported_actions, imported_meta = import_reboot_plan(conn, doc)
        print(f"imported {imported_actions} active_actions + {imported_meta} meta keys from {path}")
    conn.commit()
    conn.close()
    p, n = export_tasks_json()
    print(f"exported {n} tasks -> {p}")


if __name__ == "__main__":
    main()
