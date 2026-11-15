> 분류: A/평가 · 영상 · Codex Worker 작업서 (sol) · step35 (긴급)
> 작성: 오흥재 (lead 세션 · Claude 작성) · 2026-10-18 04:39
> 근거: step33 한 편 실제 실행 `C:/Users/AI-WS01/s2_lab/s2_step33_run/videos_u2000_slot00/` (읽기 전용) · `videos_u2000_slot00.launch_receipt.json` (HOLD no_video_completed)
> 요지: 영상 자식이 환경 생성 단계에서 오류 기록 없이 끝난다(종료 코드 0, episode 없음). 원인을 기록으로 남기게 하고 고친다
> 상태: 작업 지시 (CPU 만 · GPU 0 은 비어 있으나 lead 가 수리 확인 뒤 돌린다)

# sol 작업서: 영상 자식 환경 생성 실패 (step35)

## 사실
- 04:35 `--only-slot 00` (gap 4000 A) 실행. `child_progress.jsonl`: `python_main_enter` → `app_launcher_start`(cuda:0) → `policy_load_start` → `policy_load_done` → `env_create_start` → `child_finally`. 오류 단계 기록이 없다. `child_exit.json` 종료 코드 0, `episode_exists` false. `child_stack.log` 0 바이트(60 초 덤프 전에 끝남). `kit.log` 54 줄, 마지막은 경고뿐이고 Python traceback 이 없다.
- Kit 의 GPU 표(Vulkan 순서): 0 = bus 81 · UUID 315d098f(**화면용 · Active**), 1 = bus 41 · UUID c08e23b0. 평가 · 학습은 c08e23b0(NVML 0)을 썼다. 영상 자식은 `CUDA_VISIBLE_DEVICES` 없이 `--device cuda:0` 이라, torch 의 cuda:0 과 Kit 렌더 GPU 가 다를 수 있다(미확인).

## 필요한 것
1. `env_create` 와 그 뒤 단계를 `try/except BaseException` 으로 감싸 예외 종류 · 메시지 · traceback 을 `child_progress.jsonl` 과 별도 파일에 즉시 쓰고, 예외가 있으면 **종료 코드를 0 이 아닌 값**으로 한다. `sys.exit`/`SystemExit`, `os._exit`, Kit `simulation_app.close()` 경로도 기록하라.
2. 원인 후보 셋을 근거로 가려라: (a) torch cuda:0 대 Kit 렌더 GPU 불일치. 평가 driver 는 같은 경우 어떻게 장치를 맞췄는지 비교한다. (b) `--enable_cameras` · `rgb_array` 렌더 초기화. (c) 평가 adapter 와 영상 adapter 차이. 평가 자식(같은 머신 · 같은 번들)은 같은 단계를 통과했으니, 영상 자식과 평가 자식의 argv · env · AppLauncher 인자를 diff 로 보여라.
3. CPU 로 가능한 재현 · 시험, 그리고 lead 가 바로 돌릴 한 편 명령.

## 끝나면
`REPORT-s2-step35.md`, `S2-STEP35-SHA256SUMS.txt`. 가능한 한 빨리(목표 05:30).
