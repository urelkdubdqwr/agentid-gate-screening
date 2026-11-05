**[urelkdubdqwr](https://github.com/urelkdubdqwr)** · [website](https://studiopinggirkasur.xyz/)

<!-- agentid-gate-screening — how to screen Agent ID-gated NFT/token drops -->

<img src="assets/header.svg" alt="agentid-gate-screening — find, verify, and mint Agent ID-gated drops before you sign" width="100%">

**Screen a `.ai` Agent ID–gated drop before you sign: what it really costs, whether the free tier is still alive, and whether the contract deserves your wallet.**

## What it is

A standalone playbook plus five read-only screeners for the drops that gate on a Binance **Agent ID** (`.ai`) — NFT
collections, token launches, mint farms, whitelist rounds. It walks the whole path: discovery feeds → bytecode truth →
free-tier test → pre-mint risk check → transaction → on-chain verification.

The premise is that a landing page is not evidence. "Free mint" means `estimateGas(value = 0)` passes from your wallet
right now; "sold out" means `free_minted >= free_cap`; "gated" means the contract's own registry getter points at the
real Agent ID registry. Everything else is marketing with a countdown timer next to it.

Nothing here holds a key or signs anything. The scripts are read-only by design (`eth_call`, `eth_estimateGas`, public
HTTP APIs), so a cloned copy can never spend from your wallet — and there is no secret in it to leak. They also never
bypass a gate: a wallet without an Agent ID still cannot mint, which is the point.

## How it works

![agentid-gate-screening architecture](assets/ecosystem.png)

- **Discovery is polled, not awaited.** `scripts/radar.py` reads the public launch radar, the public call channel and
  the curated catalog, keeps only entries whose gate reference mentions the Agent ID registry, dedupes against a state
  file, and prints nothing when nothing is new — so it can run on a schedule without turning into noise.
- **Recon reads the dispatcher, not the tweet.** `scripts/recon.py` pulls runtime bytecode, detects EIP-1967 proxies,
  recovers every function selector and names them (4byte / openchain). That is how a contract exposing only
  `openFree()` `0x1644fa8e` and `agentRegistry()` `0x0d1cfcae` — names no template expects — still gets judged
  correctly instead of written off as a dead end.
- **"Free" is a simulation, not a claim.** `scripts/free_tier.py` reads `FREE_SUPPLY` / `MAX_SUPPLY` /
  `MAX_PER_WALLET` / `price` / `mintedBy(you)` / `costFor(qty)`, then simulates `mint(qty)` with `value = 0`. Pass =
  the mint is free for that quantity; revert = decode the selector, then check whether the value that *is* demanded
  comes back through a `claimFree()`/refund path — which makes it a deposit, not a price.
- **Safety is mechanical before it is judgement.** `scripts/safety.py` reports source verification, upgradeability,
  owner powers (`pause`, `withdraw`, `transferOwnership`), the payee, and whether the mint path carries approvals or
  `transferFrom` — the plumbing a drainer needs.
- **Verify with the contract's own view.** After signing (Foundry `cast`, a small `web3.py` script, or an MPC agent
  wallet CLI), success is `receipt.status == 1` **plus** a moved balance or an ownership mapping that names your
  wallet. `BROADCASTED` is not a result.

Verdict rules — full logic in [`docs/03-verify-onchain.md`](docs/03-verify-onchain.md):

| Evidence | Meaning |
| --- | --- |
| `estimateGas(mint, value = 0)` passes | the mint is free, or a fully refundable deposit — read the spec |
| `estimateGas` reverts | tier gone, wrong selector, or a time gate — decode before concluding |
| `free_minted >= free_cap` | free slot dead; paying does not "unlock" it |
| `agentIdRegistry()` / `agentRegistry()` = `0x60B9…022F` | the real Binance Agent ID registry is enforced |
| landing page says "free" | worthless on its own — never evidence |

## Quickstart

```bash
git clone https://github.com/urelkdubdqwr/agentid-gate-screening.git
cd agentid-gate-screening

./smoke.sh                       # read-only: runs every screener against a live gated contract
./smoke.sh 0xYourWallet          # optionally include the wallet-dependent checks

# the manual path, one command at a time
python3 scripts/gate_check.py --wallet 0xYourWallet          # do you even hold a .ai Agent ID?
python3 scripts/recon.py 0xContract                          # code size, proxy, selectors, gate getter
python3 scripts/free_tier.py --wallet 0xYourWallet --qty 1 0xContract
python3 scripts/safety.py 0xContract                         # owner powers, plumbing, source check
python3 scripts/radar.py --hours 24 --free-only              # what is live right now
```

Needs Python 3.9+ and one public BNB Chain RPC (default `https://bsc-dataseed.binance.org`, override with `--rpc` or
`RPC_URL`). No `pip install`, no API key, no account. Ethereum-side rounds are screened with the same scripts by passing
an Ethereum RPC.

## What's inside

| Path | What it is |
| --- | --- |
| [`docs/00-what-is-agent-id.md`](docs/00-what-is-agent-id.md) | what a `.ai` Agent ID is, where it lives, why projects gate on it |
| [`docs/01-gate-mechanics.md`](docs/01-gate-mechanics.md) | the two gate designs: on-chain registry check vs backend EIP-712 voucher |
| [`docs/02-discovery.md`](docs/02-discovery.md) | the discovery feeds worth polling (APIs, catalogs, channels, X) |
| [`docs/03-verify-onchain.md`](docs/03-verify-onchain.md) | bytecode recon, selector recovery, free-tier reads, simulation, verdicts |
| [`docs/04-risk-checklist.md`](docs/04-risk-checklist.md) | pre-mint checklist: owner powers, honeypots, drainers, taxes |
| [`docs/05-execute-and-verify.md`](docs/05-execute-and-verify.md) | signing paths, receipts, balance/ownership proofs |
| [`docs/06-automation.md`](docs/06-automation.md) | turning the manual loop into a watcher that stays quiet when nothing happens |
| [`docs/07-case-studies.md`](docs/07-case-studies.md) | real drops, real txs, what worked and what got missed |
| [`scripts/gate_check.py`](scripts/gate_check.py) | does this wallet hold a `.ai` Agent ID? |
| [`scripts/recon.py`](scripts/recon.py) | bytecode, proxy detection, selector recovery + naming |
| [`scripts/free_tier.py`](scripts/free_tier.py) | free-tier state reads + `value = 0` simulation |
| [`scripts/safety.py`](scripts/safety.py) | owner powers, token plumbing, source verification |
| [`scripts/radar.py`](scripts/radar.py) | live discovery of new Agent ID–gated launches |
| [`scripts/lib.py`](scripts/lib.py) | JSON-RPC + ABI-shim helpers shared by the above |
| [`smoke.sh`](smoke.sh) | read-only proof the repo works from a fresh clone |
| [`data/known-drops.csv`](data/known-drops.csv) | verified Agent ID–gated drops and their free rule |
| [`data/field-notes.md`](data/field-notes.md) | traps, false verdicts, timings |
| `assets/diagram.mmd` + `assets/ecosystem.png` | pipeline diagram, source + render |

## License

MIT — see [LICENSE](LICENSE).

*Worked from the edge of the bed. → [studiopinggirkasur.xyz](https://studiopinggirkasur.xyz/)*
