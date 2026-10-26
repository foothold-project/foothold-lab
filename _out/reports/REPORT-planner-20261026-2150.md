# REPORT-planner 2026-10-26 21:50 · X26v · X26w 재대조 (고침 1 · 2 닫힘 확인)

> 분류: 대조 보고 (planner, 설계 반박 검토 · 21:15 보고의 후속)
> 작성: planner (Claude Fable 5.1) · 2026-10-26 21:50
> 근거: 사양 JUDGE-SPEC v0.8(60c4b89c) J-T5 · J-T10 · 5.2 의 3 · 구현 impl-integ(feature/judge-mapratio-integ-jay) 7639a97d(X26v) · afad7987(X26w, 21:43) 의 `git diff 58a4af15..afad7987` · 부모 저장본 폴더 `impl-sb/logs/rsl_rl/foothold_s2_sb/2026-10-26_01-17-47_sb-main/manifest.json`(내가 열어 봄) · 시험 `test_world_frame.py` · `test_terrain_mark.py` 를 내가 돌림(isaac311 python -m pytest, CPU, `-p no:cacheprovider`, 34 passed 2.87 s)
> 요지: **막음 0 · 고침 0 · 참고 4.** 21:15 보고의 고침 1(설정 · manifest 경로 없음) · 고침 2(표식 덮기 기록용 미전환) 는 두 커밋으로 닫혔다. 실행 인자 `--judge_world_frame` · `--judge_mask_new_task` 가 gym.make 앞에 커리큘럼 term params 에 박히고, manifest `modes` 에 `terrain_judge` · `parent_judge` · `start_checkpoint_judged_with` 가 남는다. 실제 부모 S-B10 m1500 manifest 에는 `terrain_judge` 가 없어 「옛 판정으로 학습됨」 문구가 나오는 것을 확인했다. 사양의 manifest 모양만 코드대로 v0.9 로 맞춘다.
> 상태: 읽기 + CPU 시험만 · GPU · 학습 · 코드 수정 없음 · reviewer(X26w) · verifier 결과는 미확인

## 1. 고침 1 (설정 경로 · manifest) 대조

| 사양(JUDGE-SPEC v0.8 J-T10) | 코드(afad7987) | 판정 |
|---|---|---|
| 설정 · 인자로 고를 수 있어야 함(함수 기본값만으로는 안 됨) | `train_start.py:38~39` · `train_sol23f_common.py:45~46` `--judge_world_frame on|off` · `--judge_mask_new_task on|off`(기본 None = 설정값 유지). `train_sb.py:10` 은 나머지 인자를 그대로 넘기므로 `run_sb.sh` 경로에서도 받는다 | 맞음 |
| S1 `CurrTerm params` 로 전달 | `s1_env_cfg.py:170` 은 여전히 params 없음. 대신 `apply_judge_args`(`terrain_levels_mixed.py:140~160`) 가 **gym.make 앞**(`train_start.py:114` → `:118`, `train_sol23f_common.py:125` → `:134`) 에 커리큘럼 term 의 params 에 실제 값을 박는다. 인자가 없어도 함수 기본값을 params 에 박아 env.yaml 에 남긴다. term 이 그 인자를 모르면 ValueError | 맞음(사양 표현 「CurrTerm params」 와 길이 다르나 뜻 충족, 사양을 코드대로 고침) |
| S2 `terrain_levels_s2(…, world_frame=True)` 가 그대로 넘김 | `terrain_levels_mixed.py:185~186` 서명에 `world_frame: bool = True, mask_new_task: bool = False`, `:197` 그대로 전달. S-B 과제 사슬(s2_sb_cfg → s2_23f_b_cfg → s2_x23_cfg → s2_env_cfg) 에서 `curriculum.terrain_levels` 를 두는 곳은 `s2_env_cfg.py:47` 하나(시험이 AST 로 확인) | 맞음 |
| manifest `terrain_judge = {"world_frame", "mask_new_task", "start_checkpoint_judged_with"}` + 「출발 저장본은 옛 판정으로 학습됨」 | `modes.terrain_judge = judge_settings(env_cfg)` = `{"world_frame", "mask_new_task"}`(`:127~138`, params 에 기본값 덮어 읽음) · `modes.parent_judge = parent_judge(resume_path)` = 부모 폴더 `manifest.json` 의 `modes.terrain_judge`, 없으면 문구 `"world_frame=False (10/26 이전)"`(`:163~175`) · `modes.start_checkpoint_judged_with` = `"world_frame"` 또는 `"body_frame"`(`:178~180`). 두 스크립트 모두 `:141~143` · `:212~214` | 맞음(키 배치가 사양과 다르나 정보 같음 → 사양 v0.9 를 코드 모양으로) |
| 실제 부모 S-B10 m1500 이 「옛 판정」 으로 남는가 | `2026-10-26_01-17-47_sb-main/manifest.json` 의 `modes` 20 키에 `terrain_judge` 없음(내가 열어 확인) → `parent_judge` 옛 문구 · `judged_with` = `body_frame` | 맞음 |
| 켜는 시점은 다음 기동부터 | 돌고 있는 프로세스 없음(21:3x GPU0 0 MiB). 코드만 바뀜 | 맞음 |

