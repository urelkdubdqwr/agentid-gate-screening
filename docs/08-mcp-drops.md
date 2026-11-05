# 08 — MCP drops: sign in, claim, wait for the window, mint

Some Agent ID drops do not expose a public mint to everyone. They run an **MCP server** (Model Context Protocol) or a
private API where the flow is: wallet sign-in → claim/order → a build or cooldown window → server-signed ticket →
mint transaction. The contract still mints, but the *right* to call it comes from the backend.

## 1. Sign in with EIP-712, from the wallet that owns the Agent ID

```
POST /auth/challenge   {"wallet": "0x…"}   -> typedData (EIP-712)
POST /auth/verify      {"wallet", "challenge", "signature"} -> Bearer token
```

Checks before you sign anything:

1. `typedData.domain.name` and `chainId` are the project's, not a generic wallet-drain domain.
2. `message.wallet` == your wallet, `message.audience` == the site, `expiresAt` in the future *and* short.
3. Sign `eth_signTypedData_v4` over that exact JSON — never `personal_sign` over a hand-rolled string, and never a
   `permit`/`setApprovalForAll` typed data ("sign in" never needs token approval).

Signature detail that costs an hour: MPC wallets return a 64-byte `r||s` with a separate recovery id. Most backends
want the 65-byte form, so append `1b`/`1c` derived from `signatureRecovery` (`"00"` → `1b`, `"01"` → `1c`).

Tokens are bound to the **exit IP**. If the token dies right after a successful read, the IP rotated — re-auth rather
than retry, and pin one stable egress for the whole session.

## 2. Drive MCP with plain HTTP

No client library needed. `initialize`, then `tools/call`:

```bash
curl -s https://app.example/mcp -H 'content-type: application/json' \
  -H 'accept: application/json, text/event-stream' \
  -H "authorization: Bearer $TOKEN" \
  -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","clientInfo":{"name":"cli","version":"1"}}}'

curl -s https://app.example/mcp -H 'content-type: application/json' \
  -H 'accept: application/json, text/event-stream' \
  -H "authorization: Bearer $TOKEN" \
  -d '{"jsonrpc":"2.0","id":2,"method":"tools/call","params":{"name":"claim","arguments":{...}}}'
```

Parse **both** shapes: plain JSON and SSE (`data: {...}` lines). Read `tools/list` once — the public records
(`protocol_info`, `list_cities`, …) usually need no token and already contain the contract addresses, the pause flag
and the supply picture.

## 3. Claim, then respect the window

Save from the claim reply: the order/character id, the server's own status link, and the **deadline**. The window is
server-side; polling faster does not shorten it. Poll the status tool every 60–90 s.

Two different pauses exist and only one keeps your ticket alive:

* server `paused: true` — the claim tool refuses; nothing to do but wait.
* contract `EnforcedPause()` — the ticket is valid and the deadline is still ticking; fire the mint on a 30–60 s loop
  so the first block after unpause is yours.

## 4. Mint what the server hands you

The mint tool returns `{to, data, value}`. Assert before signing:

* `to` == the mint contract published in the protocol record,
* `value` == the quoted price (0 for free),
* `data` selector is a function the contract actually has (see `10-bytecode-abi-recovery.md`).

A refused simulation is the cheapest diagnostic you get: replay `{from, to, data, value}` as a raw `eth_call`, read the
4-byte selector out of the error `data`, and look it up. `EnforcedPause()` → keep firing. `NoAgentId()` → wrong wallet.

## 5. Failure modes that look like auth but are not

* Every `isError` mapped to `not_signed_in` → you re-auth against a project pause forever. Branch on the parsed
  `reason` field first; only the literal `not_signed_in` means auth loss.
* A fresh token is sometimes refused for a few seconds. Sleep ~15 s and retry once.
* A released character/order is not a loss: re-order with the same handle, then continue the loop.

## 6. Verify on-chain

`receipt.status == 1` + `balanceOf(you)` moved, or the contract's own ownership mapping. The app's "minted" screen is
not evidence; two-step contracts (commit → reveal) legitimately show nothing until the reveal lands.
