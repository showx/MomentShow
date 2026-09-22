#!/bin/bash
cd "$(dirname "$0")"
if [ -f .venv/bin/activate ]; then
  source .venv/bin/activate
fi
exec python3 -m momentshow
