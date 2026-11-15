> 분류: A/정책학습 · 평가 · ASTRA 의뢰 17g · 미경험 v5 (17e 고침) · 무작위화 판 3 (17d 고침) 기동 검토
> 작성: 오흥재 (lead 세션 · Claude 작성) · 2026-10-14 00:44
> 근거: VERIFY-astra-17e.md · VERIFY-astra-17d.md · night-tools-20261013/uncr_v5/ (이번에 고정) · night-tools-20261013/rand_scenes/ (bdc5182f) · lead 재실행 (아래 2 절)
> 요지: 미경험 지형 회귀 진단 v5 와 무작위화 장면 판 3 을 GPU 1 에서 띄워도 되는지, 기동 순서가 맞는지 판정해 달라. 허용이면 v5 full 의 승인 파일을 같이 써 달라
> 상태: 의뢰 (17h 다음 차례)

# ASTRA 17g · 미경험 v5 · 무작위화 판 3 기동 검토

## 답하는 자세 (팀장 지시 · 모든 사항에 적용)

비판적이면서도 냉정하고, 현실적이면서도 아주 전문성이 높은, 이 분야를 평생 탐구한 전문가로서 답해 주십시오. lead 와 하위 작업의 보고를 맞다고 가정하지 마십시오.

## 1. 대상 (해시 고정)

**A. 미경험 지형 회귀 진단 v5** (`night-tools-20261013/uncr_v5/SHA256SUMS.txt`). 원본 위치는 `C:/isaac/ext/go2_rl_robotlab/_eval/` 이고 사본과 바이트가 같습니다.

| 파일 | sha256 앞 12 자 | 내용 |
|---|---|---|
| `unseen_driver_cmdr_v5.py` | df0cf1e0a1df | v5 실행기. 머리 주석에 17e §3.1 ~ §3.4 · §5 · §6 반영 내용 |
| `uncr_revalidate_v2.py` | 089574adfa10 | 재검사기 v2 (명령 계약 · 동결 · wrapper 등록) |
| `test_uncr_v5.py` · `mutate_uncr_v5.py` | 983d7b434634 · ff1ef3fdac09 | CPU 시험 · 변이 |
| `revalidate-20261014-004331.json` | 98322ffbf284 | lead 가 00:43 에 재검사기 v2 로 옛 루트 `out_uncr` 를 다시 잰 보고 |
| `manifest_v5-20261014-004332.json` | 4a000dea672b | lead 가 00:43 에 `--stages manifest` 로 뽑은 새 실행 manifest 와 승인 틀 |

**B. 무작위화 장면 판 3** (`night-tools-20261013/rand_scenes/SHA256SUMS.txt` · 커밋 bdc5182f). 00:44 에 `_eval/rand_scenes/` 원본 8 파일이 사본 해시와 같음을 다시 확인했습니다. 돌리는 법은 그 폴더 `README-rand-scenes.md` 0 절.

## 2. lead 가 다시 잰 것 (10/14 00:32 ~ 00:44)

| 항목 | 결과 |
|---|---|
| v5 시험 · `isaac311-moects` python (3.11.15 · numpy 1.26.0, 밤 스크립트와 같은 해석기) | 51/51 통과 · 실제 7 칸 모두 valid |
| v5 시험 · anaconda base python (3.13.9 · numpy 2.3.5) | **X01 FAIL**: 옛 23 실행 중 valid 8 · hold 15. 까닭은 「q_post 를 다시 돌리면 episodes.csv (일부는 cells.json) 바이트가 다름」. invalid 는 0 |
| v5 변이 | 38/38 잡힘 · 시험 뒤 대상 네 파일 해시 그대로 · 변이 사본 남지 않음 |
| 재검사기 v2 로 옛 루트 (00:43:31) | runs valid 23 · diag runs valid 21 · diag 칸 valid 7 · 묶음 해시 e55975172405… (17e 가 검토한 값과 같음) · frozen_ok True · 입력 253 |
| `--stages manifest` (00:43:32) | registered True · code manifest ac09c26492f5… · 새 실행 75 (reuse_partial no) |
| 무작위화 판 3 | lead 재실행 27/27 (bdc5182f 때) · 이번에는 해시만 다시 대조 |

