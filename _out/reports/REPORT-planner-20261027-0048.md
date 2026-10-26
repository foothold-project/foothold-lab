> 분류: 보고 · planner → lead (orchestration task_3d77d131c969)
> 작성: planner (Claude Fable 5.1) · 2026-10-27 00:48
> 근거: `impl-turncases/logs/sb10_eval/m1500/walk_turn_summary.json` + `turn16_walk_{eval_gt,probe_prop_only}/arrays_walk_turn_{left,right}.npz`(sonnet-code X27g 00:36, 네 판 rc 0, 저장본 sha 4d987818 · 코드 07fc5e73) · `judge_gate.THRESHOLDS` walk_* · `turn_probe_plan.PROTOCOLS` · planner `inbox/jay/20261026-experiments/a5_baseline.py`(npz 독립 재계산)
> 요지: A5 걸으며 돌기 부모 기준선을 json 에서 생성기로 읽어 EX-35 카드 v0.8 · JUDGE-SPEC v0.12 · RULES-HUB 10.1 에 채웠다. **막음 1 닫힘.** 사실 하나: 성공선 다섯 성분 중 넷은 부모가 이미 통과하고 전진 적분 3.2 m 만 좌 미달. 막음 2 는 lead 가 쓸 A11 판독표(카드 §4b.4) 로.
> 상태: 커밋 전 초안 → 커밋 뒤 이 줄 갱신 없음(커밋 해시는 #557 · worker_done 에)

## 1. 막음

| 번호 | 내용 | 상태 | 근거 |
|---|---|---|---|
| 막음 1 | A5 걸으며 돌기 m1500 기준선 미측 | **닫힘** | 네 판(좌 · 우 × 켬 · 가림) rc 0, planner 가 npz 에서 Q · C · 전진 적분을 독립 식으로 다시 재어 json 과 ≤ 1e-6 · 정수(kept · 끝 생존 · 반대) 0 차이. eval_pred 모드는 미측(기록만, 판정 하한 없음) |
| 막음 2 | A11 영상 칸은 연장 전 증거 | **lead 판독** | 카드 §4b.4 판독표(머리 여섯 칸 + 기준 문장 ①~⑤ 표). 「있음」 하나면 멈춤, 전부 「없음」 + 머리 칸 완비면 7a |

## 2. A5 기준선 (생성기 출력 그대로)

| 모드 · 경우 | Q | C | kept / 끝 생존 | 반대 | 전진 적분 m (성공선 3.200) | 성공선 성분 Q · C · kept · 반대 · 전진 | 유지 하한 Q ≥ / C ≤ / 적분 ≥ `[가정]` |
|---|---|---|---|---|---|---|---|
| 켬 좌 (`walk_turn_left`) | 0.4544 | 0.215 | 16 / 16 | 0 | 3.006 | 통과 · 통과 · 통과 · 통과 · **미달** | 0.254 / 0.465 / 2.705 |
| 켬 우 (`walk_turn_right`) | 0.4460 | 0.092 | 16 / 16 | 0 | 4.289 | 통과 · 통과 · 통과 · 통과 · 통과 | 0.246 / 0.342 / 3.860 |
| 가림 좌 (`walk_turn_left`) | 0.4487 | 0.172 | 16 / 16 | 0 | 3.065 | 통과 · 통과 · 통과 · 통과 · **미달** | 0.249 / 0.422 / 2.759 |
| 가림 우 (`walk_turn_right`) | 0.4366 | 0.077 | 16 / 16 | 0 | 4.369 | 통과 · 통과 · 통과 · 통과 · 통과 | 0.237 / 0.327 / 3.932 |

- 성공선(JUDGE-SPEC 4.4 = `judge_gate.THRESHOLDS`): Q ≥ 0.25 · C ≤ 0.6 · kept ≥ 14 · 반대 0 · 전진 적분 ≥ 0.8 × 0.5 × 8 s = 3.200 m.
- **사실(해석 없음)**: Q · C · kept · 반대 네 성분은 부모가 네 판 모두 통과. 전진 적분은 우 통과(4.289 · 4.369 m), **좌 미달**(3.006 · 3.065 m). 좌 · 우 차이는 적기만 한다(lead 00:3x).
- 답 아는 입력(JUDGE-SPEC 6.8.2): 부모 묶음을 `_success_walk` 에 넣으면 `success_walk_vx` 가 (eval_gt, walk_turn_left) · (probe_prop_only, walk_turn_left) 둘만 나와야 한다.
- 유지 하한 `[가정: A3 식 차용]`: Q ≥ 기준 − 0.20 · C ≤ 기준 + 0.25 · kept ≥ 14 · 적분 ≥ 기준 × 0.90(표 마지막 열). 추세 「개선」 폭 0.115 는 A3 빌림(가정).

## 3. 바뀐 파일

| 파일 | 판 | 바뀐 곳 |
|---|---|---|
| `inbox/jay/20261021-experiments/EXP-EX35-SB10-cmd-S2a.md` | v0.8 | 상태 줄 · §3 walk_turn 두 행 · §4b.1 A5 기준선 · 하한 칸 · §4b.2 기대 시각 · §4b.3 2 행 · **§4b.4 A11 판독표(새)** · §5 조건 5 상태 · §8 lead 가 정할 것 (6) · 판 표 |
| `inbox/jay/20261026-experiments/JUDGE-SPEC.md` | v0.12 | 상태 줄 · 4.4 주석 부모 실측 · **6.8.2(새)** 기준선 표 · 성공선 성분 통과표 · 답 아는 입력 · 판 표 |
| `inbox/jay/20261019-design/RULES-HUB.md` | v1.6 초안 | 10.1 A5 행 기준선 · 상태 칸(미측 → 실측) · 상태 줄 · 판 표. **lead 39d0af37 위에 다시 얹음(3-way 충돌 0)** |
| `inbox/jay/20261026-experiments/a5_baseline.py` · `figs/ex35-parent-baseline/a5_baseline.json` | 새 | 생성기 · 산출 json(원자료 경로 · 상수 · 행) |

## 4. lead 가 정할 것

1. (카드 §8 (6)) 성공선 다섯 성분 중 넷을 부모가 이미 넘으므로 m2000 「다음 단계」 판정은 사실상 좌 전진 적분 한 성분에 달린다. 숫자는 결과 전 고정이라 그대로 두었다. 「부모가 이미 넘는 성분」 을 기록만 할지, 기준 대비 개선을 요구할지는 lead · 팀장.
2. RULES-HUB cherry-pick 은 이번 커밋(39d0af37 위) 으로. 카드 · JUDGE-SPEC 은 fable-25a 에만 있다.
3. A11 판독표(§4b.4) 의 형식이 쓰기 편한지. 파일 이름 `ex35_window_m<N>_A11.md` 는 제안.

## 5. 재지 않은 것

- walk_turn 재측정 폭(한 번 잼) · eval_pred 모드 walk_turn · 좌 · 우 전진 적분 차의 원인(해석 금지 지시) · 코드 `_success_walk` 를 부모 묶음에 실제로 돌린 결과(기댓값만 적음, 구현 시험은 sonnet-code).
- GPU · 학습 · 코드 수정 · push 없음. EX-35 cuda:0 진행 중(손대지 않음).
