# 10 — Bytecode ABI recovery (unverified contracts)

Half the interesting drops are unverified, and the react-to-that mistake is guessing selectors: `mint()`,
`mint(uint256)`, `claim()` all revert with empty data and prove nothing. The dispatcher **is** the ABI. Recover it.

## 1. Pull out every selector the contract accepts

An unverified bytecode dispatcher contains the selector table as literal constants followed by a comparison and a jump:

```
63 <sel(4 bytes)> 14 61 <dest> 57        // PUSH4 sel; EQ; PUSH2 dest; JUMPI
```

```bash
# all selectors in one shot
curl -s $RPC -H 'content-type: application/json' \
  -d '{"jsonrpc":"2.0","id":1,"method":"eth_getCode","params":["0xCONTRACT","latest"]}' \
| python3 -c "
import sys, json, re
code = json.load(sys.stdin)['result'][2:]
sels = sorted(set(re.findall(r'63([0-9a-f]{8})14', code)))
print(len(sels), 'selectors'); [print(' ', s) for s in sels]"
```

## 2. Name them in one request

`openchain.xyz` accepts a comma-separated batch and needs no key; `4byte.directory` is the fallback for single lookups:

```bash
curl -s "https://api.openchain.xyz/signature-database/v1/lookup?function=0x1644fa8e,0xa0712d68&filter=true" | jq .
```

`scripts/recon.py` in this repo does both steps and prints the named table next to the gate getter.

## 3. Reconstruct the argument shape

* no args → send the bare selector;
* one `uint256` → selector + 64 hex chars;
* `(uint256, address)` → two 32-byte words, address left-padded;
* arrays → offset + length + elements. When in doubt, the project's own `agent.json` / `config.js` usually publishes a
  calldata builder (`hexQty(n)`) — read that instead of guessing.

## 4. Thin proxies and diamonds

`eth_getCode` returning ~200–300 bytes while `name()`/`totalSupply()` revert with plain `0x` is a proxy or diamond,
not an empty contract. Resolve it before declaring anything:

* EIP-1967 implementation slot `0x360894a13ba1a3210667c828492db98dca3e2076cc3735a920a3ca505d382bbc`;
* `facets()` `0x52ef6b2c` and `facetAddresses()` `0x52a9679b` for diamonds;
* fetch each facet's ABI from `https://sourcify.dev/server/v2/contract/<chainId>/<addr>?fields=metadata`.

Aggregator/router diamonds happily look like "the mint contract" and then fail with a misleading revert.

## 5. Custom errors: decode them, do not guess

A revert body of 4 bytes (`0xcd1c8867`) is a custom error. Name it by hashing candidates and comparing, or via the
signature database:

```python
from Crypto.Hash import keccak            # or use web3.py: Web3.keccak(text=...)
for name in ("FreeOver()", "SoldOut()", "NotOpen()", "BadTime()", "AlreadyClaimed()",
             "NoAgentId()", "CapReached()", "Paused()", "QuotaExceeded()", "WrongValue()"):
    print(keccak.new(digest_bits=256, data=name.encode()).hexdigest()[:8], name)
```

Reading the exit matters: `FreeOver()` = stop retrying (supply gone); `NotOpen()`/`BadTime()` = keep firing.

## 6. Two Agent-ID-specific traps

* **The Agent ID token id is `uint256(keccak256(handle))`**, not the handle string and not a sequence number.
  `mintFree(uint256 agentId)` fed `0` or a guess reverts `ERC721NonexistentToken`. Derive it from the handle and
  confirm `ownerOf(id)` is your wallet.
* **`ownerOfHandle(string)` returns the owner address, not the id.** Same family of mistake, opposite direction.

## 7. When a view reverts but a neighbour works

That is ABI drift, not ineligibility. Different builds of the same drop expose different subsets. Judge eligibility
from a **simulation of the write** (`eth_estimateGas` from your wallet), never from a view that failed to answer.
