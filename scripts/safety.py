#!/usr/bin/env python3
"""safety.py — mechanical half of the pre-mint checklist.

    python3 scripts/safety.py 0xADDR [--chain 56] [--rpc URL]

Reports: source verification, proxy/upgradeability, owner powers present in the ABI,
paused state, payee, and any external-call plumbing visible in the dispatcher
(approve / transferFrom / setApprovalForAll reachable from the mint path is the
biggest drainer signal in this genre).

This is a heuristic, not an audit. "Unverified bytecode" means YOU read the bytecode.
"""
from __future__ import annotations

import argparse
import re
import sys

from lib import (DEFAULT_RPC, as_addr, as_int, call, code_size, eip1967_implementation,
                 find_selectors, name_selectors, rpc, sourcify)

DANGER = {
    "a22cb465": "setApprovalForAll(address,bool)",
    "095ea7b3": "approve(address,uint256)",
    "23b872dd": "transferFrom(address,address,uint256)",
    "42842e0e": "safeTransferFrom(address,address,uint256)",
}


def audit(addr: str, chain: int, rpc_url: str) -> int:
    size = code_size(addr, rpc_url)
    print(f"== {addr}")
    if size == 0:
        print("   ❌ no code on this chain")
        return 1
    verified = sourcify(chain, addr)
    print(f"   source      {'✅ verified (sourcify)' if verified else '⚠️ unverified — the bytecode IS the spec, read it'}")

    impl = eip1967_implementation(addr, rpc_url)
    print(f"   upgradeable {'⚠️ YES, EIP-1967 impl ' + impl if impl else 'no (no EIP-1967 slot)'}")

    code = rpc("eth_getCode", [addr, "latest"], rpc_url=rpc_url) or "0x"
    sels = find_selectors(code)
    names = name_selectors(sels)
    named = sorted(set(names.values()))

    powers = []
    for sel, label in (("5c975abb", "paused()"), ("3ccfd60b", "withdraw()"), ("8da5cb5b", "owner()"),
                       ("8456cb59", "pause()"), ("02329a29", "unpause()"), ("f2fde38b", "transferOwnership()"),
                       ("715018a6", "renounceOwnership()")):
        if any(n.startswith(label.split("(")[0] + "(") for n in named):
            powers.append(label)
    print(f"   admin       {', '.join(powers) if powers else 'none obvious in the dispatcher'}")

    owner = as_addr(call(addr, "8da5cb5b", rpc_url=rpc_url))
    payee = as_addr(call(addr, "ae90b213", rpc_url=rpc_url))
    paused = as_int(call(addr, "5c975abb", rpc_url=rpc_url))
    if owner:
        print(f"   owner       {owner}{'  (renounced)' if int(owner, 16) == 0 else ''}")
    if payee:
        print(f"   payee       {payee}")
    if paused is not None:
        print(f"   paused      {'YES' if paused else 'no'}")

    risky = [f"{sel} {DANGER[sel]}" for sel in sels if sel in DANGER]
    if risky:
        print("   token plumbing present (normal for an NFT, but check the mint path does not touch YOUR assets):")
        for r in risky:
            print(f"     - {r}")
    else:
        print("   token plumbing  none found in the dispatcher")

    # crude external-call sniff: CALL/DELEGATECALL/STATICCALL opcodes near the surface
    ext = len(re.findall(r"(?:f1|f2|fa|f4)", code[2:], re.I))
    print(f"   external calls  {ext} opcode sites in runtime code (informational)")

    print("   checklist       " + ("see docs/04-risk-checklist.md — answer every box before signing"))
    return 0


def main() -> int:
    p = argparse.ArgumentParser(description="Mechanical pre-mint safety screen")
    p.add_argument("addresses", nargs="+")
    p.add_argument("--chain", type=int, default=56, help="chain id for sourcify (56 = BSC)")
    p.add_argument("--rpc", default=DEFAULT_RPC)
    a = p.parse_args()
    rc = 0
    for addr in a.addresses:
        rc |= audit(addr, a.chain, a.rpc)
        print()
    return rc


if __name__ == "__main__":
    sys.exit(main())
