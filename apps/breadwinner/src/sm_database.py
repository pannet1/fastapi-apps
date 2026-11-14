import sqlite3
import os
from typing import List, Dict, Any, Optional

DB_PATH = os.environ.get("SALES_DB_PATH")
if not DB_PATH:
    parent_data = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "sales.db")
    local_data = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "sales.db")
    DB_PATH = parent_data if os.path.exists(os.path.dirname(parent_data)) else local_data

def get_connection():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_connection()
    cursor = conn.cursor()
    
    # 1. Personas (Mapping to REBOOT_PLAN.yaml personas)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS personas (
        slug TEXT PRIMARY KEY,
        title TEXT NOT NULL,
        what_you_do TEXT NOT NULL,
        speed_to_cash TEXT NOT NULL,
        revenue_model TEXT NOT NULL,
        bottleneck TEXT,
        active_lead_summary TEXT,
        value INTEGER NOT NULL DEFAULT 0
    )
    """)

    # 2. Campaigns (AI proposals & active commercial drives)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS campaigns (
        slug TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        start_date TEXT NOT NULL,
        end_date TEXT NOT NULL,
        target_revenue INTEGER NOT NULL,
        status TEXT NOT NULL DEFAULT 'proposed',
        repo TEXT,
        module TEXT,
        persona_slug TEXT,
        rationale TEXT
    )
    """)

    # 3. Persona Repo Actions & Objectives
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS persona_repo_actions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        persona_slug TEXT NOT NULL,
        repo TEXT NOT NULL,
        action TEXT NOT NULL,
        objective TEXT NOT NULL,
        UNIQUE(persona_slug, repo, action)
    )
    """)

    # 4. Active Actions (the human's daily field task list; replaces data/REBOOT_PLAN.yaml active_actions)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS active_actions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        task TEXT NOT NULL,
        action TEXT NOT NULL,
        time TEXT,
        status TEXT NOT NULL DEFAULT 'pending',
        campaign_slug TEXT REFERENCES campaigns(slug),
        repo TEXT,
        persona_slug TEXT
    )
    """)

    # 5. Plan metadata (mission / updated; replaces the REBOOT_PLAN.yaml header)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS plan_meta (
        key TEXT PRIMARY KEY,
        value TEXT
    )
    """)

    conn.commit()
    conn.close()
