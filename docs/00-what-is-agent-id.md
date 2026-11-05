# 00 — What is a `.ai` Agent ID, and why do projects gate on it?

## The short version

A **Binance Agent ID** is a handle like `yourname.ai` that is minted by the **Binance Agentic Wallet (BAW)**
and recorded in an on-chain registry on **BNB Smart Chain**:

```
Agent ID registry (BSC):  0x60B9262456dE011F7d15a54CdD8c48bAaa8B022F
```

The registry is a simple identity primitive: one wallet can own a `.ai` handle. On-chain, "gated by Agent ID"
means "the mint contract calls `balanceOf(...)` / `ownerOf(...)` on that registry and refuses anything that is not
a registered agent". Off-chain (backend-gated drops) it means "the backend reads that registry and only then
signs you a voucher".

There is no protocol-level "agent" magic inside the handle. Its value to launchpads is **sybil resistance**:
minting a `.ai` handle costs real gas and a real Binance flow, so a drop gated on it gets *agents* instead of
one person with 4,000 throwaway wallets. That is why this whole genre of drops exists:

* the free slot per Agent ID is genuinely one-per-identity — worth grabbing early;
* the paid ladder is open to the same crowd — usually not worth it;
* mint volume per registered agent is a public, readable number (see `agents` counters in the radar feed).

## How to check a wallet's Agent ID

Two ways, both read-only:

```bash
python3 scripts/gate_check.py --wallet 0xYourWallet
```

or by hand:

```bash
# balanceOf(address) on the registry — >= 1 means this wallet is a registered agent
curl -s https://bsc-dataseed.binance.org -H 'content-type: application/json' \
  -d '{"jsonrpc":"2.0","id":1,"method":"eth_call","params":[
        {"to":"0x60B9262456dE011F7d15a54CdD8c48bAaa8B022F",
         "data":"0x70a08231000000000000000000000000<wallet-without-0x>"},"latest"]}'
```

If you run an agent wallet you can also ask the wallet itself:

```bash
baw wallet agent-id --json          # -> {"claimed": true, "handle": "yourname", "agentId": "yourname.ai"}
```

## The economics you are screening against

Almost every drop in this genre follows the same shape:

1. **Tier 0 — free, 1..N per Agent ID** (`free_cap` total, `max_per_wallet` per wallet). This is the actual prize.
2. **Tier 1+ — paid ladder** (0.0002–0.002 BNB per unit, rising in steps). Usually a bad trade at mint price.
3. **Sometimes a refundable deposit** — you pay `qty × price` but can `claimRefund()`/`withdraw()` later, which is
   effectively free capital-wise (see the AGC case study in `07-case-studies.md`). Verdict "paid" without reading the
   refund path is a screening bug, not a safety win.

Two consequences worth internalising:

* **Free slots die in hours-to-days, not weeks.** A drop can be fully swept between two of your polling ticks.
* **The paid ladder never disappears**, so there is no urgency and no reason to pay to "not miss out".

## Where the tutorials go next

* `01-gate-mechanics.md` — the two ways a contract enforces the gate (this determines your recon path).
* `02-discovery.md` — how you find drops before their free tier is gone.
