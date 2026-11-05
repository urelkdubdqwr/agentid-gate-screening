#!/usr/bin/env bash
# smoke.sh — verify every script in this repo actually runs (read-only).
#
#   ./smoke.sh                  # checks that don't need a wallet
#   ./smoke.sh 0xYourWallet     # also checks your Agent ID status + free-tier simulation
#
# Nothing is signed. Only eth_call / eth_estimateGas / public HTTP APIs are used.

set -u
cd "$(dirname "$0")"

WALLET="${1:-}"
CONTRACT="0xc9f30f3d8e8858c3360eb96843a8de9138e27ec4"   # an agent-gated contract on BSC (Cipher Agent)

fail=0
run() {
  echo "── $*"
  if "$@" > /tmp/agentid-smoke.out 2>&1; then
    head -n 8 /tmp/agentid-smoke.out
  else
    rc=$?
    # gate_check / free_tier legitimately exit 1 on a negative verdict
    if [ "$rc" -eq 1 ]; then
      head -n 8 /tmp/agentid-smoke.out
      echo "   (exit 1 = negative verdict, script ran fine)"
    else
      echo "   FAILED rc=$rc"
      cat /tmp/agentid-smoke.out
      fail=1
    fi
  fi
  echo
}

run python3 scripts/recon.py "$CONTRACT"
run python3 scripts/safety.py "$CONTRACT"
run python3 scripts/radar.py --hours 1 --no-state --quiet-empty

if [ -n "$WALLET" ]; then
  run python3 scripts/gate_check.py --wallet "$WALLET"
  run python3 scripts/free_tier.py --wallet "$WALLET" --qty 1 "$CONTRACT"
else
  echo "── wallet checks skipped (pass your address as \$1 to include them)"
  echo
fi

if [ "$fail" -ne 0 ]; then
  echo "SMOKE: FAIL"
  exit 1
fi
echo "SMOKE: OK"
