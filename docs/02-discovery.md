# 02 — Discovery: where new Agent-ID drops actually show up

The free tier is gone in hours. Discovery is the part of screening that decides whether you get anything at all.
There are four classes of source; use all of them, they fail differently.

---

## 1. On-chain radar (best signal, machine-readable)

**`unitytool.app` — "Agent Radar"** indexes every BSC contract that *references* the Agent ID registry in its bytecode
and publishes the ones that look like launches.

```bash
# new / recently seen agent-gated launches
curl -s 'https://unitytool.app/api/launches?limit=500' \
     -H 'referer: https://unitytool.app/' | jq '.items[] | select(.gate=="bytecode") | {name,addr,description,first_seen}'
```

Fields that matter:

| Field | Why |
| --- | --- |
| `gate` | `bytecode` / `behavior` = it really references the Agent ID registry |
| `gate_ref` | human string, e.g. “铸造合约 0x… 引用 Binance Agent ID” |
| `first_seen` | age in seconds — the fresher, the more free tier is left |
| `description` | often contains the actual free rule ("First 50 free, then 0.0005 BNB. Max 5 per wallet") |
| `agents` | distinct Agent-ID wallets already touching it — the crowd meter |

Detail endpoint adds the mint mechanics:

```bash
curl -s 'https://unitytool.app/api/project/0x8891c1F1A2B3…' -H 'referer: https://unitytool.app/' \
  | jq '.launch | {free_cap, free_minted, minted, price, price_usd}'
```

Other endpoints on the same host: `/api/audits` (risk level per contract), `/api/search?q=`, `/api/agent/<wallet>`,
`/api/wallets/top`, `/api/events` (SSE feed with global counters).

> **Gotcha:** without the `referer` header the API sometimes answers `error code: 502`. Send it, and retry.

`scripts/radar.py` wraps all of this (see `06-automation.md`).

---

## 2. Curated catalogs (best context, always slightly stale)

**`agentidhub.eth.limo`** — a curated catalog of ~1,000 projects in the ecosystem, with per-project
`verdict` (can-join / cost / risk / deadline / score), `quality`, `mintProgress` and source links.
The data is not an API: it ships as `project-catalog.js` (`globalThis.AGENTID_PROJECT_CATALOG`, several MB).

```bash
curl -s https://agentidhub.eth.limo/project-catalog.js \
  | sed 's/^.*= //; s/;$//' > catalog.json
jq '.generatedAt, (.projects|length)' catalog.json
jq -r '.projects[] | select(.verdict.canJoin=="yes") | [.name, .verdict.cost.en, .verdict.risk] | @tsv' catalog.json
```

Use it for **context** (is this project legit? what did someone else conclude? is the contract verified?), never as
truth about *today's* free-tier state. Re-check on-chain before minting.

---

## 3. Call channels and X (fastest, least reliable)

Telegram channel previews are scrapeable without an account:

```bash
curl -s https://t.me/s/agentidcall | grep -o 'js-message_text[^>]*>[^<]*' | head
```

These posts usually carry: project name, contract address, progress (`531/2000`), a 5-part score and a risk line.
Treat the address as a **lead**, never as a verified contract — feed it straight into `scripts/recon.py`.

X threads listing "22 free Agent ID mints" are also leads. To read a specific post without API credits:

```bash
curl -s https://api.fxtwitter.com/<handle>/status/<id> | jq -r '.tweet.text'
```

---

## 4. Watcher wallets (highest precision, but you must curate)

Follow a handful of *smart Agent-ID wallets* (operators who mint early and often) and diff their recent transactions:

```bash
# every tx from a watched wallet, newest first
curl -s "https://api.bscscan.com/api?module=account&action=txlist&address=0xWatched&sort=desc&page=1&offset=20"
```

When 7+ watched agents call the **same contract with the same selector and `value = 0`** inside a short window, that
is a live free mint. That rule (count + value + selector) is what turns a noisy watchlist into a signal.

---

## Ranking: what to look at first

```
score = free tier still open            (free_minted < free_cap)      -> mandatory
      + age < 6h                        (first_seen)                  -> strong
      + gate_ref mentions Agent ID                                     -> strong
      + agents counter climbing         (agents, agents1h)            -> medium
      + verified source / low risk      (safety.py, /api/audits)      -> medium
      - price > 0 on the *first* unit   (costFor(1) != 0)             -> heavy penalty
```

Rules of thumb:

* Anything older than ~48h with `minted > 0` has probably lost its free tier — check `free_minted` first, do not
  spend a full recon on it.
* A drop minted by < 10 agents is either very new or a ghost. New = good. Ghost = still cheap to test.
* Ignore "sold out" claims from the site; `totalMinted()` and `FREE_SUPPLY()` are one `eth_call` away.
