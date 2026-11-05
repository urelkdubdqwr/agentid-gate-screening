# 12 — `value > 0` is not always "paid": deposit-and-refund farms

Contracts in this genre often ask for `msg.value > 0` and then hand it back. A screener that stops at "price != 0"
writes off the best plays. Before you label anything paid, look for the exit door.

## The pattern

```
mintFree(uint256 shares, address receiver) payable   // requires msg.value == shares * price
claimFree(uint256[] ids)                             // after a lock period: principal back + reward
```

Pay `shares × price` as a **deposit**, wait out the lock (24 h in one verified case, 14 days in another), claim the
principal in full plus a base reward. Effectively free; the only cost is working capital sitting still and gas.

## Four numbers that decide whether the deposit comes back

1. **Solvency.** Compare the debt getters (`refundOwed`, `totalPending`, `pending`) with the contract's native
   balance. Equal = fully backed. A mismatch is the headline finding, not a footnote.
2. **Emission cap.** Sum base-per-share × shares across all halving stages + stage reserves + initial mint, and compare
   with `MAX_SUPPLY`. If the total can exceed the cap, `mint()` reverts at the cap and the claim that mints-before-refund
   reverts with it — user principal gets stuck.
3. **Claim wave.** From the first mint log + the lock constant, compute when the first big claim wave lands, and compare
   locked-but-unclaimed rewards against market cap. Several times market cap = scheduled sell pressure. That belongs in
   the verdict.
4. **Distribution and keys.** Sweep `Transfer` logs from the deploy block (chunked), label pair / locker / Gnosis Safe
   / escrow. A ~171-byte contract holding a large supply is a Safe (`masterCopy` `0xa619486e`, `getOwners` `0xa0e67e2b`,
   `getThreshold` `0xe75235b8`). If owner, pauser and treasury are the same EOA, write "one entity".

## Probe checklist before depositing

* simulate the gate in both polarities (eligible wallet vs a wallet without an Agent ID);
* `receive()` exists? funds that arrive by plain transfer are unrecoverable otherwise;
* `pause()` / `setPaused()` present → the claim can be frozen by the owner at will;
* check `shares` limits (`maxPerWallet`, `totalShares`) against what the UI offers;
* confirm the refund function is permissionless for the depositor and not owner-gated.

## Reporting rule

Never write "paid, skip" from the value alone, and never write "free" without the refund path. The honest label is
**"deposit, refundable after N hours, backed/unbacked"** plus the solvency number.
