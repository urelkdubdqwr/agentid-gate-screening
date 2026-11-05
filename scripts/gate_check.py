#!/usr/bin/env python3
"""gate_check.py — does this wallet hold a .ai Agent ID?

    python3 scripts/gate_check.py --wallet 0xWALLET [--rpc URL]

Read-only: one eth_call to the Binance Agent ID registry on BNB Chain.
Exit code 0 = wallet is a registered agent, 1 = it is not.
"""
from __future__ import annotations

import argparse
import sys

from lib import AGENT_ID_REGISTRY, DEFAULT_RPC, as_int, call, enc_addr


def check(wallet: str, rpc_url: str = DEFAULT_RPC) -> int | None:
    res = call(AGENT_ID_REGISTRY, "70a08231", enc_addr(wallet), rpc_url=rpc_url)
    return as_int(res)


def main() -> int:
    p = argparse.ArgumentParser(description="Check a wallet's .ai Agent ID (BNB Chain registry)")
    p.add_argument("--wallet", required=True, help="wallet address to check")
    p.add_argument("--rpc", default=DEFAULT_RPC)
    p.add_argument("--json", action="store_true")
    a = p.parse_args()

    bal = check(a.wallet, a.rpc)
    if bal is None:
        print(f"RPC error while reading registry {AGENT_ID_REGISTRY} (rpc={a.rpc})")
        return 2
    ok = bal >= 1
    if a.json:
        print(f'{{"wallet":"{a.wallet}","registry":"{AGENT_ID_REGISTRY}","balance":{bal},"agent":{str(ok).lower()}}}')
    else:
        print(f"wallet   {a.wallet}")
        print(f"registry {AGENT_ID_REGISTRY} (BNB Chain)")
        print(f"balance  {bal}")
        print(f"verdict  {'AGENT ✅ — gate will accept this wallet' if ok else 'NOT AN AGENT ❌ — gated mints will revert'}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
