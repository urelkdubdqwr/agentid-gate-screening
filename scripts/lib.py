#!/usr/bin/env python3
"""Shared helpers: JSON-RPC, ABI shims, selector recovery, signature lookups.

Stdlib only. Nothing here signs anything or needs a private key.
"""
from __future__ import annotations

import json
import os
import re
import time
import urllib.error
import urllib.request

DEFAULT_RPC = os.environ.get("RPC_URL", "https://bsc-dataseed.binance.org")
AGENT_ID_REGISTRY = "0x60B9262456dE011F7d15a54CdD8c48bAaa8B022F"

# --- selectors used all over the Agent-ID mint genre -------------------------
SEL = {
    "mint(uint256)": "a0712d68",
    "mint()": "1249c58b",
    "freeMint(uint256)": "7c928fe9",
    "claim()": "4e71d92d",
    "claimFree()": "f366afc9",
    "commitFreeMint()": "74d04cfc",
    "reveal(uint256)": "c2ca0ac5",
    "balanceOf(address)": "70a08231",
    "ownerOf(uint256)": "6352211e",
    "totalSupply()": "18160ddd",
    "totalMinted()": "a2309ff8",
    "FREE_SUPPLY()": "9858cf19",
    "MAX_SUPPLY()": "32cb6b0c",
    "MAX_PER_WALLET()": "0f2cdd6c",
    "PRICE()": "8d859f3e",
    "currentPrice()": "9d1b464a",
    "costFor(uint256)": "b31dfc8f",
    "quote(address,uint256)": "8f79306e",
    "mintedBy(address)": "3cef28d2",
    "hasAgentId(address)": "4eab3ef2",
    "mintableBy(address)": "1d2e6765",
    "agentIdRegistry()": "8854a0ff",
    "owner()": "8da5cb5b",
    "payee()": "ae90b213",
    "withdraw()": "3ccfd60b",
    "paused()": "5c975abb",
    "name()": "06fdde03",
    "symbol()": "95d89b41",
    "supportsInterface(bytes4)": "01ffc9a7",
    "Transfer(address,address,uint256)": "ddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef",
    "TransferSingle(address,address,address,uint256,uint256)": "c3d58168c5ae7397731d063d5bbf3d657854427343f4c083240f7aacaa2d0f62",
}
SEL_BY_HEX = {v: k for k, v in SEL.items()}

# EIP-1967 implementation slot
EIP1967_IMPL = "0x360894a13ba1a3210667c828492db98dca3e2076cc3735a920a3ca505d382bbc"


def rpc(method: str, params: list, rpc_url: str = DEFAULT_RPC, timeout: int = 25, retries: int = 3):
    body = json.dumps({"jsonrpc": "2.0", "id": 1, "method": method, "params": params}).encode()
    last = None
    for i in range(retries):
        try:
            req = urllib.request.Request(rpc_url, data=body, headers={"content-type": "application/json"})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                out = json.loads(r.read().decode())
            if "error" in out:
                return {"__error__": out["error"]}
            return out.get("result")
        except Exception as e:  # noqa: BLE001
            last = e
            time.sleep(1 + i)
    return {"__error__": f"{type(last).__name__}: {last}"}


def get_json(url: str, timeout: int = 25, retries: int = 3, headers: dict | None = None):
    last = None
    h = {"user-agent": "agentid-gate-screening/1.0"}
    h.update(headers or {})
    for i in range(retries):
        try:
            req = urllib.request.Request(url, headers=h)
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return json.loads(r.read().decode("utf-8", "replace"))
        except Exception as e:  # noqa: BLE001
            last = e
            time.sleep(1 + i)
    raise RuntimeError(f"GET failed {url}: {last}")


# --- tiny ABI shims ----------------------------------------------------------
def enc_uint(n: int) -> str:
    return f"{int(n):064x}"


def enc_addr(a: str) -> str:
    return a.lower().replace("0x", "").rjust(64, "0")


