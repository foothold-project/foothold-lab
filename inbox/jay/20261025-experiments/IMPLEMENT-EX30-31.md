> 분류: 리서치
> 작성: 오흥재 · lead_tmp · 2026-10-25
> 근거: DESIGN-EX30-31.md · d9517fb9 실제 runner·명령·지각 코드 · ASTRA24f 요구 소비 감사
> 요지: 같은 부모에서 지도 선택만 다르게 출발하고 명령·지형·DR 확대와 관측을 실제 소비하는 코드 계약 및 시험을 지정한다.
> 상태: v1.0 진행 · T1 · T4 일부 구현 (리뷰 중) · 나머지 미완료 · 장기 기동 승인 아님
> 판: v1.0

# EX-30·31 구현 계획

**목표**: [설계](DESIGN-EX30-31.md)의 두 판을 코드·manifest·측정·이어받기에서 같은 계약으로 구현한다. **구조**: 기존 START 학습망을 유지하고 전환 importer, 순수 curriculum/command 코어, Isaac 어댑터, 관측·평가를 분리한다. **기술**: 설치 Isaac Lab·rsl_rl·PyTorch, 기존 `foothold_s2`, Windows 단일 GPU/3072. 버전/환경 해시는 기존 실행에서 직접 추출해 새 manifest에 둔다.

실행 담당은 lead가 Claude sonnet-code/rl에 배분하고 검토는 fable가 맡는다. 기존 실행 worktree `lead-tmp-start-b`@d9517fb9와 그 로그는 불변이다. 새 구현은 그 코드에서 분기한 독립 worktree에서 한다. 공유 체크아웃·기존 live 코드에 쓰지 않는다. 실행 방법은 팀장과 이미 합의한 세션 배분을 따르며 Codex 작업자를 새로 늘리지 않는다.

## v1.0 진행 (lead · 10/25)

- 설계 v1.0 (F1~F3 팀장 결정) 에 따라 **창 1 (추가 0~250) 은 B cfg 그대로 · 지도 처치만**. 그래서 창 1 에 필요한 것은 T1 + T4 의 평가 모드 + 짧은 Kit 시험뿐이고, T2 · T3 은 창 1 이 도는 동안 구현해 창 2 이후 적용한다.
- T1 추가 항목: 창 1 에서는 부모 지형 레벨을 두 판 모두 같은 방식으로 이어 쓰는 선택 복원 플래그 (planner F1 최소 수정). 창 2 의 P0 진입 때 `course_v1` 계약으로 바꾸고 옛 지형 승급 · vmax 자동 상승 term 을 끈다.
- 구현 (feature/ex30-31-impl-jay, worktree `C:/mai/wt/foothold-lab/impl-ex30-31`, 로컬 커밋, push 안 함): T1 `52977744` → 리뷰 막음 2 고침 `d1c22796` · T4 일부 지도 모드 `bcbe5f2e` · 평가 · 짧은 Kit 스크립트 `ee90aa82` (평가 스크립트에 리뷰 막음 1, 고치는 중).
- 리뷰: reviewer `_out/review/PRECHECK-d9517fb9.md` (v0.2) · `REVIEW-52977744.md` · `REVIEW-ee90aa82.md`. 아래 체크 표시는 리뷰 통과와 Kit 확인 뒤에만 바꾼다.

## 전역 계약

- 부모 SHA·2판 시작·std12개·optimizer/LR은 설계§2.1 그대로. 계약이 다른 보통 resume은 계속 거절한다.
- 3072×24, actor96/critic664, learned I-E, 모델 크기·gradient detach·보상 B·foot_edge0을 유지한다. 이 수치는 새 cfg의 실제 forward shape로 검증한다.
- `mainline_adaptive`와 `gt_control`의 차이는 지도 선택 처치와 그 결과다. 나머지 named config diff는 허용 목록0으로 검사한다. 출력 이름/ID 등 운영값은 별도 목록이다.
- 코드·원자료·cfg·전환영수증·확대journal·평가코드 SHA를 manifest에 묶는다. 소스 옆에 파일만 존재하는 것으로 소비를 증명하지 않는다.
- 로드된 hard/soft limits·action 이름/단위·200Hz 접촉·depth/GT/PRED 시간축을 실제 소비 위치에서 기록한다.
- 구현 후 CPU 시험, 별도 승인된 짧은 Kit 시험과 장기기동을 구별한다. 아래 미완료를 통과로 보고하지 않는다.

