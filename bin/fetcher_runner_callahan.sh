#!/bin/bash
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
for i in {0..9}; do $SCRIPT_DIR/fetcher_callahan.py -begin_id=$((i*2000)) -end_id=$(( (i+1)*2000)) & done
