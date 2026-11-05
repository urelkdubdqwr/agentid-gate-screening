# 15 — Airdrop / Merkle claims

Half the Agent ID ecosystem pays out through a Merkle claim rather than a mint. The mechanics are simple; the failure
modes are all about *which* wallet is eligible.

## 1. Read the four constants before touching anything

```
merkleRoot()   claimed(address)   claimDeadline()   claimFee()
```

* root non-zero and known to you (published in the project repo / site JSON, usually `proofs.json`);
* `claimed(you) == false`;
* deadline in the future;
* fee — some claims charge a flat amount; know it before you press the button.

## 2. Eligibility is per address, not per person

`proofs.json` is almost always `{address: [proof…], amount: …}`. If your address is not a key in it, you are not in that
round — a different wallet you control may well be. Check every address you own before concluding "not eligible", and
check the address **case**: proof sets are usually keyed by lowercase.

## 3. Verify the proof off-chain first

Recompute `keccak256(abi.encodePacked(address, amount))` up the proof path and compare with `merkleRoot()`. A mismatch
means you are reading a proof for another contract/epoch — sending it reverts and costs gas.

## 4. Claim and verify

```bash
# claim(address, amount, proof[])
cast send 0xCLAIM "$(cast calldata 'claim(address,uint256,bytes32[])' 0xYOU 1000000000000000000 "[0x…,0x…]")" \
  --rpc-url https://bsc-dataseed.binance.org --private-key "$(cat ~/.keys/mint.key)"
cast call 0xTOKEN 'balanceOf(address)(uint256)' 0xYOU
cast call 0xCLAIM 'claimed(address)(bool)' 0xYOU
```

Success = `claimed(you) == true` **and** the token balance moved. A receipt with status 1 and no balance change
usually means the claim credited a different address (read the `Claimed` event).

## 5. Watch it, do not chase it

Claims are rarely first-come: the deadline is generous and the root does not change. The one exception is a claim that
also gates a mint (claim → allowlist). In that case the mint window is the deadline that matters, so claim early and
keep the receipt.

## 6. Common traps

* claiming with the wrong chain selected (same address, different deployment) — confirm `merkleRoot()` matches the
  published one on *that* chain;
* a claim contract that is a proxy: resolve the implementation before trusting a view (see `10`);
* "claim" buttons that actually call `stake()`/`deposit()` — read the calldata the page builds before signing;
* unclaimed dust left because a second epoch was published; re-check `proofs.json` for your address per epoch.