## 검토 집중점

1. 부모 force_gt=true가 새 cfg를 덮는 경로, variant 검사 우회가 다른 부모까지 허용하는 경로 → T1.
2. 지형/명령/DR의 값을 바꿨지만 실제 runtime은 옛값인 경로, reset 때 반복 배율 누적 → T2/T3.
3. 빠른 판만 승급하거나 map RNG 차이가 command RNG까지 바꾸는 경로 → T2.
4. 지도없음0을 평지로 해석, 센서 frame age/reset이 다른 episode로 새는 경로 → T4.
5. deadline·촬영·재개가229처럼 임의회차에 멈추거나 .done은있는데 검정영상인 경로 → T5/T6.

## T1. 명시적 부모 전환과 정확한 재개

파일: 새 `foothold_s2/runners/stage_transfer.py`, `foothold_s2/tests/test_stage_transfer.py`; 수정 `runners/start_runner.py`, 새 EX30/31 runner/cfg. 기존 `sol23f_runner.py` 변경 금지.

인터페이스:
- `import_parent(parent_path: Path, spec: TransferSpec, device: str) -> TransferResult`
- `TransferSpec`: parent_sha256, experiment_id, map_policy (`adaptive`/`gt`), seed, curriculum_spec_sha256.
- `TransferResult`: weights/optimizers/LR/normalizers, parent_iter, parent_completed_updates, new_completed_updates=0, explicit_reset_fields, receipt.
- `restore_child(path: Path, expected_spec_sha: str)`는 새 판의 정확 재개. `import_parent`와 혼용 금지.

- [ ] 반례 시험: B부모를 일반resume+force_gtFalse로 읽으면 현재와 같이 거절. importer에 틀린SHA/타모델/차원불일치/초기snapshot을 주면 거절.
- [ ] 정상 시험: 두 판의 모델·optimizer·LR·std·정규화 바이트/텐서가 동일. GT와 PRED 선택을 제외한 같은 입력 출력 동일. 첫 GT mask는 두판 모두True, 첫 유효 CV 갱신 뒤 mainline만 변경 가능.
- [ ] 구현: 명시한 상태만 가져오고 새env/episode/RNN reset 및 새curriculum P0를 초기화. 이름이 다른variant 허용은 importer한곳만. 부모자료를수정하지않음.
- [ ] 재개 시험: child25추가 갱신 저장 뒤 새프로세스에서26으로 이어짐. `model_1500+k`, 부모1501+추가k라는 번호/경험량 대조. dtype/device·optimizer step 카운터도 확인.
- [ ] CPU 시험과 변경 diff를 검토해 별도 커밋. 명령: `python -m pytest foothold_s2/tests/test_stage_transfer.py -q`.

## T2. 명령 분포와 성과 기반 과정

파일: 새 `curriculum/performance_course.py`, `commands/course_core.py`, `tests/test_performance_course.py`, `tests/test_course_commands.py`; 수정 `commands/mixed_command.py`, `curriculum/terrain_levels_mixed.py`의 **새 cfg 분기만**.

인터페이스:
- `CourseState`: version, global_boundary, per_cohort {mode/sign/terrain/level/range/mix/dr_stage}, previous_windows, journal_sha.
- `propose_progress(state, paired_metrics, spec) -> CourseDecision` (순수 함수); `CourseDecision`는 hold/promote/regress·한축delta·근거분모·sequence_no.
- `sample_commands(profile, goal_state, named_rng, dt) -> command_3, mode, eligibility, source_id`.