## 2. 고침 2 (표식 덮기 기록용) 대조

| 사양(5.2 의 3 · J-T5) | 코드 | 판정 |
|---|---|---|
| `mask_new_task` 기본 False, 표식 에피소드도 판정대로 움직이고 `new_task_stats` 로 기록만 | `terrain_levels_mixed.py:14` 기본 False, `:49` `new_task_stats.add(...)` 는 늘, `:50~51` `if mask_new_task: move = rules.mask_new_task(move, marked)` | 맞음 |
| True 면 옛 덮기와 비트 동일 | 같은 `rules.mask_new_task` 호출. 시험 `test_marked_episodes_are_only_recorded_by_default_and_masked_when_asked`(기본: up `[T,F,T,F]` down `[F,T,F,T]` · marked 2 · would_have up 1 down 1; True: 표식 둘 모두 0) | 맞음 |
| 머리말 「기본 끔」 옛 문장(21:15 참고 4) | 시험 파일 머리말 「기본 켬(팀장 결정 8) · 설정(커리큘럼 term params) 과 실행 인자로 고른다」 로 고침 | 닫힘 |

## 3. 시험

내가 돌린 결과: `test_world_frame.py` + `test_terrain_mark.py` **34 passed, 2.87 s**(CPU, 캐시 안 씀). 새로 들어온 시험 7 개는 기본값 켬 · 옛 동작 인자 · `judge_settings` S1/S2 · `apply_judge_args` 쓰기 · 모르는 term 거절 · S2 전달 + train_start 순서(`apply_judge_args` < `gym.make` < `judge_settings`) · `parent_judge` 네 경우(manifest 없음 · 키 없음 · 있음 · 깨진 JSON) · S-B 사슬 소유자 · `train_sol23f_common` 노출 순서다. 사양 J-T10 시험 줄 「설정 경로로 `world_frame=False` 를 준 기동의 manifest 에 그 값이 남음」 은 `judge_settings` 단위 시험으로만 닫혔고 Kit 기동은 조건 4(smoke) 몫이다.

## 4. 참고 (막음 아님)

1. **manifest 키 배치.** 사양은 `start_checkpoint_judged_with` 를 `terrain_judge` 안에, 코드는 `modes` 바로 아래에 `parent_judge` 와 나란히 둔다. 코드 쪽이 부모 정보를 더 남기므로 사양을 코드대로 고친다(v0.9). 바꿀 것 없음.
2. **`parent_judge` 의 폴더 가정.** 체크포인트와 같은 폴더의 `manifest.json` 을 읽는다. EX-35 의 `--resume_from` 은 S-B10 원 폴더 `…/2026-10-26_01-17-47_sb-main/model_1500.pt` 를 가리켜야 한다. 복사본 폴더를 가리키면 이번 판은 결과가 같으나(둘 다 옛 문구) EX-36 이 EX-35 산출을 부모로 삼을 때 `terrain_judge` 를 못 읽어 출처가 끊긴다. 카드 §5 조건 4 에 확인 줄로 넣었다(v0.2).
3. **9 칸 밖 0 시험(21:15 참고 2) 은 그대로 남음.** 9 칸 표 시험은 analyst 반례 한 에피소드(`c-1w0` 1) 만 보고, 2000 에피소드 모의는 강등 수만 본다. 막음 아님, 다음 손질 때.
4. **sonnet-code 보고 파일 미확인.** lead 창의 경로 `sonnet-code/_out/reports/REPORT-sonnet-code-20261026-2130.md` 를 내 접근 경로(`C:/mai/wt/foothold-lab/*`, 주 체크아웃 `_out`) 에서 찾지 못했다. 대조는 diff 와 시험으로 했고 보고 본문은 읽지 않았다.

## 5. 재지 않은 것

Kit 기동의 실제 manifest(조건 4 smoke10 · smoke2 뒤) · reviewer X26w 재확인 · verifier 두 겹 · 통합 전체 회귀(sonnet-code 몫) · 실제 학습에서 갈린 에피소드 빈도.
