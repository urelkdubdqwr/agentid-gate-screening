#!/usr/bin/env python3
"""Batch gate sweep — screen every freshly launched Agent-ID-gated contract at once.

Reads the public launch radar, keeps the entries whose gate reference mentions the Agent ID, then for each
contract asks the chain three questions with one `eth_estimateGas` per candidate selector and `value = 0`:

    does this wallet pass the mint right now, for free?

Verdicts per contract:
    FREE   estimateGas passed with value 0 -> free for this wallet, today
    PAID   the call reverts with a body -> not free through the probed selector
    CLOSED no candidate selector exists in the dispatcher / no code at the address

Read-only: `eth_call`, `eth_estimateGas`, `eth_getCode` and the radar feed. It never signs and never sends.

Usage:
    python3 sweep.py --wallet 0xYourWallet [--limit 500] [--rpc URL] [--json-out rows.json] [--free-only]
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from concurrent.futures import ThreadPoolExecutor

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lib import DEFAULT_RPC, call, enc_addr, enc_uint, find_selectors, get_code, get_json, rpc  # noqa: E402

RADAR = "https://unitytool.app/api/launches"
RADAR_HEADERS = {"referer": "https://unitytool.app/", "accept": "application/json"}

REGISTRY = "0x60b9262456de011f7d15a54cdd8c48baaa8b022f"

# (label, selector, argument) — argument None = arrays/odd shapes, simulated bare as a last resort
CANDIDATES = [
    ("mint(uint256)", "a0712d68", 1),
    ("mint()", "1249c58b", None),
    ("freeMint(uint256)", "7c928fe9", 1),
    ("freeMint()", "5b70ea9f", None),
    ("claim()", "4e71d92d", None),
    ("claimFree()", "f366afc9", None),
    ("openFree()", "1644fa8e", None),
]

GATE_GETTERS = [("agentIdRegistry()", "8854a0ff"), ("agentRegistry()", "0d1cfcae")]


def fetch_gated(limit: int) -> list[dict]:
    items = get_json(f"{RADAR}?limit={limit}", headers=RADAR_HEADERS).get("items", [])
    out = []
    for it in items:
        if it.get("gate") not in ("bytecode", "behavior"):
            continue
        blob = " ".join(str(it.get(k) or "").lower() for k in ("gate_ref", "description", "name"))
        if "agent id" in blob or "agent-id" in blob:
            out.append(it)
    return out


def probe(item: dict, wallet: str, rpc_url: str) -> dict:
    addr = item["addr"].lower()
    row = {"addr": addr, "name": item.get("name"), "verdict": "CLOSED", "selector": None,
           "gas": None, "revert": None, "registry_official": None, "held": None, "selectors": 0}
    code = get_code(addr, rpc_url)
    if not code or code == "0x":
        row["revert"] = "no code"
        return row
    sels = set(find_selectors(code))
    row["selectors"] = len(sels)

    for name, sel, arg in CANDIDATES:
        if sel not in sels:
            continue
        data = "0x" + sel + (enc_uint(arg) if arg is not None else "")
        res = rpc("eth_estimateGas", [{"from": wallet, "to": addr, "value": "0x0", "data": data}, "latest"],
                  rpc_url=rpc_url)
        if isinstance(res, str) and res.startswith("0x"):
            row.update(verdict="FREE", selector=name, gas=int(res, 16))
            break
        if isinstance(res, dict) and "__error__" in res:
            row.update(verdict="PAID", selector=name, revert=str(res["__error__"])[-40:])
            break

    for label, sel in GATE_GETTERS:
        res = call(addr, sel, rpc_url=rpc_url)
        if isinstance(res, str) and len(res) >= 42:
            row["registry_official"] = ("0x" + res[-40:]).lower() == REGISTRY
            break

    bal = call(addr, "70a08231", enc_addr(wallet), rpc_url=rpc_url)
    if isinstance(bal, str) and len(bal) >= 66:
        row["held"] = int(bal, 16)
    return row


def main() -> int:
    ap = argparse.ArgumentParser(description="Batch-screen Agent-ID-gated contracts from the launch radar.")
    ap.add_argument("--wallet", required=True, help="wallet the simulation runs as (must hold the Agent ID to pass a gate)")
    ap.add_argument("--limit", type=int, default=500, help="how many radar entries to read (default 500)")
    ap.add_argument("--rpc", default=DEFAULT_RPC, help=f"JSON-RPC endpoint (default {DEFAULT_RPC})")
    ap.add_argument("--workers", type=int, default=12, help="parallel probes (default 12)")
    ap.add_argument("--json-out", help="also write the full row set to this file")
    ap.add_argument("--free-only", action="store_true", help="print only the FREE rows")
    args = ap.parse_args()

    if not args.wallet.startswith("0x") or len(args.wallet) != 42:
        print("--wallet must be a 0x-prefixed 20-byte address", file=sys.stderr)
        return 2

    cands = fetch_gated(args.limit)
    print(f"# gated contracts in feed: {len(cands)}")
    if not cands:
        return 0

    with ThreadPoolExecutor(args.workers) as ex:
        rows = list(ex.map(lambda it: probe(it, args.wallet, args.rpc), cands))

    by = {it["addr"].lower(): it for it in cands}
    for r in rows:
        meta = by.get(r["addr"], {})
        r["first_seen"] = meta.get("first_seen")
        r["free_cap"] = meta.get("free_cap")
        r["free_minted"] = meta.get("free_minted")

    free = [r for r in rows if r["verdict"] == "FREE"]
    paid = [r for r in rows if r["verdict"] == "PAID"]
    closed = [r for r in rows if r["verdict"] == "CLOSED"]

    show = free if args.free_only else rows
    for r in sorted(show, key=lambda x: (x["verdict"] != "FREE", x["addr"])):
        gate = {True: "official-registry", False: "other-registry", None: "no-getter"}[r["registry_official"]]
        line = f"{r['verdict']:6} {r['addr']}  {gate:17} {r['selector'] or '-':20}"
        if r["gas"]:
            line += f" gas {r['gas']:>7}"
        if r["revert"]:
            line += f" revert {r['revert']}"
        if r["held"]:
            line += f" held {r['held']}"
        print(line.rstrip())
        if r["name"]:
            print(f"       {r['name']}")

    print(f"\n# FREE {len(free)} · PAID {len(paid)} · CLOSED {len(closed)} · scanned {len(rows)}")
    if args.json_out:
        with open(args.json_out, "w") as fh:
            json.dump({"wallet": args.wallet, "rows": rows}, fh, indent=1)
        print(f"# rows -> {args.json_out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
