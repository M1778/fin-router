#!/bin/sh
# Unit tests + real-HTTP smoke test. Needs finc on PATH (or FINC set)
# and a zhttp checkout (FIN_ZHTTP, default: the fin-dev workspace sibling).
set -e
FINC="${FINC:-finc}"
FIN_ZHTTP="${FIN_ZHTTP:-$HOME/workspace/fin-dev/builder-1/zhttp/src}"
cd "$(dirname "$0")/.."
"$FINC" -I src tests/test_router.fin -o test_router
./test_router
FIN_ZHTTP="$FIN_ZHTTP" python3 tests/smoke.py
