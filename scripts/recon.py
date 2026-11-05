#!/usr/bin/env python3
"""recon.py — what is this contract? (size, proxy, selectors, gate)

    python3 scripts/recon.py 0xADDR [0xADDR2 ...] [--rpc URL]

Answers, in order:
  1. is there code?  how big?
  2. is it a thin proxy? (EIP-1967 impl, diamond facets)
  3. every function selector in the dispatcher, resolved to a signature
  4. whether the contract gates on the real Binance Agent ID registry
  5. basic identity: name / symbol / owner / pause flag

Read-only. No signing.
"""
from __future__ import annotations

import argparse
import sys

from lib import (AGENT_ID_REGISTRY, DEFAULT_RPC, as_addr, as_int, call, code_size,
                 eip1967_implementation, find_selectors, name_selectors, rpc)


def show(addr: str, rpc_url: str) -> int:
    size = code_size(addr, rpc_url)
    print(f"== {addr}")
    print(f"   code size   {size} bytes")
    if size == 0:
        print("   verdict     NO CODE on this chain — wrong address or wrong chain")
        return 1

    impl = eip1967_implementation(addr, rpc_url)
    if impl:
        print(f"   proxy       EIP-1967 implementation -> {impl} (read the impl, not the proxy)")
    elif size < 600:
        print("   proxy?      small runtime — likely proxy/facet host; try facets() 0x52ef6b2c")

    code = rpc("eth_getCode", [addr, "latest"], rpc_url=rpc_url) or "0x"
    sels = find_selectors(code)
    names = name_selectors(sels)
    named = sorted({names[s] for s in sels})
    print(f"   selectors   {len(sels)}")
    for s in sorted(names):
        print(f"     {s}  {names[s]}")

    # gate
    reg = as_addr(call(addr, "8854a0ff", rpc_url=rpc_url))
    if reg:
        real = reg.lower() == AGENT_ID_REGISTRY.lower()
        print(f"   gate        agentIdRegistry() = {reg} {'✅ official Binance registry' if real else '⚠️ NOT the official registry'}")
    elif any(n in named for n in ("hasAgentId(address)", "mintableBy(address)")):
        print("   gate        helper-style (hasAgentId/mintableBy) — resolve the registry it reads before trusting it")
    else:
        print("   gate        no on-chain registry view — check for a backend-signed voucher (see docs/01)")

    for sig, label in (("mint(uint256)", "mint"), ("freeMint(uint256)", "freeMint"), ("claim()", "claim")):
        if any(n.startswith(sig.split("(")[0] + "(") for n in named):
            print(f"   entry       {label} ✔")

    ident = []
    for sel, label in (("06fdde03", "name"), ("95d89b41", "symbol")):
        raw = call(addr, sel, rpc_url=rpc_url)
        if isinstance(raw, str) and len(raw) > 130:
            try:
                ln = int(raw[66:130], 16)
                txt = bytes.fromhex(raw[130:130 + ln * 2]).decode("utf-8", "replace")
                ident.append(f"{label}={txt}")
            except Exception:  # noqa: BLE001
                pass
    owner = as_addr(call(addr, "8da5cb5b", rpc_url=rpc_url))
    paused = as_int(call(addr, "5c975abb", rpc_url=rpc_url))
    if ident:
        print("   identity    " + " ".join(ident))
    if owner:
        print(f"   owner       {owner}{' (renounced)' if int(owner, 16) == 0 else ''}")
    if paused is not None:
        print(f"   paused      {'YES — retry, do not re-recon' if paused else 'no'}")
    return 0


def main() -> int:
    p = argparse.ArgumentParser(description="Bytecode recon for agent-gated contracts")
    p.add_argument("addresses", nargs="+")
    p.add_argument("--rpc", default=DEFAULT_RPC)
    a = p.parse_args()
    rc = 0
    for addr in a.addresses:
        rc |= show(addr, a.rpc)
        print()
    return rc


if __name__ == "__main__":
    sys.exit(main())
