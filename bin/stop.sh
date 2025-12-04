#!/usr/bin/env bash
cd "$(dirname "$(readlink -f "$0")")" &> /dev/null && source utils.sh || exit
pids=$(get_pids)
if [[ -n $pids ]]; then
  kill -9 $pids && info "server stopped success !"
else
  warn "server not found"
fi
