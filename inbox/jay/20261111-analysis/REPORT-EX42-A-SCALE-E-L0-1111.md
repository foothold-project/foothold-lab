# EX-42 A Go2 축척 생성기 · E L0 정정

> 분류: A/지형씬제작 · 구현 검증
> 작성: verifier-lx · 2026-11-11
> 근거: lead-lx 01:23 의뢰 · D158 · CURRICULUM-GATES v0.16 · DESIGN-EX42-TERRAIN-draft §4.2
> 요지: EX-42 전용 start_go2_v2 생성 API 추가, 기존 START 절대판 두 파일 보존, E L0 정본 일치
> 상태: CPU 확인됨 · Kit/GPU 미실행 · 측정기 호출부 연결과 Kit 실측은 통합 뒤 별도

## 범위와 정본

기준 `origin/lead/linux-integration-1109` **75293ad567bbdaef63e32b163c95b3fd480b14b8**. 작업 가지 `verifier/ex42-terrain-a-scale-1111`, 작업 자리 `/home/jay/mai/wt/foothold-lab/verifier-lx`. 기존 #555 의뢰 기록으로 수행했다. 공유 본 사본은 수정하지 않았다.

정본은 fable-25a **368d03e2061b505fc72ad73e9cd2527a766e7738**의 다음 줄을 직접 읽었다. 기준 코드 가지의 오래된 문서로 덮어쓰지 않았다.

| 근거 | 소비 |
|---|---|
| `inbox/jay/20261102-ex42/DESIGN-EX42-TERRAIN-draft.md:114,174~186`, D158 | x × 1.108 · y × 0.885 · z 유지. 타일 길이 전체를 늘리지 않고 돌·빔·틈 치수에 적용 |
| `inbox/jay/20261026-experiments/CURRICULUM-GATES.md:277,595`, v0.16 | 평균대 폭 L0 0.531 → L9 0.09, 선형 L/9. 나머지 축척 치수 그대로 |
| 같은 문서 `:294` | E 경사 0.40 → 0.70 · 계단 단 0.23 → 0.30 |

정본 표의 반올림 표시를 생성기 상수로 다시 반올림하지 않았다. 다음은 **계산값**이며 CPU 상자 좌표에서도 대조했다.

| 종류·축 | L0 | L9 |
|---|---:|---:|
| 징검돌 길이 x | 0.554 | 0.2216 |
| 징검돌 폭 y | 0.4425 | 0.177 |
| 징검돌 틈 x | 0.1939 | 0.277 |
| 징검돌 틈 y | 0.0885 | 0.154875 |
| 평균대 폭 y | 0.531 | 0.09 |
| 디딤 빔 두께 x | 0.554 | 0.1662 |
| 디딤 빔 틈 x | 0.1108 | 0.3047 |
| gaps 틈 x | 0.1108 | 0.7756 |
| E 경사 비 | 0.40 | 0.70 |
| E 계단 단 m | 0.23 | 0.30 |

깊이 U[0.2,0.7] m, 높이 ±0.05 m, high r=L/9, low r=0, 타일 8×8 m와 가운데 8×4 m 띠는 보존했다. 평균대 L5 폭은 0.286 m. 돌은 직사각형으로 생성하며 타일 안 개수를 새 치수로 다시 계산한다. low 지지 패치 수(L0/L9)는 CPU 실측 56/144, 디딤 빔은 9/13이다. 원본 지지면 수를 축척판의 수로 복사하지 않는다.

## 코드와 연결 계약

- 새 `foothold_s2/terrains/start_go2_v2.py`: `generate(kind, level, rng, randomness=None)`, `build_tile(kind, difficulty)`, `sparse_subterrains(proportions=None)`. Isaac import는 cfg를 만들 때만 한다. cfg에 `preset_id="start_go2_v2"`와 새 callback 경로가 들어가 절대판 캐시와 구분된다. 별도 `SIDE_TABLE`이 캐시 복원도 축척판으로 수행한다.
- `foothold_s2/terrains/ex42.py`: E의 네 L0 끝값만 변경. L9·폭·platform·border 등은 보존했다.
- 새 `foothold_s2/tests/test_start_go2_v2_cpu.py`: 정본 수치와 출처 줄을 직접 적고 상자 좌표·CPU trimesh bounds·캐시 복원·cfg 전달·기존 파일 SHA를 검사한다. Isaac cfg 껍질 시험은 대역이며 실제 Kit 통과가 아니다.

