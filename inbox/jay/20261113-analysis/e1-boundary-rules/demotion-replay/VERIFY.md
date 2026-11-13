# 경계 내림 도구 검증
> 분류: A/평가
> 작성: analyst-lx · 2026-11-14 02:22
> 근거: 원장 a76e783d · 실제 m250/m500/m750 · CPU 시험 로그
> 요지: 전체225시험 통과·7개 잘못된 변형 검출·전진0.1 하락0.134729 DEMOTE 재현
> 상태: 확인됨 · PR 검토 요청용

원자료 재생은 [KNOWN-INPUTS.md](KNOWN-INPUTS.md). m500은7칸, m750은9칸 DEMOTE다. 지도별 원값·문턱·최고회차는 각 하위 DEMOTE.md에 있다.

| 잘못된 변형 | 실패한 시험 수 | 결과 |
|---|---|---|
| fwd01_threshold | 2 | 검출 |
| both_maps_must_cross | 36 | 검출 |
| one_map_direction | 2 | 검출 |
| only_previous_best | 2 | 검출 |
| yaw_best_maximum | 13 | 검출 |
| exclusive_threshold | 19 | 검출 |
| ignore_history_errors | 1 | 검출 |

별도 반례: 체크포인트·계획·시드999·P1 해시 불일치, 빠진 과거 경계는 HOLD. 경로 별칭은 같은 파일이면 허용. 학습 폴더와 고정 코드 사본 아래 출력은 거절한다.

새 기능은 판단용18칸과 기존 지도 끔 생존21칸만 읽는다. 구간을 바꾸거나 보상을 적용하는 함수는 없다.

재현 명령:

```bash
CUDA_VISIBLE_DEVICES='' PYTHONDONTWRITEBYTECODE=1 /home/jay/miniforge3/envs/isaac311/bin/python -B -m pytest inbox/jay/20261113-analysis/e1-boundary-rules -q -p no:cacheprovider --basetemp=/home/jay/mai/tmp/analyst/e1-demote-recheck
CUDA_VISIBLE_DEVICES='' PYTHONDONTWRITEBYTECODE=1 /home/jay/miniforge3/envs/isaac311/bin/python -B inbox/jay/20261113-analysis/e1-boundary-rules/mutate_demote.py --out /home/jay/mai/tmp/analyst/e1-demote-mutations-recheck
```

미확인: 새 재출발의 m250은 아직 없으므로 이 PR에서 새 정책의 성과를 주장하지 않는다. 문턱은 실측 폭을 올려 고정한 운영 규칙이며 유의성 검정이나 원인 증명이 아니다.
