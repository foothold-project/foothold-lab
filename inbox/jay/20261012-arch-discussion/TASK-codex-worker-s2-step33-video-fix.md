> 분류: A/평가 · 영상 · Codex Worker 작업서 (sol) · step33 (step31 보다 먼저)
> 작성: 오흥재 (lead 세션 · Claude 작성) · 2026-10-18 02:35
> 근거: step30 영상 도구 첫 실제 실행 `C:/Users/AI-WS01/s2_lab/s2_step30_run/videos_u2000_fixed8/` (읽기 전용) · 로그 `C:/Users/AI-WS01/.claude/jobs/09bbf294/tmp/videos_launcher.log` · 최종 평가 `C:/Users/AI-WS01/s2_lab/s2_step32_run/runs/evalfull-u2000-live-20261018-002543-8bb6a76b/` (120 건 중 유효 113, 결측 7) · 결과 `s2_lab/s2_step32_run/results_u2000/S2-AB-UPDATE2000.json`
> 요지: 영상 도구가 실제 실행에서 두 곳에 걸렸다. 결과에 결측 쌍이 있으면 차이 예시 선택을 통째로 거절하고, 첫 자식 Kit 이 episode 없이 끝났다. 고쳐서 아침 보고 전에 영상이 나오게 한다
> 상태: 작업 지시 (CPU 만 · GPU 0 은 lead 가 update 0 평가로 쓰는 중, 약 04:15 까지)

# sol 작업서: 영상 도구 실제 실행 수리 (step33)

## 사실

1. `--episodes` 를 주면 `s2_video_plan._pairs_from_episodes` 가 `valid_case_arms != 120` 이라 `episodes_identity_or_completeness` 로 거절. `--result` (S2-AB-UPDATE2000.json) 도 `result_identity_or_verification` 로 거절(결과 파일의 `comparison_ready` · `performance_verified` 가 결측 때문에 false).
2. 둘 다 빼고 결과 전 고정 8 편만으로 02:31 기동 → 첫 슬롯 `00-video-gap-s4000-A` 의 Kit 자식이 episode 를 남기지 않고 끝나 `VideoRunHold: case_episode_missing:00`, 전체 중단. `kit.log` 끝은 USD 경고(`Unresolved reference prim path ... Head_lower/visuals`)뿐이고 오류 줄이 없다. 원인 미확인.

## 필요한 것

1. **결측 쌍을 빼고 계속.** 차이 예시 선택은 등록 규칙대로 결측 쌍을 제외한 유효 쌍에서 고른다(평가 결과와 같은 규칙). 결과 · episodes 의 신원(cases_sha256 · update · 스키마)은 계속 대조하되, 「120 건 모두 유효」 를 영상 선택의 조건으로 쓰지 않는다. 빠진 쌍과 그 이유를 selection.json 에 기록한다.
2. **첫 자식이 episode 없이 끝난 원인.** 위 슬롯 폴더와 kit.log 를 읽고(쓰지 않고) 자식이 어디서 끝났는지 밝혀라(종료 코드, 마지막 Python 줄, faulthandler, 렌더 모드 rgb_array 초기화, 카메라 · viewer 인자). 평가 driver 와 다른 점은 어댑터 렌더 인자 하나뿐이라고 보고했으니 그 경로를 먼저 의심한다. 자식이 실패하면 그 편만 실패로 기록하고 **다음 편으로 계속**(평가와 같은 방식, 같은 운영 결함 5 건 연속이면 중단).
3. **실제 확인을 짧게 먼저.** lead 가 GPU 가 비면 한 편(gap 4000 A)만 먼저 돌려 볼 수 있게 `--only-slot` 같은 인자를 둬라.
4. **창을 띄우지 않기 (팀장 확정 「A」).** 자식 기동 플래그에서 `DETACHED_PROCESS` 를 빼고 `CREATE_NO_WINDOW | CREATE_NEW_PROCESS_GROUP` 만. 근거: vfxpedia/mai-os main 49af062 `os/repro/win_console_popup_repro.py`, `os/tool-hazards.md` 마지막 절. 확인: (a) 같은 재현 방식으로 창 0 개, (b) 부모를 닫아도 작업 생존(Job Object · 워치독), (c) 로그 · 종료 확인서 · kill 경로가 DETACHED 가정에 기대지 않음.
5. **시험:** 결측 7 쌍이 있는 실제 결과 파일로 선택 PASS(차이 예시가 결측 쌍을 고르지 않음), 실패 자식 한 편 → 다음 편 진행, 창 0 개.

## 끝나면

`REPORT-s2-step33.md`(원인 · 바뀐 파일 · 시험 · 미확인 · lead 명령 한 줄), `S2-STEP33-SHA256SUMS.txt`. **목표 04:00 (update 0 평가가 끝나는 04:15 에 GPU 가 비면 바로 영상).** step31 은 그 다음에 이어서 하고, step31 의 기동기 수정에도 4 번(창 안 띄우기)을 같은 확인 항목으로 넣어라.
