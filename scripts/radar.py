#!/usr/bin/env python3
"""radar.py — live discovery of Agent-ID gated launches.

    python3 scripts/radar.py [--hours 24] [--free-only] [--limit 500]
                             [--wallet 0x…] [--state PATH] [--quiet-empty] [--json]

Sources (all public, no keys):
  * unitytool.app Agent Radar  — /api/launches + /api/project/<addr>
  * t.me/s/agentidcall         — public call-channel preview (contract leads)

Filtering: gate ∈ {bytecode, behavior} AND the gate reference mentions the Agent ID registry.

Exit code 0 always (a watcher should not spam failures); use --json for machine output.
With --quiet-empty nothing is printed when there is nothing new (cron-friendly).
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time

from lib import get_json, human_age

RADAR = "https://unitytool.app/api/launches?limit={limit}"
PROJECT = "https://unitytool.app/api/project/{addr}"
TG = "https://t.me/s/agentidcall"
HEADERS = {"referer": "https://unitytool.app/", "accept": "application/json"}


def is_agent_gated(item: dict) -> bool:
    if item.get("gate") not in ("bytecode", "behavior"):
        return False
    blob = " ".join(str(item.get(k) or "").lower() for k in ("gate_ref", "description", "name"))
    return "agent id" in blob or "agent-id" in blob


def load_state(path: str) -> dict:
    try:
        with open(path) as f:
            return json.load(f)
    except Exception:  # noqa: BLE001
        return {"seen": {}, "tg": {}}


def save_state(path: str, st: dict) -> None:
    d = os.path.dirname(os.path.abspath(path))
    os.makedirs(d, exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w") as f:
        json.dump(st, f, indent=1)
    os.replace(tmp, path)


def collect(limit: int, hours: float, wallet: str | None, st: dict, quiet: bool):
    now = time.time()
    launches = get_json(RADAR.format(limit=limit), headers=HEADERS).get("items", [])
    cand = [x for x in launches if is_agent_gated(x)]
    fresh = [x for x in cand if (x.get("first_seen") or 0) > now - hours * 3600]

    rows = []
    seen = st.setdefault("seen", {})
    budget = 12
    for x in sorted(fresh, key=lambda i: -(i.get("first_seen") or 0)):
        addr = x["addr"].lower()
        prev = seen.get(addr)
        if prev and now - prev.get("reported_at", 0) < 6 * 3600:
            continue
        if budget <= 0:
            continue
        budget -= 1
        try:
            det = get_json(PROJECT.format(addr=addr), headers=HEADERS)
        except Exception:  # noqa: BLE001
            det = {}
        lau = det.get("launch") or {}
        fcap, fmint = lau.get("free_cap"), lau.get("free_minted")
        minted = lau.get("minted") or 0
        if fmint is None and fcap:
            fmint = min(minted, fcap)
        free_open = bool(fcap) and (fmint or 0) < fcap
        rows.append({
            "addr": addr, "name": x.get("name"), "kind": x.get("kind"),
            "desc": (det.get("description") or x.get("description") or "").strip(),
            "free_cap": fcap, "free_minted": fmint, "free_open": free_open,
            "price_bnb": lau.get("price"), "price_usd": lau.get("price_usd"),
            "minted": minted, "agents": x.get("agents") or det.get("agents"),
            "first_seen": x.get("first_seen"), "website": det.get("website"), "x": det.get("x"),
            "sim": None,
        })
        seen[addr] = {"reported_at": now, "free_open": free_open, "free_minted": fmint}

    tg_rows = []
    html = ""
    try:
        import urllib.request
        req = urllib.request.Request(TG, headers={"user-agent": "agentid-gate-screening/1.0"})
        with urllib.request.urlopen(req, timeout=25) as r:
            html = r.read().decode("utf-8", "replace")
    except Exception:  # noqa: BLE001
        html = ""
    tg = st.setdefault("tg", {})
    for b in re.findall(r"js-message_text[^>]*>(.*?)</div>", html or "", re.S)[-8:]:
        txt = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", b)).strip()
        for c in set(re.findall(r"0x[0-9a-fA-F]{40}", txt)):
            cl = c.lower()
            if cl in tg:
                continue
            tg[cl] = now
            tg_rows.append({"addr": cl, "note": txt[:200]})

    st["tg"] = {k: v for k, v in tg.items() if now - v < 30 * 86400}
    st["seen"] = {k: v for k, v in seen.items() if now - v.get("reported_at", 0) < 30 * 86400}
    return cand, rows, tg_rows


def main() -> int:
    p = argparse.ArgumentParser(description="Agent-ID gate radar")
    p.add_argument("--hours", type=float, default=24)
    p.add_argument("--limit", type=int, default=500)
    p.add_argument("--free-only", action="store_true", help="only show items whose free tier is still open")
    p.add_argument("--wallet", help="simulate from this wallet (needs a .ai Agent ID) and print a verdict")
    p.add_argument("--state", default=os.path.expanduser("~/.agentid-gate-screen/state.json"))
    p.add_argument("--quiet-empty", action="store_true")
    p.add_argument("--json", action="store_true")
    p.add_argument("--no-state", action="store_true", help="ignore/don't write the state file")
    a = p.parse_args()

    st = {"seen": {}, "tg": {}} if a.no_state else load_state(a.state)
    try:
        cand, rows, tg_rows = collect(a.limit, a.hours, a.wallet, st, a.quiet_empty)
    except Exception as e:  # noqa: BLE001
        print(f"RADAR-FAIL {e}")
        return 0
    if not a.no_state:
        save_state(a.state, st)

    if a.free_only:
        rows = [r for r in rows if r["free_open"]]

    if a.json:
        print(json.dumps({"gated": len(cand), "rows": rows, "channel": tg_rows}, indent=1))
        return 0

    if not rows and not tg_rows:
        if not a.quiet_empty:
            print(f"no new agent-gated launches in the last {a.hours:g}h ({len(cand)} gated projects in feed)")
        return 0

    now = time.time()
    print(f"agent-gated projects in feed: {len(cand)} · new in window: {len(rows)}")
    for r in sorted(rows, key=lambda x: (not x["free_open"], x["first_seen"] or 0), reverse=False)[:12]:
        free = ("free %s/%s" % (r["free_minted"] or 0, r["free_cap"])) if r["free_cap"] else "no free tier"
        if r["free_cap"] and not r["free_open"]:
            free = "free tier GONE"
        price = f" · paid {r['price_bnb']:.6f} BNB" if r["price_bnb"] else ""
        print(f"\n{r['name']} ({r['kind']}) — {free}{price}")
        if r["desc"]:
            print(f"   {r['desc'][:150]}")
        print(f"   minted {r['minted']} · agents {r['agents']} · {human_age(r['first_seen'] or now)} old")
        print(f"   https://bscscan.com/address/{r['addr']}")
    if tg_rows:
        print("\nchannel leads:")
        for r in tg_rows[:5]:
            print(f"   {r['addr']}\n     {r['note'][:120]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
