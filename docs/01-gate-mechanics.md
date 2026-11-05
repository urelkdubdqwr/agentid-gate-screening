# 01 — The two gate designs (and how they change your recon)

There are exactly two ways a drop can enforce "Agent ID only". You must know which one you are looking at before
you simulate anything, because the failure modes are different.

---

## Design A — on-chain registry check (the common one)

The mint contract holds the registry address and calls it during mint:

```solidity
IERC721 reg = IERC721(agentIdRegistry);          // BSC 0x60B9…
require(reg.balanceOf(msg.sender) > 0, "NoAgentId");
```

**How to recognise it**

```bash
python3 scripts/recon.py 0xContract          # look for these selectors in the recovered ABI
```

| Selector | Signature | Meaning |
| --- | --- | --- |
| `0x8854a0ff` | `agentIdRegistry()` | contract exposes the registry it gates on — gold standard |
| `0x4eab3ef2` | `hasAgentId(address)` | boolean helper, common in older drops |
| `0x1d2e6765` | `mintableBy(address)` | precomputed eligibility |

If `agentIdRegistry()` returns `0x60B9262456dE011F7d15a54CdD8c48bAaa8B022F`, the gate is real and it is the
official registry — nothing else to argue about.

**What you can simulate cheaply**: everything. `eth_estimateGas` with `value = 0` from your wallet is a full dry run.
Pass = you can mint *that quantity right now, for zero payment*. Revert = either the gate rejects you, the free tier is
gone, or the selector/arg shape is wrong — decode the revert (see `03-verify-onchain.md`).

**Failure modes specific to Design A**

* *Free tier is a global counter, not per-wallet* — `FREE_SUPPLY` gets drained by everyone; `free_cap - minted` is the
  only number that matters, and it moves between your read and your tx.
* *Free tier is per-wallet* — `mintedBy(wallet) < max_per_wallet` and the price is a ladder per wallet. Both shapes
  exist; read `costFor(qty)` instead of guessing.
* *Quantity-shaped free mints* — some contracts are `freeMint(uint256 qty)` while the paid path is `mint(uint256 qty)`.
  Simulating the wrong one looks like "tier gone" when it is just the wrong function.

---

## Design B — backend-signed EIP-712 voucher

The mint contract has no registry call at all. Instead:

1. you POST your handle + minter address to the project's backend,
2. the backend reads the BNB registry itself, checks the free/presale state, and **signs a voucher** bound to
   `(minter, shares, nonce, deadline)`,
3. the contract only verifies the signature (`ecrecover`) and the replay counter.

Real example: `$AGI` on Ethereum mainnet (`agentideth.com`) — mint lives on ETH, identity lives on BNB Chain.

**How to recognise it**: no `agentIdRegistry()` selector; instead the mint function takes a `bytes signature` /
`bytes sig` argument, and the docs mention a voucher/signature endpoint.

**Failure modes specific to Design B**

* **The minter must be the wallet that owns the Agent ID.** There is no way to mint from a different (better-funded)
  wallet: `{"error": "Minter wallet does not own this Agent ID."}`. Plan funding accordingly — this is the #1 surprise.
* **The backend is the gate.** When it says the free round is full, it is full, even if the contract would accept a
  voucher. Poll the backend endpoint, not only the chain.
* **The voucher has a nonce + deadline**; a stale voucher is a revert, and asking for a new one after a state change can
  hand you a different price.
* Everything the backend tells you is a claim. Simulate the final `mint(...)` calldata anyway — the contract is the judge.

---

## Quick decision tree

```
contract exposes agentIdRegistry() / hasAgentId() ?
├── yes  -> Design A: simulate mint(qty) with value 0 from your wallet.
│           passes -> free, go.  reverts -> decode (gate? tier? selector?).
└── no, but mint takes a signature and backend has an /api
         -> Design B: verify handle on the backend, fetch voucher,
            assert voucher.minter == your agent wallet, then simulate the mint.
```

## Gate-adjacent traps

* **Registry copycats.** A contract can point `agentIdRegistry()` at *any* ERC721. Only accept
  `0x60B9262456dE011F7d15a54CdD8c48bAaa8B022F` as the real Binance registry; anything else is a gate with the same
  name and none of the meaning.
* **"Agent gated" in marketing only.** Some launches call themselves agent-native but gate on a plain allowlist or
  nothing at all. If there is no registry call and no voucher, it is an open mint wearing a costume.
* **Cross-chain voucher mismatch.** Identity on BSC, mint on ETH/Base — the wallet address is the same, the chain is
  not. Approvals and gas live on the mint chain.
