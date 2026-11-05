# 06 — Automation: a watcher that is silent until it matters

Manual screening works until the first drop you miss. The fix is a polling loop with three properties:

1. **cheap** — no LLM per tick, just HTTP + `eth_call`;
2. **idempotent** — a state file decides what has already been reported;
3. **silent** — no output means no message; an empty tick must not ping you.

---

## The loop

```
fetch radar (/api/launches)
  └─ filter: gate∈{bytecode,behavior} AND gate_ref mentions Agent ID
       └─ for the newest N unseen items:
            fetch /api/project/<addr>     -> free_cap, free_minted, minted, price
            eth_getCode + selector scan   -> is the registry call really there?
            eth_estimateGas(value=0)      -> is it free for MY wallet right now?
       └─ report only: new item, or free tier that just opened/closed
```

`scripts/radar.py` implements exactly this and can be run from cron.

```bash
python3 scripts/radar.py --hours 24 --free-only            # human table
python3 scripts/radar.py --json > state_snapshot.json      # machine output
```

## State, not vibes

```json
{
  "seen": {
    "0xc9f30f3d8e8858c3360eb96843a8de9138e27ec4": {
      "reported_at": 1793888288,
      "free_open": true,
      "free_minted": 5
    }
  }
}
```

Rules:

* report an address **once**; re-report only when `free_open` flips or the free counter jumps;
* keep the state file out of the repo (`.gitignore`) — it is runtime data;
* never key change-detection on counters that move every tick (block height, countdown, total supply of a growing
  collection). Those make every tick look "changed" and destroy the silence.

## Scheduling

```cron
*/20 * * * * cd /opt/agentid-gate-screening && RPC_URL=$RPC_URL python3 scripts/radar.py \
             --hours 6 --free-only --state /var/lib/agentid-screen/state.json \
             --quiet-empty >> /var/log/agentid-screen.log 2>&1
```

`--quiet-empty` prints nothing when there is nothing new. Pipe that into your notifier of choice (Discord webhook,
Telegram bot, `mail`). One message per discovery, zero per poll.

If you run this from an agent framework with its own scheduler, the same three rules apply — the state file is the only
thing that must survive between ticks.

## Anti-patterns that look like automation but are not

| Anti-pattern | Why it fails |
| --- | --- |
| polling the project's HTML page | you get the marketing copy, not the tier state |
| re-reporting every tick "to be safe" | alert fatigue; you stop reading, then you miss the real one |
| retrying a `NoAgentId` revert | the gate will never flip; you just burn RPC quota |
| a watcher that dies with the session | the whole point of the free tier window is that it outlives your attention |
| caching the contract ABI forever | templates get redeployed with new selectors; re-read the dispatcher |

## Burst detection (optional, higher precision)

Instead of trusting feeds, watch the chain: scan `Transfer(0x0 → *)` logs on a rolling window and flag contracts
that mint ≥ 25 units/hour and are not in your registry yet. That is how you catch a drop whose website and socials do
not exist yet — the contract is live before the marketing is.

```bash
# eth_getLogs Transfer(from=0x0) over the last ~1200 blocks (≈1h on BSC)
curl -s $RPC_URL -H 'content-type: application/json' -d '{
  "jsonrpc":"2.0","id":1,"method":"eth_getLogs","params":[{
    "fromBlock":"0x7db000","toBlock":"latest",
    "topics":["0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef",
              "0x0000000000000000000000000000000000000000000000000000000000000000"]
  }]}' | jq -r '.result[].address' | sort | uniq -c | sort -rn | head
```

Then run `recon.py` + `free_tier.py` on the top addresses. Public RPCs often cap `eth_getLogs` ranges — if you get
`-32701`, use a wider-range provider or chunk the window.
