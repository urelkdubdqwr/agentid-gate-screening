# 04 — Pre-mint risk checklist

Free does not mean safe. The gas is cheap, but these contracts can still cost you the NFTs you already hold.
Run this list before **every** first mint on an unknown contract. `scripts/safety.py` automates the mechanical parts.

---

## 1. Does the mint touch your other assets?

Read the bytecode path the mint call takes. Red flags:

* the mint function calls `transferFrom(...)` / `safeTransferFrom(...)` on an **external token contract you did not pass
  in as an argument** — that is how "free mint" drainers take existing NFTs;
* the mint takes an arbitrary token/collection address parameter *and* an approval as an argument;
* a `setApprovalForAll` / `permit` appears in the mint path (you never need one to receive an NFT).

Rule: a legitimate free mint sends you a token and reads state. It does **not** move anything of yours.

## 2. Owner powers

| Capability | Selector | Risk |
| --- | --- | --- |
| unpause / pause minting | `0x8456cb59` / `0x02329a29` | low — normal for staged drops |
| `withdraw()` | `0x3ccfd60b` | fine when the payee is a multisig; check `payee()` |
| `setBaseURI` / reveal | — | fine, but un-revealed metadata is not a rug |
| `setPrice` / ladder edits | — | medium for paid tiers, irrelevant for free |
| renounced ownership | `owner() == 0x0` | best case; not required for a free mint |
| upgradeable proxy | EIP-1967 slot non-zero | medium — the logic can be swapped after you mint |

## 3. The three "free" traps

1. **Free tier is a teaser for an expensive ladder** — the first unit is 0 and unit #2 costs 20× market. Fine if you
   only take the free unit; never let a UI bundle them (`mint(5)` when only #1 is free is a paid tx).
2. **Refundable deposit presented as paid** — `msg.value = qty × price` with a real `claimRefund()`/`withdraw()`.
   Capital is parked days, not lost. Read the refund function before calling it "paid".
3. **Free shard of a fee-on-transfer token** — you receive a token that taxes every transfer. Worth something only if a
   pool exists; check for a pair before counting it as value.

## 4. Contract-level hygiene

* **Verified source?** `https://sourcify.dev/server/v2/contract/56/0xAddr?fields=metadata` or the explorer API.
  Unverified is not automatically bad, but then the bytecode *is* your spec — read it (Step 2 in `03-verify-onchain.md`).
* **Holders / concentration**: if 3 wallets hold the rest of the collection, "floor" is fiction.
* **Market exists?** No marketplace listing, no market. Free souvenirs are fine; anything you pay for is not.
* **Reentrancy in the mint path**: check for the classic state-after-external-call pattern
  (`call{value: ...}` before the supply counter increments). Cheap to spot in the meta, expensive to ignore.

## 5. Wallet hygiene (your side)

* Use an **agent wallet you dedicated to this genre**; do not mint from the wallet holding your main assets.
* Keep a small BNB float for gas (0.005–0.01 BNB covers a lot of 200k-gas mints at 0.05 gwei).
* Never approve `setApprovalForAll` for a mint you have not read.
* Revoke approvals periodically: `https://revoke.cash` or an on-chain `approve(spender, 0)`.

## 6. Scoring template

Copy this into your notes per contract and fill it in; anything below the line means **skip**:

```
PROJECT:                     CONTRACT:
[ ] gate is the official registry (0x60B9…022F) or a signed voucher
[ ] mint path does not move any token of mine
[ ] owner powers understood (pause / withdraw / upgradable)
[ ] free unit is genuinely free: estimateGas(value=0) passes
[ ] free quota counts against a cap I can still fit into
[ ] bytecode or verified source read at least once, by me
[ ] no "you must buy before you can claim" clause
[ ] known refund path if value > 0
------------------------------------------------------------
[ ] after mint: receipt status 1 AND balanceOf delta confirmed
```

`safety.py` prints the mechanical half of this (owner functions, external-call targets, source verification,
proxy detection) with an explicit "unverified bytecode = read it yourself" warning.
