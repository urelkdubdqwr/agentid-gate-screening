# 13 — FCFS windows: read the clock from the contract and race properly

"First 800 shares, first come first served" is not a transaction, it is a race. Measured on one live Agent-ID-gated
sale: 800 slots, 1 439 competing transactions, first successful claim at T+1 s and the last at T+26 s. A serial wallet
loses to a parallel one for reasons that have nothing to do with merit.

## 1. The opening time is on-chain

Read `startTime()` `0x78e97925` (or the local equivalent) — not the page countdown. Pages are often rendered in
`Asia/Shanghai` (UTC+8); convert to UTC before telling anyone "it opens at 21:00 local".

## 2. Preflight at T-15 minutes

Per wallet, in one pass: identity gate (`hasId`, `account()`), `freeClaimed`, native balance, `gasPrice`, and the
signing session. A preflight that fails at T-15 gives you 15 minutes to fix; the same failure at T-0 is a lost slot.

Fund every participating wallet **before** the window: a wallet with < ~0.00003 BNB dies at the start line. One gas
top-up the day before costs pennies.

## 3. At T-0, fire all wallets in parallel

Threads, not a loop. Each attempt is ~0.9 s over an MPC/agent wallet and ~0.2–0.5 s with a local pre-signed raw
transaction, so serialising wallets guarantees the second one starts after the window closes.

* retry every ~150 ms with a deadline of 60–90 s (not 12 attempts spaced 2 s);
* **no RPC reads at T-0** — no preamble, no `account()` re-check, no re-simulation. Everything pre-T-0; the first
  attempt goes out immediately;
* pre-sign at T-2 s and send at T0 when you control the key, bumping the nonce on retries.

## 4. Read the revert, then decide

Custom errors without a signature-database entry: hash candidate names yourself
(`FreeOver()`, `SoldOut()`, `NotOpen()`, `BadTime()`, `AlreadyClaimed()`, `NoAgentId()`, `QuotaExceeded()`).

* `FreeOver()` → stop, supply is gone (retrying only burns gas).
* `NotOpen()` / `BadTime()` → keep firing, the window is not open yet.
* Revert 4 hours before `startTime()` is a **time gate**, not ineligibility. Verify eligibility from
  `account(wallet).hasId` / `freeClaimed(id)`, never from that revert.

## 5. Post-mortem: measure the real window from the chain

Binary-search blocks for `timestamp >= startTime`, sweep ~70 blocks forward, and note the offset of the first and last
successful claim. That is what separates "lost by a second" from "wrong selector".

## 6. Route reality check

An Agent ID gate can only be satisfied by a wallet that actually holds a `.ai` handle — a locally generated hot wallet
cannot fake it. So:

* Agent-ID-gated races → the agent/MPC wallets, in parallel;
* pure on-chain gates (holder lists, public FCFS) → local pre-signed hot wallets, faster;
* decide which barrel you are in **before** T-0 by simulating once with `--simulate`: `NoAgentId()` = account gate,
  not a time gate.

## 7. Ladder after the window

Schedule follow-up attempts at T+10 / T+40 / T+90 minutes with a `--silent-if-done` flag that exits quietly when every
wallet already shows `freeClaimed`. Windows reopen (owner unpauses, unsold shares return); a one-shot cron misses that.

## 8. Report with counters

`soldShares / totalShares`, `isLive`, per-wallet attempts, seconds, tx hash, revert selector. "Lost the race" and "we
were never eligible" look identical in a card that only says "failed".