- [ ] 반례:200episode 미만,1000env·s미만,한판만pass,중복journal,좌성적만으로우승급,두축동시확대는승급하지않음. 0성공에서도새종류첫5%탐색은이미잘하길요구하지않음.
- [ ] 경계 시험:0.8/0.9와연속2창,0.5미만2창후퇴,나머지유지. 모든phase/혼합합1,쉬운과제최소20%,inactive=0,확장후동일pairedspec SHA.
- [ ] 명령시험:100000표집에서 P0/P1/P2 허용범위/비율 및부호;stand 0,0,0과spin분리. backoff미자격땐후진없음,자격때몸x음수·2s·0.6m. 목표뒤=돌아가기와backoff 구분. heading감김π경계·goal무효셀·마지막2s정지.
- [ ] RNG시험:mainline의GT선택표집을100회더해도동일command seed의명령열은불변. 종자+env+episode키를저장,새episode수차이는실현노출로보고.
- [ ] 실제 생성기/runner의 옛 `contract=start`가새명령을거절하지않도록 `course_v1` 계약 추가. 기존start반례검사는유지. `start_mode=False`한줄로끝났다고보고금지.
- [ ] CPU시험·정상/의도실패출력·별도커밋. `python -m pytest foothold_s2/tests/test_performance_course.py foothold_s2/tests/test_course_commands.py -q`.

## T3. 지형 배정과 물리 실제 적용

파일: 새 `tasks/s2_course_env.py`, `tasks/s2_course_cfg.py`, `curriculum/physical_course.py`, `tests/test_physical_course.py`, `tests/test_course_terrain.py`; 기존 `terrains/rough_go2_cfg.py`, `s2_layout.py`, `s2_runtime.py`, `commands/mixed_command.py` 연결부.

인터페이스: `apply_course_at_reset(env_ids, CourseDecision) -> AppliedStateReceipt`. 수치결정은T2, 실제설정쓰기/읽기는T3. 영수증에는 requested와readback·관절/링크순서·nominal SHA·dtype/units·실패이유가있다.

- [ ] 답아는입력:nominalgain25에1.02반복reset20번후25.5이지누적곱아님. COM도nominal+offset. delay substep1은5ms이고policy1step20ms와혼동하면실패.
- [ ] 소재표집반례:dynamic>static거절,combine mode누락거절,읽어온물리값안바뀌면receipt 실패. 실제Kit확인전CPU더미통과를PhysX적용확인으로쓰지않음.
- [ ] 지형은행:12종형상과flags유효성을분리. 초기연속90/flat10,기존연속상대비율,5%frontier,원점/level/spawn앞뒤순서. 시작네발지지·관측무효셀·0valid인경우·타일경계진행을시험.
- [ ] 양판공통course가범위일치. episode별realized DR·지형·명령노출을저장한다. old회수기반p_advance가뒤에서재배정하면반례로거절.
- [ ] `python -m pytest foothold_s2/tests/test_physical_course.py foothold_s2/tests/test_course_terrain.py -q` 통과·별도커밋.

## T4. 실제 지도 선택과 지각 불량 진단

파일: 수정 `models/start_perception.py`, `eval/adapters.py`의명시모드; 새 `tests/test_course_map_modes.py`; `runners/map_stats.py`, `sensors/start_obs.py` 기록 연결.

인터페이스: `MapEvidence` = gt/pred/selected/selection_mode/actual_use_gt/grid_frame/valid_mask/visible_mask/last_seen_age/camera_tick/episode_id. mode는train_adaptive/train_gt/eval_pred/eval_gt/probe_prop_only.

- [ ] 정답평면·기울기·구멍을아는입력으로 x/y순서·yaw회전·referenceheight·clip단위를검산. GT/PRED를서로다른정수상수로넣어실제선택과logger대조.
- [ ] eval_pred는parentforce_gtTrue라도policy입력GT0개. reset후에도0. train_adaptive는False여도GT선택가능. oldcfg한줄만으로누출없다고보고하지않음.
- [ ] prop_only 진단은mapCNN토큰을attention에서제외하는mask로구현,0높이지도대체금지. 이진단은학습처치추가아님·정상성미보장. TR/I-E손실과actor입력크기그대로,변경모드명시.
- [ ] depth2frames·10Hz·history/reset/age와GT같은시각을검산. 첫PRED episode로그강제보존. rawdepth보존,Keyer표시는별도.
- [ ] `python -m pytest foothold_s2/tests/test_course_map_modes.py foothold_s2/tests/test_start_perception.py -q`·별도커밋.

