#!/usr/bin/env python3
"""free_tier.py — is the free tier alive, and is the free mint really free?

    python3 scripts/free_tier.py --wallet 0xWALLET [--qty 1] 0xADDR [0xADDR2 ...]

Reads the state views, then SIMULATES mint(qty) with value 0 from your wallet
(eth_estimateGas). Simulation is the verdict; the views are context.

Exit code 0 = at least one address is mintable for free, 1 = none.
"""
from __future__ import annotations

import argparse
import sys

from lib import (AGENT_ID_REGISTRY, DEFAULT_RPC, as_addr, as_int, call,
                 decode_revert_selector, enc_addr, enc_uint, name_revert, rpc)


def read_view(addr: str, selector: str, args: str = "", rpc_url: str = DEFAULT_RPC):
    return as_int(call(addr, selector, args, rpc_url=rpc_url))


def simulate(addr: str, wallet: str, selector: str, qty: int, value: int, rpc_url: str):
    data = "0x" + selector + enc_uint(qty)
    res = rpc("eth_estimateGas", [{"from": wallet, "to": addr, "value": hex(value), "data": data}, "latest"],
              rpc_url=rpc_url)
    if isinstance(res, str) and res.startswith("0x"):
        return {"ok": True, "gas": int(res, 16), "selector": selector}
    sel = decode_revert_selector(res)
    return {"ok": False, "selector": selector, "revert": sel, "reason": name_revert(sel) if sel else str(res)[:160]}


def report(addr: str, wallet: str, qty: int, rpc_url: str) -> int:
    print(f"== {addr}")
    free_cap = read_view(addr, "9858cf19", rpc_url=rpc_url)
    max_supply = read_view(addr, "32cb6b0c", rpc_url=rpc_url)
    max_wallet = read_view(addr, "0f2cdd6c", rpc_url=rpc_url)
    total_minted = read_view(addr, "a2309ff8", rpc_url=rpc_url)
    price = read_view(addr, "8d859f3e", rpc_url=rpc_url)
    cur = read_view(addr, "9d1b464a", rpc_url=rpc_url)
    mine = read_view(addr, "3cef28d2", enc_addr(wallet), rpc_url=rpc_url)
    cost_qty = read_view(addr, "b31dfc8f", enc_uint(qty), rpc_url=rpc_url)
    reg = as_addr(call(addr, "8854a0ff", rpc_url=rpc_url))

    def fmt(v, unit=""):
        return "n/a" if v is None else f"{v}{unit}"

    print(f"   FREE_SUPPLY     {fmt(free_cap)}")
    print(f"   MAX_SUPPLY      {fmt(max_supply)}")
    print(f"   MAX_PER_WALLET  {fmt(max_wallet)}")
    print(f"   totalMinted     {fmt(total_minted)}")
    print(f"   PRICE           {fmt(price, ' wei')}   currentPrice {fmt(cur, ' wei')}")
    print(f"   mintedBy(you)   {fmt(mine)}")
    print(f"   costFor({qty})    {fmt(cost_qty, ' wei')}")
    print(f"   gate            {reg or 'no agentIdRegistry() view (maybe voucher-gated)'}"
          f"{' ✅ official' if reg and reg.lower() == AGENT_ID_REGISTRY.lower() else ''}")

    free_left = None
    if free_cap:
        used = total_minted if total_minted is not None else 0
        free_left = max(free_cap - used, 0)
        print(f"   free left       {free_left} of {free_cap} (uses totalMinted as the counter)")
    if max_wallet is not None and mine is not None:
        print(f"   wallet quota    {mine}/{max_wallet} used -> {max(max_wallet - mine, 0)} left")

    sim = simulate(addr, wallet, "a0712d68", qty, 0, rpc_url)
    if sim["ok"]:
        print(f"   SIMULATE        ✅ mint({qty}) value 0 passes — gas ≈ {sim['gas']} (that gas is your budget)")
        verdict = "FREE — mint now"
    else:
        print(f"   SIMULATE        ❌ mint({qty}) value 0 reverts -> {sim.get('reason')} (sel {sim.get('revert')})")
        if sim.get("revert"):
            print(f"   decode          https://www.4byte.directory/api/v1/signatures/?hex_signature=0x{sim['revert']}")
        verdict = "not free via mint(uint256)"

    if not sim["ok"]:
        sim2 = simulate(addr, wallet, "7c928fe9", qty, 0, rpc_url)
        if sim2["ok"]:
            print(f"   SIMULATE alt    ✅ freeMint({qty}) passes — gas ≈ {sim2['gas']} (use selector 0x7c928fe9)")
            verdict = "FREE via freeMint(uint256)"

    if cost_qty and cost_qty > 0:
        print(f"   note            costFor says this quantity costs {cost_qty} wei — free tier may be per-wallet only")

    print(f"   VERDICT         {verdict}")
    return 0 if verdict.startswith("FREE") else 1


def main() -> int:
    p = argparse.ArgumentParser(description="Free-tier reader + value-0 simulation")
    p.add_argument("addresses", nargs="+")
    p.add_argument("--wallet", required=True, help="wallet to simulate from (must hold a .ai Agent ID)")
    p.add_argument("--qty", type=int, default=1)
    p.add_argument("--rpc", default=DEFAULT_RPC)
    a = p.parse_args()
    rc = 1
    for addr in a.addresses:
        rc = min(rc, report(addr, a.wallet, a.qty, a.rpc))
        print()
    return 0 if rc == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
