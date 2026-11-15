#!/usr/bin/env bash
# S1-b 를 S1a-v1.1 blind 의 model_5999.pt 에서 이어 시작한다 (lead 10/21). usage: run_s1b_from_v11.sh <cuda:N> [추가 인자...]
export S1B_FROM_EXPERIMENT=foothold_s1a_v11 S1B_FROM_SUFFIX=s1a_v11_blind
exec bash "$(dirname "${BASH_SOURCE[0]}")/run_s1b.sh" "$@"
