# 14 — Smart-wallet follow: track the wallets that keep winning

The last rung of the ladder is not "find the next drop" — it is "watch wallets that already find them". Agent-ID
wallets are attributable (`handle.ai`, one owner, public record), which makes them unusually good to follow.

## 1. Build the watchlist from outcomes, not from follower counts

Rank candidate wallets by what they actually did: tokens they were early on, mints that later traded, positions still
open. Signals worth keeping:

* first-buyer on tokens that then held value for days (not the same block as deploy);
* a mint history that is mostly free-tier or allowlist, i.e. they read the same mechanics described in this repo;
* consistent behaviour across two different ecosystems, so you are not following one lucky trade;
* a public handle you can read (their posts tell you *why* they moved, which is the part a block explorer cannot).

Filter out: wallets that only sniped the deploy block, wallets whose inbox is 90% airdrop dust, and anything whose
position sizes are in a league you cannot copy.

## 2. Rank by edge, then gate on your own budget

Two numbers per wallet: hit rate (share of entries that did not immediately bleed) and median hold. A 20% hit rate
with long holds is often more copyable than a 60% rate on 20-minute scalps. Then apply *your* constraints: gas budget,
per-position size, and the free-only rule on anything gated.

## 3. Entry and exit rules that survive unattended

* entry is a **notification**, not an automatic buy: size the position from a fixed budget, never from a percentage of
  someone else's;
* take-profit at a multiple of your own cost, then a trailing stop from the peak (e.g. take-profit at +100% of the
  position, trail 15% below the high) — mechanically, in code, because the whole point is not to be watching;
* if a copy would exceed the per-position cap, skip it and log the skip;
* exit on the *wallet's* exit only when you can observe it in the same block-relevant window; otherwise use your own
  levels and say so.

## 4. Operational hygiene

* watch addresses from the chain (transfers in/out), not from screen-scraped dashboards;
* one state file per target with the last seen block, so a restart does not re-notify the whole history;
* rate-limit notifications per wallet — a noisy watcher gets muted, and a muted watcher is worse than none;
* distinguish "new position" from "existing position added" from "round-tripped" before alerting.

## 5. Where this fits the rest of the repo

Discovery (02, 11) finds drops; screening (03, 04, 10) says whether they are real; execution (05, 13) gets them cheap.
Following smart wallets is the **front of that pipeline** — it tells you where to point discovery. It does not replace
screening: a wallet being early says nothing about a new contract being safe.

## 6. Honest limits

Copy-trading from public data is a latency game you will usually lose on the same-block stuff. The edge here is the
**slow middle**: allowlists, free tiers, and mechanics that take 10+ minutes to understand — exactly the part that bots
do not do well and this repo is written for.
