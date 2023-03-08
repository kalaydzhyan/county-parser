#!/bin/bash
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
for i in {0..5}; do $SCRIPT_DIR/fetcher_tomgreen.py -begin_id=$((i*20000)) -end_id=$(( (i+1)*20000)) & done
