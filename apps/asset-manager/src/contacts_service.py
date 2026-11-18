import glob
import os
import sqlite3
from typing import Any, Dict, List, Optional


def find_thunderbird_abook() -> Optional[str]:
    """Locates the primary populated Thunderbird address book sqlite file."""
    tb_base = os.path.expanduser("~/.thunderbird")
    if not os.path.isdir(tb_base):
        return None
    candidates = glob.glob(f"{tb_base}/*/abook-1.sqlite") + glob.glob(f"{tb_base}/*/abook.sqlite")
    candidates = [c for c in candidates if os.path.isfile(c)]
    if not candidates:
        return None
    candidates.sort(key=lambda p: os.path.getsize(p), reverse=True)
    return candidates[0]


def build_vcard(name: str, phone: Optional[str] = None, email: Optional[str] = None) -> str:
    """Builds a standard RFC 6350 vCard (v3.0) from name and optional contact info."""
    clean_name = (name or "Unknown").strip()
    lines = [
        "BEGIN:VCARD",
        "VERSION:3.0",
        f"FN:{clean_name}",
    ]
    if phone and str(phone).strip():
        lines.append(f"TEL;TYPE=CELL,PREF:{str(phone).strip()}")
    if email and str(email).strip():
        lines.append(f"EMAIL:{str(email).strip()}")
    lines.append("END:VCARD")
    return "\r\n".join(lines)


def search_thunderbird_contacts(query: str, limit: int = 8) -> List[Dict[str, Any]]:
    """
    Fast, read-only search across Thunderbird address book vCards.
    Returns matched names, phone numbers, and full vCard payloads.
    """
    q = (query or "").strip().lower()
    if not q:
        return []

    abook_path = find_thunderbird_abook()
    if not abook_path:
        return []

    try:
        conn = sqlite3.connect(f"file:{abook_path}?mode=ro", uri=True, timeout=2.0)
        c = conn.cursor()
        query_pattern = f"%{q}%"
        c.execute(
            """
            SELECT value FROM properties 
            WHERE name = '_vCard' AND lower(value) LIKE ?
            LIMIT ?
            """,
            (query_pattern, limit * 3),
        )

        results = []
        seen = set()
        for (vcard,) in c.fetchall():
            name = ""
            phones = []
            for line in vcard.splitlines():
                if line.startswith("FN:"):
                    name = line[3:].strip()
                elif line.startswith("TEL"):
                    parts = line.split(":", 1)
                    if len(parts) == 2:
                        p = parts[1].strip()
                        if p and p not in phones:
                            phones.append(p)

            if name and name.lower() not in seen:
                seen.add(name.lower())
                results.append({
                    "name": name,
                    "phone": phones[0] if phones else "",
                    "phones": phones,
                    "vcard": vcard,
                })
                if len(results) >= limit:
                    break

        conn.close()
        return results
    except Exception:
        return []
