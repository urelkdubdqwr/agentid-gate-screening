# Field notes — traps, false verdicts, timings

Raw, unpolished lessons. Add to this file whenever a screening call turns out wrong.

## False verdicts and why they happened

| Symptom | Wrong conclusion | Real cause | Fix |
| --- | --- | --- | --- |
| `FREE_SUPPLY 50`, `minted 50`, card said "free 0/50 open" | "free tier alive" | API returns `free_minted: null`; code defaulted it to 0 | if `free_minted` is null, use `min(total_minted, free_cap)` |
| `estimateGas` reverts "unknown selector" | "gate closed" | custom error we had not seen, or the wrong entry point (`openFree()` not `mint(1)`) | read the dispatcher first; look the selector up |
| `quote()`/`priceOfNth()` returns 0 for every index | "it is free" | the view is a stub / ladder tail | only `costFor` + simulation settle it |
| landing page says "free" | free | marketing copy lags the on-chain counter by hours | chain only |
| `currentPrice() == 0` | free | the *first* ladder step only; per-wallet ladder may already be past it | read `mintedBy(you)` too |
| `withdraw()` present | rug signal | normal treasury plumbing; check `payee()` instead | judge powers by who holds them |
| unverified bytecode | skip | verified source is a convenience, not a requirement | read the dispatcher and the storage |

## Timing observations

* Free windows on this genre have run **hours to ~3 days**. The three observed misses all happened inside the first
  24h.
* A fresh contract with `minted < 30` and `agents < 15` is usually < 2h old — those are the ones worth a full recon.
* Gas on BSC at 0.05 gwei: a 210k-gas mint costs ≈ 0.0000105 BNB. Ten mints ≈ 0.0001 BNB. Gas is never the reason to
  skip a genuinely free unit; **price** is.
* Public RPC `eth_getLogs` windows: keep the block range ≤ ~2k or you will get `-32701`.

## Operational notes

* `free_tier.py --qty N` is the workhorse: `costFor(N) == 0` **and** a passing `value = 0` simulation means N free
  units, no interpretation required.
* If a mint succeeds but the NFT balance shows nothing, check for a two-step commit/reveal (`commitFreeMint` →
  `reveal`) or an ERC-1155 id you have not read out of the `TransferSingle` logs. Balance 0 right after a commit is
  not a failure.
* Some contracts mint to `msg.sender` only; a "mint for a friend" option in the UI is usually a different function with
  a different gate. Do not assume.
* Keep the state file (radar dedupe) out of the repo. A watcher that re-reports on every tick gets muted, and then you
  miss the drop it was built for.

## Sources worth re-checking weekly

* `unitytool.app` Agent Radar (`/api/launches`, `/api/project`, `/api/audits`) — new contracts referencing the registry.
* `agentidhub.eth.limo` `project-catalog.js` — curated verdicts, useful as context, always re-check the free tier.
* `t.me/s/agentidcall` — call channel; leads with progress numbers and risk lines.
* X threads from operators who post "N free Agent ID mints" lists — treat as leads, feed straight into `recon.py`.
* Rewards/launchpad configs on project sites (`/js/config.js`, `/agent.json`, `llms.txt`) — often publish the ABI,
  the ladder and the free rule faster than any indexer.
