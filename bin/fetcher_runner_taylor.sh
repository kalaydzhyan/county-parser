#!/bin/bash
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
for i in {1..10}; do $SCRIPT_DIR/fetcher_taylor.py -begin_id=$((i*10000)) -end_id=$(( (i+1)*10000)) & done