**EX-42 소비자는 명시적으로 새 모듈을 import해야 한다.** 현재 기준 가지에는 sonnet의 `ex42_kit_measure.py`가 아직 없다. 다른 작업 사본은 수정하지 않았다. sonnet의 A 분기에서 다음 import로 교체하고, EX-42 메시 판의 A 분기에도 같은 모듈을 사용해야 한다.

```python
from foothold_s2.terrains.start_go2_v2 import sparse_subterrains
# continuous_subterrains()는 기존대로, A의 sparse 6종만 새 API 사용
```

EX-41·옛 평가 경로의 import는 바꾸지 않는다. 복원 지도 평가용 `start_go2_eval_*` 추가 구현은 이 의뢰 범위 밖이며 이 PR이 그것을 구현했다고 주장하지 않는다.

### 축척판에서만 필요한 깃발 보정

실측 반례: `stepping_beams`, difficulty 0.95의 기존 5 cm 높이장 검색은 깃발 `(3.9,4.0)`을 실제 발판 밖에 둔다. 새 preset에서만 그 후보를 가장 가까운 실제 지지 사각형에 투영한다. 별도 물리 여유값은 만들지 않았다. 기존 절대판 스냅 함수·반환값은 그대로다. 6종 × L0/L5/L9의 발판 위 깃발 검사를 통과했고 보정을 제거하면 같은 반례로 실패한다.

## CPU 검증과 경계

환경 `/home/jay/miniforge3/envs/isaac311/bin/python`, `CUDA_VISIBLE_DEVICES=''`, `PYTHONDONTWRITEBYTECODE=1`, `-p no:cacheprovider`, 임시 경로 `/home/jay/mai/tmp/verifier-lx/`.

| 확인 | 결과 |
|---|---|
| 변경 전 기존 sparse·E 시험 | **22 passed** |
| 새 시험 변경 전 | E L0 **1 failed**, 새 모듈 미존재 **20 errors**, 절대판 SHA **1 passed** |
| 새 시험 + 기존 sparse·E | **48 passed** (새 시험 26개) |
| 관련 8개 파일 회귀 | **147 passed, 1 failed** |
| 위 실패 기준 커밋 재생 | **1 failed** 동일 재현. `test_kind_stats.py`의 `torch.manual_seed(42)` 문자열 금지와 기존 `eval_map_modes.py`의 해당 호출이 충돌. 시험과 소비 파일 3개가 기준 git blob과 바이트 동일함을 확인. 이번 변경으로 생긴 실패가 아니며 범위 밖이라 고치지 않음 |
| 고침 제거 돌연변이 5개 | 모두 pytest rc1: x 축척 제거 · 돌 y에 x값 사용 · 평균대 옛 폭 · E L0 옛값 · 깃발 보정 제거 |
| 기존 START 두 파일 | Linux 파일 SHA 및 git diff로 바이트 불변 |
| Kit·실제 TerrainGenerator·GPU | **미실행·미확인**. CPU trimesh callback까지 확인 |

원출력: `/home/jay/mai/tmp/verifier-lx/terrain-final.log`, `terrain-baseline-fail.log`, `terrain-mutant-*.log`; 재현 스크립트 `terrain_mutants.py`. 새 시험 파일에 정본 수치가 남고 임시 자료에만 의존하지 않는다.

기존 파일 SHA256:

- `eval/start_sheet.py`: `15e830bda3fc5ed7f106074d415b30e6ca5334887a9f1b011d980ffce018d9ec`
- `terrains/sparse_terrains.py`: `5f296cf750609b83d99c46d6f730716d2f58532f436fae0dc3b776be7737b522`

**구현 범위 막음 0.** 새 A API를 측정기·EX-42 메시 판에 연결하지 않은 기존 호출은 여전히 절대판이므로, 이 보고만으로 통합 메시가 축척판이라고 확정할 수 없다. 연결·새 geometry SHA·실제 L9 메시 치수는 sonnet 통합 및 lead의 Kit 측정에서 확인할 대상이다. 기동 승인 보고가 아니다.
