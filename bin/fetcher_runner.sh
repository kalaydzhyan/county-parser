for i in {1..10}; do ./fetcher_taylor.py -begin_id=$((i*10000)) -end_id=$(( (i+1)*10000)) &>/dev/null & done
