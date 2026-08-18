#!/usr/bin/env bash
# Reproduce every figure in the README. fetch.py caches, so re-runs hit disk not network.
set -e
cd "$(dirname "$0")/src"
python fetch.py
python build.py
python roles.py
python concentration.py
python network.py
python mirror.py
