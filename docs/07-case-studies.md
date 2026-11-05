# 07 — Case studies (real drops, real transactions)

Every case below is a live contract on BNB Chain (or Ethereum, where noted), with the evidence that produced the
verdict. Addresses and selectors are public chain data. Where a mint was actually taken, the receipt is cited.

---

## 1. Cipher Agent / Tessera Agent — free tier is per-wallet ×5, not "1 free unit"

Found by the radar, minutes after deployment (that is the point of `02-discovery.md`).

| | Cipher Agent | Tessera Agent |
| --- | --- | --- |
| contract | `0xc9f30f3d8e8858c3360eb96843a8de9138e27ec4` | `0x98577dc06adafd432cff0c92517b936e2bce7b46` |
| `MAX_SUPPLY()` | 700 | 488 |
| `FREE_SUPPLY()` | 50 | 50 |
| `MAX_PER_WALLET()` | 5 | 5 |
| `PRICE()` | 0.0005 BNB | 0.0005 BNB |
| `agentIdRegistry()` | `0x60b9…022F` ✅ | `0x60b9…022F` ✅ |

Screening transcript (abridged):

```
FREE_SUPPLY 50 · MAX_PER_WALLET 5 · PRICE 0.0005 BNB
costFor(5) = 0 wei                    <- five units are free right now
estimateGas mint(5) value 0 -> 212,801  <- passes, so the free mint is real
```

Minted `mint(5)` on both, value 0. Result: **5 + 5 NFTs** for ~0.000037 BNB of gas in total
(receipts `status 1`, `gasUsed` 206,458 and 206,489; `balanceOf(wallet)` = 5 and 5).

**Lesson:** `MAX_PER_WALLET` is a *free quota*, not a paid limit, in this template. Reading only "1 free per wallet"
from a tweet would have left 8 free units on the table.

---

## 2. AgentBox — the interface you did not expect

Call-channel lead: `0x08393dad165d90e7258501fe1dfb5f3498644011` — "Agent ID can open 1 box free (gas only)".

`recon.py` recovered **85 selectors** and none of the usual suspects. No `mint(uint256)`, no `FREE_SUPPLY()`.
Instead:

| selector | signature | role |
| --- | --- | --- |
| `0x0d1cfcae` | `agentRegistry()` | the gate (note: not `agentIdRegistry()`) |
| `0x1644fa8e` | `openFree()` | the free entry point |
| `0x17a37067` | `freeOpened(address)` | per-wallet used flag |
| `0x5ebad500` | `nextBoxId()` | box counter |
| `0x4ed3faf2` | `boxes(uint256)` | box → owner mapping |
| `0x603f4d52` | `saleState()` | 7-word sale config |

Verdict path: `agentRegistry()` = `0x60b9…022F` ✅ official; `estimateGas openFree() value 0` → 209,351 ✅;
`claim()` reverted with a custom error carrying a timestamp (time gate — do not brute-force it).

Executed `openFree()`: `status 1`, gas 203,049, and `boxes(4248)` listed the minting wallet as owner.

**Lesson:** a generic "check `FREE_SUPPLY` / `mint(uint256)`" screener says *n/a* here and would call it a dead end.
The dispatcher is the spec — `recon.py` is not optional. Also: `agentRegistry()` and `agentIdRegistry()` are
different functions; both can point at the same registry, but only one will exist in any given contract.

---

## 3. $AGI / AgentID (agentideth.com) — gate on BNB, mint on Ethereum, voucher in the middle

Design B in the flesh. Identity registry lives on BSC; the mint contract is on **Ethereum mainnet**:
token `0xBF01…a461`, mint `0xB27e…c459`.

Screening outcome at launch:

* `/api/connect {handle}` → verified the handle against the BNB registry and returned the derived wallet;
* `/api/bind-x` → one X account per Agent ID (social gate on top of the identity gate);
* whitelist round **500/500 full**, public free round **full** → the only lane left is the paid ladder ($1.00 →
  $8.04 per share, 10,000 tokens per share, max 15 shares/wallet);
* `/api/voucher` with a *different* minter → `{"error":"Minter wallet does not own this Agent ID."}` — the voucher is
  bound to the agent wallet, so you cannot mint from a better-funded wallet;
* `/api/voucher` with `wl=true` on a non-whitelisted agent → `{"error":"Whitelist allocation is 0."}`.

**Lesson:** screen the **backend** as carefully as the contract on voucher-gated drops. "Free" and "sold out" are
server-side facts here, and the minter is fixed before you ever touch a tx.

---

## 4. AGC / Agentic Coin — `value > 0` that is actually free

`mintFree(uint256,address)` (`0x0db5ae5a`) requires `msg.value == shares × 0.002 BNB` or it reverts `WrongValue()`.
A screener that treats nonzero value as "paid" writes this drop off. Read the exit: `claimFree(uint256[])`
(`0x73fc9ccc`) refunds the deposit in full after 24h, plus a base reward.

**Lesson:** always look for `claimFree` / `refund` / `withdraw` before labelling a mint "paid". Deposits that come back
are free with a lock-up, not a cost.

---

## 5. FAGENT / FIST Agent — the miss that shaped the pipeline

`claimFree()`, 1 share = 50,000 tokens per Agent ID, 4,444 free slots, opened 2026-10-28 07:35 UTC.
By the time the news thread was read and the contract was fully reconned, `freeClaimed == MAX_FREE_SHARES`
and `launched == true`.

Same pattern repeated on two more drops that week (NIULAI: 4,444 slots gone before a one-hour-old check).

**Lesson:** three misses, one cause — *research latency*. The fix is ordering, not effort:

```
freeClaimed() < MAX_FREE_SHARES ?  -> mint first, research after
```

Reading a landing page before simulating is a self-inflicted race condition.

---

## Pattern summary

| Signal | What it really means |
| --- | --- |
| `MAX_PER_WALLET()` ≥ 1 with `costFor(N) == 0` | N free units per wallet — take N, not 1 |
| `FREE_SUPPLY()` − `totalMinted()` small | hours left, not days |
| `value > 0` + existing `refund()` | deposit, not price |
| `estimateGas` revert with a custom error + timestamp | time gate — wait, do not retry-loop |
| unknown function names in the dispatcher | a template you have not met; read it, do not assume |
| backend `{"error": "… full"}` | the chain cannot help you; the lane is closed |
