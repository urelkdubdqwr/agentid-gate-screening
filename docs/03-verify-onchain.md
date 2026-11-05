# 03 — On-chain verification: from address to verdict

This is the core of screening. Five steps, each one cheap, each one falsifiable.
Run them in order; stop as soon as a step gives you a "no".

---

## Step 1 — Is it even a contract, and is it a proxy?

```bash
python3 scripts/recon.py 0xContract
```

By hand:

```bash
curl -s $RPC_URL -H 'content-type: application/json' \
  -d '{"jsonrpc":"2.0","id":1,"method":"eth_getCode","params":["0xContract","latest"]}' \
  | jq -r '.result | length/2 - 1'      # byte size of runtime code
```

* **big code (5k–30k bytes)** → normal contract, continue.
* **~200–300 bytes + `name()`/`totalSupply()` reverting with `0x`** → a thin proxy/diamond. Resolve it before judging:
  * EIP-1967 implementation slot: `0x360894a13ba1a3210667c828492db98dca3e2076cc3735a920a3ca505d382bbc`
  * diamonds: `facets()` `0x52ef6b2c` / `facetAddresses()` `0x52a9679b`
  * ABI per address: `https://sourcify.dev/server/v2/contract/<chainId>/<addr>?fields=metadata`
* **no code (`0x`)** → it is not deployed on this chain. Wrong chain, or a site lying about its own address.

---

## Step 2 — Recover the real function list from the bytecode

Unverified ≠ unknown. The dispatcher keeps every selector in the clear:

```
63 <selector> 14 61 <dest> 57      ; if (msg.sig == 0x<selector>) goto dest
```

```bash
python3 scripts/recon.py 0xContract        # prints selectors + resolved names
```

Name them without an API key:

```bash
curl -s "https://api.openchain.xyz/signature-database/v1/lookup?function=0xa0712d68,0x9858cf19&filter=true" | jq .
```

Selectors you will meet constantly in this genre:

| Selector | Signature | Use |
| --- | --- | --- |
| `0xa0712d68` | `mint(uint256)` | the main mint (payable in most contracts) |
| `0x7c928fe9` | `freeMint(uint256)` | explicit free path |
| `0x1249c58b` | `mint()` | no-arg, usually 1 free per wallet |
| `0x4e71d92d` | `claim()` | claim-style free drop |
| `0xf366afc9` | `claimFree()` | claim-style, no args |
| `0x3cef28d2` | `mintedBy(address)` | per-wallet counter |
| `0x9858cf19` | `FREE_SUPPLY()` | global free cap |
| `0x32cb6b0c` | `MAX_SUPPLY()` | collection cap |
| `0x0f2cdd6c` | `MAX_PER_WALLET()` | per-wallet cap |
| `0x8d859f3e` | `PRICE()` | flat price (wei) |
| `0x9d1b464a` | `currentPrice()` | live price (0 = free right now) |
| `0xb31dfc8f` | `costFor(uint256)` | **cost of minting N right now** |
| `0x8f79306e` | `quote(address,uint256)` | per-wallet quote (ladder-aware) |
| `0xa2309ff8` | `totalMinted()` | total supply minted |
| `0x8854a0ff` | `agentIdRegistry()` | the gate itself |

---

## Step 3 — Read the free-tier state (never the landing page)

```bash
python3 scripts/free_tier.py --wallet 0xYourWallet --qty 1 0xContract
```

What it actually reads and how to read it yourself:

| Call | Meaning of the answer |
| --- | --- |
| `FREE_SUPPLY()` | total free units; **if `totalMinted() >= FREE_SUPPLY()` the free tier is gone** |
| `costFor(qty)` | `0` → this mint is free *right now* for anyone |
| `mintedBy(wallet)` | how many this wallet already took (compare with `MAX_PER_WALLET()`) |
| `agentIdRegistry()` | must equal `0x60B9262456dE011F7d15a54CdD8c48bAaa8B022F` |
| `currentPrice()` / `PRICE()` | `0` = free window, anything else = paid ladder is live |

