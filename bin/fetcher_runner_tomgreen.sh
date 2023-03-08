#!/bin/bash
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
for i in {0..120}; do $SCRIPT_DIR/fetcher_taylor.py -begin_id=$((i*1000)) -end_id=$(( (i+1)*1000)) & done