def call(to: str, selector: str, *args: str, rpc_url: str = DEFAULT_RPC):
    """eth_call a view function; returns raw hex or an {'__error__': …} dict."""
    data = "0x" + selector + "".join(args)
    return rpc("eth_call", [{"to": to, "data": data}, "latest"], rpc_url=rpc_url)


def as_int(v) -> int | None:
    if isinstance(v, str) and v.startswith("0x") and len(v) <= 66:
        try:
            return int(v, 16)
        except ValueError:
            return None
    return None


def as_addr(v) -> str | None:
    if isinstance(v, str) and v.startswith("0x") and len(v) == 66:
        a = "0x" + v[-40:]
        return a if int(a, 16) else None
    return None


# --- bytecode -----------------------------------------------------------------
def get_code(addr: str, rpc_url: str = DEFAULT_RPC) -> str:
    res = rpc("eth_getCode", [addr, "latest"], rpc_url=rpc_url)
    return res if isinstance(res, str) else "0x"


def code_size(addr: str, rpc_url: str = DEFAULT_RPC) -> int:
    return (len(get_code(addr, rpc_url)) - 2) // 2


def find_selectors(code: str) -> list[str]:
    """Dispatcher pattern `63 <sel> 14 61 <dest> 57` — every function in the clear."""
    body = code[2:] if code.startswith("0x") else code
    return sorted(set(re.findall(r"63([0-9a-f]{8})14", body)))


def storage_slot(addr: str, slot: str, rpc_url: str = DEFAULT_RPC) -> str:
    res = rpc("eth_getStorageAt", [addr, slot, "latest"], rpc_url=rpc_url)
    return res if isinstance(res, str) else "0x" + "0" * 64


def eip1967_implementation(addr: str, rpc_url: str = DEFAULT_RPC) -> str | None:
    raw = storage_slot(addr, EIP1967_IMPL, rpc_url)
    impl = as_addr(raw)
    return impl


# --- signature naming (free, no API key) --------------------------------------
def name_selectors(selectors: list[str]) -> dict[str, str]:
    """Resolve 4-byte selectors -> human signatures via openchain.xyz."""
    names = {s: SEL_BY_HEX.get(s, "?") for s in selectors}
    unknown = [s for s in selectors if names.get(s) == "?"]
    if not unknown:
        return names
    try:
        url = ("https://api.openchain.xyz/signature-database/v1/lookup?function="
               + ",".join("0x" + s for s in unknown) + "&filter=true")
        d = get_json(url, timeout=20)
        table = (d.get("result") or {}).get("function") or {}
        for s in unknown:
            hit = table.get("0x" + s)
            if hit:
                names[s] = hit[0]["name"]
    except Exception:  # noqa: BLE001
        pass
    return names


def decode_revert_selector(data) -> str | None:
    """Extract the 4-byte revert selector from an RPC error payload."""
    blob = json.dumps(data) if not isinstance(data, str) else data
    m = re.search(r"0x([0-9a-fA-F]{8})", blob)
    return m.group(1).lower() if m else None


def name_revert(selector: str) -> str:
    try:
        d = get_json(f"https://www.4byte.directory/api/v1/signatures/?hex_signature=0x{selector}",
                     timeout=15, retries=1)
        res = d.get("results") or []
        if res:
            return res[0].get("text_signature", "?")
    except Exception:  # noqa: BLE001
        pass
    return SEL_BY_HEX.get(selector, "unknown selector")


def sourcify(chain_id: int, addr: str) -> bool:
    try:
        d = get_json(f"https://sourcify.dev/server/v2/contract/{chain_id}/{addr}?fields=metadata",
                     timeout=15, retries=1)
        return bool(d.get("match") or d.get("metadata"))
    except Exception:  # noqa: BLE001
        return False


def human_age(ts: float) -> str:
    d = max(int(time.time() - ts), 1)
    if d < 3600:
        return f"{d // 60}m"
    if d < 86400:
        return f"{d // 3600}h"
    return f"{d // 86400}d"