## T5. contact·관절·측정과 독립 probe

파일: 새 `diagnostics/course_evidence.py`, `eval/course_probe.py`, `tests/test_course_evidence.py`, `tests/test_course_probe.py`; 기존 `measurement-sol24i/record_sol24i.py`는복사후프로젝트모듈로옮기고동작회귀시험.

인터페이스: `capture_substep(snapshot, identity)`; `EpisodeRecord`; `evaluate_probe(policy, ProbeSpec) -> ProbeResult`. 세부채널·주기는설계§7/8. `ProbeSpec`는seed목록·지형hash·center/방향·cmd/지속·mode·DR배열·예상frame수.

- [ ] 경계시험:아는관절상한·cliptorque·접촉impulse로원인채널계산. calf만접촉한입력을footcontact로세지않음. simultaneoustermination bitset보존.
- [ ] XY속도와경사접선속도가다른synthetic예를통과. contactnormal/point없는경우slip확정값null·대용치명명. API미지원필드의0채우기금지.
- [ ] 잘걷다타일밖으로나간episode는의도지형성공으로세지않음. 조기죽음의오차를고정200step분모로나눠좋아보이게하지않음. trace상고정horizon·validtime·firstreset을분리.
- [ ] 좌/우회전독립reset·원하는command부호·순서반전. vx0이라도wz작동,예상방향앞뒤구분. 평가plainphysics와trainDR표본분리.
- [ ] `python -m pytest foothold_s2/tests/test_course_evidence.py foothold_s2/tests/test_course_probe.py -q`·별도커밋.

## T6. 저장·촬영·재개·인계

파일: 새 `scripts/train_course.py`, `scripts/run_course_pair.py`, `tests/test_course_lifecycle.py`; 재사용 `eval/seq_video.py`의 검증기·blackframe 보완. 정책/과정상태는JSON+checkpoint,LLM세션존재에의존하지않음.

- [ ] 기동시Parent/코드/설계/실소비cfg해시·단위·env·seed·GPU·상한·wall deadline·운영승인참조를등록한다. 승인참조를에이전트가창작하지않음.
- [ ] boundary stop=50/100배수계약. 일찍촬영준비신호가와도임의229에서중단하지않음. 절대deadline은최후가능경계계산·긴급종료구분. 모델원자저장→해시→자식종료→촬영→동일child재개→첫추가갱신순서시험.
- [ ] 자식실패/끊긴MP4/검정/빈영수증/잘못된NPZ episodeID는.done게시안함. decode·300frame같은값은ProbeSpec으로계산,무조건12초강제하지않음.
- [ ] 빠른판이pairedboundary를넘어임의승급하지않음. 느린판실패해도다른판/남의process를죽이지않고승인된경계에저장·상태보고.
- [ ] CPU suite·짧은 실제Kit 승인후10update→저장→새프로세스2update재개·record→video decode/눈확인. 이과정완료전긴학습준비완료라고보고하지않음.
- [ ] `python -m pytest foothold_s2/tests/test_course_lifecycle.py -q`·별도커밋. 실측시간/VRAM/추가촬영여유를보고Windows실행또는Linux이전선택을팀장과정함.

## 요구와 검증의 인계

[요구 추적표](REQUIREMENTS-EX30-31.md)의 각행을T1~T6,기존정본,실제파일/시험/증거로잇는다. 구현완료라고표시하려면실제소비위치와결과파일이필요하다. CPU/Kit/성능/실기네층을같은PASS로묶지않는다. fable는설계한번,구현뒤변경경로검토를맡으며통과할때까지반복하는자동절차를만들지않는다.

| 판 | 날짜 | 내용 |
|---|---|---|
| v0.1 | 2026-10-25 | 구현 경계·인터페이스·답 아는 입력 반례·미완료 상태 지정 |
