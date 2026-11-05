# 05 — Execute and verify

Screening ends with a transaction. Three signing paths below — pick one. None of them lives in this repo: the
scripts here are read-only, on purpose, so a copied repo can never spend from your wallet.

---

## The calldata you need

```bash
# mint(uint256 qty) = 0xa0712d68 + uint256 as 64 hex chars
QTY=1; printf '0xa0712d68%064x\n' "$QTY"
# amount is wei, not BNB: 0.0005 BNB = 500000000000000
```

Builder without any library:

```bash
TO=0xMintContract
DATA=$(printf '0xa0712d68%064x' 1)
VALUE=0
```

## Path A — `cast` (Foundry)

```bash
cast send "$TO" "$DATA" --value "$VALUE" --gas-limit 300000 \
  --rpc-url https://bsc-dataseed.binance.org \
  --private-key "$(cat ~/.keys/mint.key)" || true

cast receipt <txHash> status gasUsed          # want status 1
```

## Path B — a small script (Python + web3)

```python
# pip install web3
from web3 import Web3

w3 = Web3(Web3.HTTPProvider("https://bsc-dataseed.binance.org"))
acct = w3.eth.account.from_key(open("/home/you/.keys/mint.key").read().strip())

tx = {
    "to": "0xMintContract",
    "value": 0,
    "data": "0xa0712d68" + (1).to_bytes(32, "big").hex(),
    "gas": 300_000,
    "gasPrice": w3.eth.gas_price,
    "nonce": w3.eth.get_transaction_count(acct.address),
    "chainId": 56,
}
signed = acct.sign_transaction(tx)
print(w3.eth.send_raw_transaction(signed.raw_transaction).hex())
```

Key hygiene: file mode `0600`, never in shell history, never in a repo, never in a chat message.

## Path C — agent/MPC wallet CLI (optional)

If your wallet is an MPC agent wallet — e.g. the Binance Agentic Wallet CLI (`@binance/agentic-wallet`, binary
`baw`), which is also the wallet that owns the `.ai` handle — signing is preview → execute:

```bash
# 1) dry run: the backend simulates and returns a requestId + balanceChanges
baw contract-call preview \
  --binanceChainId 56 \
  --from 0xYourAgentWallet \
  --to   0xMintContract \
  --value 0 \
  --inputData "$DATA" \
  --gasLimit 300000 --json

# 2) read simulationResult.balanceChanges — count the tokens you are about to receive
# 3) execute the previewed request
baw contract-call execute --requestId <requestId> --json   # -> {"status":"BROADCASTED","txHash":"0x…"}
```

Notes that save hours (true for any simulator, not just this one):

* `--value` is **wei**. `0.0005 BNB` = `500000000000000`.
* the gas limit is a **cap**. An undersized cap fails at preview (cheap) instead of on-chain (expensive). The
  5-per-wallet mints in `07-case-studies.md` land around **200–215k gas**.
* set the cap on `preview` only; `execute` has no gas flag.
* `BROADCASTED` is not success — poll the receipt.
* MPC wallets have no raw key to leak. That is the main reason to use one when an agent is doing the signing.

---

## Verification, always

```bash
# 1. receipt
curl -s $RPC_URL -H 'content-type: application/json' \
  -d '{"jsonrpc":"2.0","id":1,"method":"eth_getTransactionReceipt","params":["0xTX"]}' | jq '{status,blockNumber,gasUsed}'

# 2. token balance delta (ERC-721 balanceOf / ERC-1155 balanceOf)
# 3. for ERC-1155 ids: read TransferSingle logs out of the receipt, do NOT guess ids 0..n
```

A mint is confirmed only when **both** are true:

1. `receipt.status == 1`
2. the balance/log actually moved (not just "no error")

Report format that prevents self-deception:

```
contract 0x…   tx 0x…   status 1   gasUsed 206458   balanceOf 5 (was 0)   cost 0.000018 BNB
```

If any field is missing, the mint is **not** confirmed — say so instead of assuming.

## Calldata cheat sheet

| Function | Selector | Args |
| --- | --- | --- |
| `mint(uint256)` | `0xa0712d68` | qty |
| `mint()` | `0x1249c58b` | — |
| `freeMint(uint256)` | `0x7c928fe9` | qty |
| `claim()` | `0x4e71d92d` | — |
| `claimFree()` | `0xf366afc9` | — |
| `mintFree(uint256,address)` | `0x0db5ae5a` | shares, receiver |
| `openFree()` | `0x1644fa8e` | — |
| `commitFreeMint()` | `0x74d04cfc` | — (then `reveal(address)` `0xc392cf41`) |
| `reveal(uint256)` | `0xc2ca0ac5` | id or count |