Three traps that produce wrong verdicts:

1. **`free_minted` is not `totalMinted`.** Many contracts have a separate `free_minted` counter; when the API only
   exposes `totalMinted`, treat `min(totalMinted, free_cap)` as the free count, otherwise you will believe a dead
   tier is alive.
2. **`quote()`/`priceOfNth()` may return `0` for every index** and still be a paid mint — only `costFor`/`mintedBy`
   plus the simulation settle it.
3. **A sold-out free tier can still *look* free** because the price view reads the ladder's first step. Simulate.

---

## Step 4 — Simulate the exact transaction (the deciding step)

`eth_estimateGas` with `value = 0` is a full dry run of the mint from your wallet, without spending anything:

```bash
curl -s $RPC_URL -H 'content-type: application/json' -d '{
  "jsonrpc":"2.0","id":1,"method":"eth_estimateGas","params":[{
    "from":"0xYourWallet",
    "to":"0xContract",
    "value":"0x0",
    "data":"0xa0712d680000000000000000000000000000000000000000000000000000000000000001"
  },"latest"]}'
```

* **returns a gas number** → the call succeeds with zero ETH: you can mint, free. The returned gas is also your
  `gasLimit` (add ~20 % headroom).
* **reverts** → decode the reason. Grab the 4-byte selector out of the error `data` and look it up:

```bash
curl -s "https://www.4byte.directory/api/v1/signatures/?hex_signature=0x<selector>" | jq .
```

| Decoded revert | Real meaning | Action |
| --- | --- | --- |
| `EnforcedPause()` | the *contract* is paused, the drop is alive | retry on a short loop, do not re-recon |
| `NoAgentId()` / `NotAgent()` | gate rejects your wallet | check `gate_check.py`; do not burn gas |
| `SoldOut()` / `ExceedsFree()` | free tier drained | stop, do not pay |
| `MaxWalletExceeded()` | you already minted your quota | move on |
| `WrongValue()` | mint wants an exact `msg.value` (often a refundable deposit) | read the spec, then simulate with the right value |
| selector not found anywhere | gate on time / allowlist / wrong args | compare against the contract's own docs, do not brute-force |

> Rule: **one** decoded revert that is not `Paused` is a verdict. Do not retry-loop a gate that said
> `NoAgentId` — that is how wallets get flagged and how hours get burned.

---

## Step 5 — Verify after minting (the only proof that counts)

```bash
# receipt status 0x1 == success; status 0x0 == reverted on-chain
curl -s $RPC_URL -H 'content-type: application/json' \
  -d '{"jsonrpc":"2.0","id":1,"method":"eth_getTransactionReceipt","params":["0xTX"]}'

# then read the ERC-721 balance the mint was supposed to give you
# balanceOf(address) = 0x70a08231 + padded address
curl -s $RPC_URL -H 'content-type: application/json' \
  -d '{"jsonrpc":"2.0","id":1,"method":"eth_call","params":[{"to":"0xNFT",
       "data":"0x70a08231000000000000000000000000<wallet>"},"latest"]}'
```

`BROADCASTED`, a toast in a web UI, and the project's own dashboard are **not** results.
Receipt `status 1` **plus** a balance delta is.

---

## Full verdict table

| Simulation result | Free-tier reads | Verdict |
| --- | --- | --- |
| passes at `value = 0` | `mintedBy < MAX_PER_WALLET` | **mint now** |
| passes at `value = 0` | `mintedBy == MAX_PER_WALLET` | nothing left for this wallet |
| passes at `value = X > 0` | spec has `refund()`/`claimRefund()` | effectively free deposit — read the refund rule, then decide |
| passes at `value = X > 0` | no refund path | paid ladder — screen it, do not auto-buy |
| reverts `SoldOut`/`ExceedsFree` | `totalMinted >= FREE_SUPPLY` | dead, walk away |
| reverts `NoAgentId` | — | wallet does not qualify; fix the wallet, not the contract |
| no such selector | — | wrong function / time gate — read the project's own ABI first |
