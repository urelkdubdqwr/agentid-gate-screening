# 11 — Chain-first discovery (find the drop before the tweet)

News feeds are slower than farmers. Free slots die in minutes-to-hours; the announcement arrives after. The fix is not
more feeds — it is moving the source of truth onto the chain.

## 1. New contracts that mention the Agent ID registry

Every gated contract has to store or pass the registry address, so it appears as a PUSH20 constant in the runtime code:

* `60b9262456de011f7d15a54cdd8c48baaa8b022f` — the `.ai` Agent ID registry,
* plus any second registry an ecosystem uses.

Scan the newest blocks for contract creations and check the code for that marker:

```text
for each new block:
  eth_getBlockByNumber(block, true)          -> txs with to == null
  eth_getTransactionReceipt(tx)              -> contractAddress
  eth_getCode(contractAddress)               -> contains registry marker?
```

Speed matters: 200 blocks serially is ~100 s, with a 16-worker pool ~9 s. A radar that runs when you get suspicious
is useless — **schedule it** (every 2–5 minutes) and keep a state file so it reports each contract once.

## 2. Burst-mint detection (the drop is already live)

Mints are `Transfer(0x0 → *)` for ERC-721 and `TransferSingle` (`topics[2] == 0x0…0`) for ERC-1155. A contract that
suddenly receives ≥25 mints in an hour is a live drop, announced or not.

```text
eth_getLogs {fromBlock, toBlock, topics:[Transfer, 0x000…0]}
group by contract -> count per contract in the window -> rank
```

Requirements that bite:

* you need an RPC that serves `eth_getLogs` **without** an address filter; public endpoints that answer `-32701` or
  "limit exceeded" cannot do this;
* keep ranges ≤ ~2 000 blocks, or 5 000 if the provider tolerates it — chunk and dedupe `(txHash, logIndex)`;
* BNB Chain blocks are ~0.45 s, so a day is ~192 000 blocks. Measure, do not memorise.

## 3. Judge free-ness from the chain, per wallet

For each candidate: `balanceOf(you) == 0`, price views (`price()`, `cost()`, `mintPrice()`, `PRICE()`,
`costFor(qty)`), then `eth_estimateGas` of the mint selector with `value = 0`. Pass = free for that quantity, today.

Simulate **per quantity**. A very common pattern is free at `qty = 1` and reverting at `qty = 5`
(`0xcd1c8867`, `0x788a686f` in the wild): that is a one-per-wallet free slot, not a paid contract.

To do that across every live launch at once instead of one contract at a time:
`python3 scripts/sweep.py --wallet 0xYourWallet --free-only` — it probes each radar contract with
`estimateGas(mint …, value = 0)` and prints who passes. Run the same sweep twice with two different wallets: a
contract that passes for a wallet holding **no** Agent ID is not gate-enforced at all (open free mint, a different
finding from a gated one).

## 4. Closed means closed — report it as a fact

`freeClaimed == MAX_FREE_SHARES`, `freeLeft() == 0`, `freeMinted >= FREE_SUPPLY` → the free pool is gone, and paying
does not "unlock" it. Report the counter, the block of the last fill, and move on. Never turn a closed free tier into
a paid mint on your own initiative.

## 5. Watcher design that survives unattended

* state file: `{contract: {reported_at, free_open, free_minted}}`, re-report nothing inside 6 h;
* JSON output for machines, text card for humans, and **nothing at all when there is nothing new**;
* one lock file so two overlapping ticks cannot double-mint;
* a `--dry` mode that only simulates, so the first run on a new box cannot spend anything;
* `status == minted` in the state file → the tick exits silently forever after.

`scripts/radar.py` is the feed-based half of this; the burst scanner is the chain half. Run both.