## 3. lead 가 제안하는 기동 (GPU 1 · 한 번에 Isaac 하나)

GPU 0 은 CMD-R 1043 on 학습 중입니다 (05:40 무렵 끝 추정). GPU 1 은 화면용 GPU 이기도 하며 데스크톱 앱이 약 5.7 GB 를 쓰고 있어 여유는 약 10 GB 입니다. v5 의 기동 전 여유 기준은 6,144 MiB 입니다. 해석기는 모두 `C:/Users/AI-WS01/anaconda3/envs/isaac311-moects/python.exe` 로 고정합니다.

1. **무작위화 smoke:** `rand_driver.py --stop_after_smoke` (README 0 절). 스틸과 `manifest.json` smoke 칸을 lead 가 보고 (영상은 전 프레임), 이상 없으면 네 판 (교란 없음 · 밀기 · 낮은 마찰 · 높은 마찰) 을 **한 실행으로** 돌립니다 (짝 비교 문구가 한 실행 안에서만 나오므로).
2. **미경험 v5 full:** `unseen_driver_cmdr_v5.py --stages full,post --reval _eval/out_uncr_reval/20261014-004331/revalidate.json --approval <승인 파일> --reuse_partial no --deadline <10/14 09:00 epoch>` · 새 실행 75 · 출력 `_eval/out_uncr_v5`.
3. 같은 시험지 (CE12) v2 짧은 기록은 CTS 대조 승인 뒤에 1 과 2 사이 빈 때에 넣습니다. 서로 겹쳐 띄우지 않습니다.

## 4. 물음

1. **v5 가 17e 의 지적을 막았나.** 17e §3.1 ~ §3.4 · §5 · §6 각각에 대해, 코드가 막는지와 시험 · 변이가 그 지적을 실제로 잡는지 (구현을 복제한 시험이 아닌지) 판정해 주십시오.
2. **해석기 의존.** 재검사가 python · numpy 판에 따라 바이트가 달라져 hold 로 떨어집니다. 지금은 안전한 쪽 (hold) 으로 막히지만, 이유 문구가 「q_post 가 다른 바이트」 라서 원인을 알기 어렵습니다. 해석기와 numpy 판을 기록 · 대조하는 관문을 full 전에 더해야 하는지, 아니면 「밤 실행은 isaac311-moects 고정」 으로 충분한지.
3. **무작위화 판 3 이 17d 의 지적 (2.1 ~ 2.4 · 3 · 5) 을 막았나.**
4. **기동 순서와 GPU 1 공유.** 3 절 순서가 맞나. 화면용 GPU 에서 두 일을 이어 돌릴 때의 위험 (여유 메모리 · 렌더 · 시간) 과 빠진 멈춤 조건.
5. **v5 full 승인 여부.** 75 실행 · reuse_partial no 를 승인하는지. 「1042 한 학습 시드의 조건부 회귀 자료」 라는 해석 범위 문구가 결과 보고에 맞게 남는지.

## 결과

- `inbox/jay/20261012-arch-discussion/VERIFY-astra-17g.md` 한 파일. 첫 줄은 한 문장 판정 (그대로 기동 · 고쳐서 기동 · 보류). A 와 B 를 따로 판정해도 됩니다.
- **v5 full 을 승인할 때만** `inbox/jay/20261012-arch-discussion/night-tools-20261013/uncr_v5/approval-astra-17g.json` 을 써 주십시오. `manifest_v5-20261014-004332.json` 의 `approval_template` 칸을 채운 것으로, `decision` 은 `approve`, `by` 는 `ASTRA 17g`, `reval_sha256` 은 `98322ffbf284fa8d2d1e1a36360839af894ff66b8513dbc74aae8aa2f6c44954` (위 보고 파일 전체 해시) 를 넣고 나머지 값은 manifest 와 같게 합니다. 승인하지 않으면 이 파일을 만들지 마십시오.
- 표기: 확인됨 · 추정 · 미확인. 코드 수정 · GPU · Isaac · 학습 · 커밋은 하지 마십시오. `_eval/out*` · `handover_*` · `handover-1635` · `slot/` 에는 쓰지 마십시오. em dash 를 쓰지 마십시오.
