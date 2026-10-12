고칠 것: cmdr_eval_driver.py · 정상 완료·짝·코드 판 고정 관문 누락, cmdr_bundle_compare.py · 허용 차이 판정과 실패 전달 오류, q_eval_cmdr.py · 부모 YAML 경로 검증 보완

> 분류: A/평가 · 일반화 벤치마크 · 지표
> 작성: 오흥재 (ASTRA 검증 · Codex 작성) · 2026-10-12
> 근거: TASK-astra-8-cmdr-eval-tools.md · VERIFY-astra-7.md 1·2절 · 평가 도구와 원본 runner · 저장된 QC·분기 관문 원자료 · CPU 인공 입력 시험
> 요지: 사본의 평가 계산과 저장 형식은 맞는다. 자동 진행을 허용하는 관문은 보완해야 하며, 현재 원자료로 정지·저속·초기 응답을 집계할 수 있다.
> 상태: 읽기 전용 검증 완료 · 이 파일만 신규 작성 · 학습·시뮬레이션 평가·GPU 작업·기존 파일 수정·커밋·push 없음

# ASTRA 8 · CMD-R 평가 도구 검증

- **확인됨:** `R=C:/isaac/ext/go2_rl_robotlab/_eval`, `B=R/out/branch`, `S=C:/isaac/ext/go2_rl_robotlab/source`로 줄인다. 검토본 SHA256 앞 16자는 `q_eval.py=717325a7a44159fe8`, `q_eval_cmdr.py=d4dc441c23b78d79`, `cmdr_eval_driver.py=5d3d5f098fe64f92`, `cmdr_bundle_compare.py=a321e9d09a1e311d`, `q_metrics.py=c9930f8d327efd04`, `q_post.py=f90aaa97a50c5347`로 의뢰서와 일치한다. 근거: 해당 파일 bytes 직접 SHA256 계산.
- **확인됨:** 아래 시험은 AST에서 순수 함수만 꺼낸 인공 입력 검사와 저장된 배열의 CPU 재대조다. 평가기·드라이버·대조기 진입점을 실행하지 않았다. 대조기 자체도 결과 JSON을 쓰므로 실행하지 않았다. 근거: `cmdr_bundle_compare.py:30~50`, `q_eval_cmdr.py:61~62,285~286`와 이번 검증 명령 범위.
- **미확인:** 이번 100-env 평가와 처리군 8192-env 초기 짝은 아직 실측 판정을 낼 수 없다. 검토 중 읽은 `R/out/cmdr_eval_driver.json`에는 `tests={}`, `runs=[]`, `gpu1_from` 없음이었고, `cq_*` 결과 디렉터리와 `B/cmdr_s1042_on_u4000/bundle.json`도 없었다. 이 관찰은 해당 시점의 저장 기록이며 이후 실행 상태를 보장하지 않는다.

## 1. 사본·checkpoint·부모 YAML

- **확인됨:** 원본과 사본의 실제 diff는 `re` import, `--train_yaml`, YAML fallback·출처 기록, loaded iteration 검증이다. 관측 구성·reset·명령·policy 호출·rollout·지표 함수 호출은 같다. 부모 YAML 값은 `dict_diff` 입력으로만 쓰이고 `env_cfg`에 적용하지 않는다. 따라서 정해진 공통 평가 환경을 유지하며, 분기의 훈련 상태를 복원하는 평가기는 아니다. 근거: `q_eval_cmdr.py:54~55,182~237,292~302,580~638` 및 `q_eval.py`와의 전체 diff.
- **확인됨:** 분기 wrapper는 원본 `OnPolicyRunnerCTS.save`를 그대로 호출한다. 원본 save/load 모두 `model_state_dict`, 두 optimizer, `iter`, `infos` 형식을 사용하고, policy의 `load_state_dict`는 전체 복원 뒤 `True`를 반환한다. 부모 20000과 gate_c1 20002의 checkpoint ZIP 안 `data.pkl`을 실행 없이 읽어 다섯 key와 각각의 `iter=20000/20002`도 확인했다. 근거: `branch/branch_run.py:269~277`, `S/rsl_rl/rsl_rl/runners/on_policy_runner_cts.py:167~181,260~285`, `S/rsl_rl/rsl_rl/modules/actor_critic_moe_cts.py:268~281`, 해당 `.pt` 내부 pickle opcode.
- **미확인:** 위 확인은 저장 형식과 로딩 경로 검증이다. 이번 사본으로 GPU에 올린 뒤 추론까지 정상 완료했다는 뜻은 아니다. 나올 예정인 22000·24000 파일의 실제 로딩도 아직 확인하지 않았다. 근거: 의뢰의 실행 금지와 위 결과 부재.
- **확인됨:** `train_yaml_source.kind`에 부모 YAML은 base config이고 분기 override는 bundle에 있다고 명시했다. 부모 YAML을 분기 전체 설정이라고 위장하지 않으므로 ASTRA 7의 요구를 지킨다. 다만 `branch_args`·`branch_code`만 복사하고 실제 동기화 상태 `bundle.state`와 bundle 자체 hash는 남기지 않는다. 출처 경로만 남기면 나중에 같은 경로의 파일이 바뀌었을 때 이 평가가 어느 bundle을 봤는지 확정하기 어렵다. 근거: `q_eval_cmdr.py:190~213`, `branch/branch_run.py:223~263`.
- **확인됨 · 수정:** 부모 YAML 검증은 두 단계 상위 디렉터리만 비교한다. 인공 경로 입력에서 `.../e1/params/env.yaml`뿐 아니라 `.../e1/params/other.yaml`도 통과했다. 부모 checkpoint SHA는 검사하지만, 임의의 YAML이 그 부모의 정확한 `params/env.yaml`이라는 것은 보장하지 않는다. 정규화한 정확한 파일 경로를 대조하고, 검증한 YAML·bundle의 내용 hash를 평가 manifest에 묶어야 한다. 잘못된 YAML이 rollout을 바꾼다는 지적이 아니라 출처 검증의 허점이다. 근거: `q_eval_cmdr.py:192~203`, 해당 경로 식의 CPU 인공 입력 시험.

## 2. 시험 넷과 자동 진행 관문

| 시험 | 확인한 효력과 놓치는 것 |
|---|---|
| ① 110-env smoke | **확인됨:** 명시한 11개 이름×10episode이므로 `fwd10` 추가와 무관하게 110 env다. 새 실행에서는 exit code 0을 요구한다. 그러나 이미 `cells.json`이 있으면 smoke를 건너뛰고, `N`, 칸별 10행, noise, UUID, loaded_iter, 비유한 값, 관측 명령 오차를 읽어 판정하지 않는다. 저장된 검사값에 오류가 있어도 프로세스가 0으로 끝나면 통과할 수 있다. 근거: `cmdr_eval_driver.py:36,100~122`, `q_eval_cmdr.py:103~106,617~643`. |
| ② 원본·사본 known answer | **확인됨:** 같은 부모의 flat stop03, 100 env, noise on에서 `cells.json` 값과 NPZ 파일 전체 SHA가 같아야 한다. 변경된 branch fallback 경로는 부모 평가에서 타지 않으므로 이 시험만으로 branch 출처 오류를 잡지는 못한다. 두 쪽이 똑같이 틀리거나 동일한 오래된 결과를 읽어도 같을 수 있다. 근거: `cmdr_eval_driver.py:124~138`, `q_eval_cmdr.py:188~204`. |
| ③ 잘못된 YAML 거부 | **확인됨:** nonzero 종료와 정확한 오류 문구를 함께 요구하므로 단순 GPU 메모리 중단·일반 예외만으로는 통과하지 않는다. 다만 다른 부모 디렉터리만 시험한다. 같은 부모 디렉터리의 다른 YAML, 부모 SHA 불일치, bundle 없음·오염, iteration 불일치를 별도로 시험하지 않는다. 근거: `cmdr_eval_driver.py:139~149`, `q_eval_cmdr.py:193~203,299~301`. |
| ④ gate_c1 20002 통과 | **확인됨:** 새 실행에서는 exit code 0, 저장된 `loaded_iter=20002`, 출처 key 존재를 요구한다. 내용이 정확한 E1 부모·YAML·bundle인지, `checks_run`이 정상인지까지 검사하지 않는다. `cells.json`이 남아 있으면 재실행을 생략하므로 이전 코드의 산출물로도 통과할 수 있다. 근거: `cmdr_eval_driver.py:150~160`. |

- **확인됨 · noise 켬 재현 근거:** `QC-E1.md:23~35`의 원자료를 다시 읽었다. `out/m20000_noise_flat`과 `out/qc_repro_m20000_noise_flat`은 둘 다 N=1100·noise on이며, `traj` shape `(1001,1100,12)`, 종료 배열, 공통 key 전체 bytes, NPZ 전체 SHA가 같았다. noise off 두 자료도 공통 배열은 같았으나 새 자료에 `cmd_hist`가 추가돼 NPZ 전체 SHA는 달랐다. 따라서 기존 on 재현은 확인됐고, off의 「궤적 동일」을 「파일 전체 동일」과 혼동하면 안 된다. 근거: 해당 네 폴더 `meta.json`·`traj.npz`의 직접 비교, `R/qc_md.py:77~85`.
- **미확인 · 이번 관문으로의 일반화:** 위 결과는 1100 env에서의 과거 재현이다. 100 env·현재 dependency·현재 GPU 상태에서도 반드시 bitwise라는 증명은 아니다. ②가 다르면 우선 원본 A 대 원본 A 재현으로 비결정성·환경 변화를 분리해야 하며, 「차이는 무조건 사본 탓」이라고 단정하면 안 된다. 근거: `cmdr_eval_driver.py:137`의 주석과 위 원자료의 N 차이. 일치를 확인하지 않은 채 허용 오차를 넓혀 통과시키라는 뜻은 아니다.
- **확인됨 · 우선 수정 1, 완료 판정:** `done()`은 파일 존재만 본다. AST로 꺼낸 함수에 존재 여부만 참인 가짜 filesystem을 넣어도 True였다. 정상 완료 표식은 필요한 JSON/CSV/NPZ 파싱·필수 key·shape·행 수·finite 검사, exit/guard 정상 종료, 기대 checkpoint hash·iter·조건·코드 hash까지 맞아야 한다. `checks_run`의 명령 오차·비유한 개수와 `checks_pre`의 student 경로 불변성 검사를 실제 실패 조건으로 연결해야 한다. 기록만 하고 다음 작업으로 넘어가면 관문이 아니다. 근거: `cmdr_eval_driver.py:110~111,117~160,204~209`, `q_eval_cmdr.py:451~538,617~643`, CPU 함수 시험.
- **확인됨 · 우선 수정 2, 판 고정:** 현재 hash는 드라이버 시작에 한 번 적고 매 실행 전에 대조하지 않는다. `q_post.py`는 목록에서 빠졌으며 새 프로세스는 그때의 `q_metrics.py`·환경·policy 코드를 읽는다. 최소 evaluator·metrics·postprocessor·환경/명령/지형/runner/policy의 근거 hash를 고정하고 각 실행의 실제 판이 같을 때만 같은 표에 넣어야 한다. 원본 known-answer 실행도 시작에 기록한 원본 hash와 맞아야 한다. 변경된 판의 이미 완료된 결과를 `done()`으로 재사용하지 않는다. 근거: `cmdr_eval_driver.py:179~180`, `q_eval_cmdr.py:79~85,632~634`.
- **확인됨 · 우선 수정 3, checkpoint 식별:** `ready()`는 정해진 크기와 mtime 경과를 보고 hash를 모델명당 최초 한 번만 저장한다. 120초 동안 두 번 재서 안 바뀐 것이 아니라 「현재 mtime이 120초 이전」이라는 조건이다. CPU 가짜 stat 시험에서 예전 hash가 LOG에 있으면 현재 hash를 읽지 않고 True를 반환했다. 현재 부모와 gate 파일 크기는 실제로 26,367,183 B이나, 그 크기만으로 저장 정상 완료·내용 불변을 보장하지 않는다. 각 실행의 `meta.checkpoint_sha256`을 고정 manifest와 대조하고, 재사용 결과도 같은 hash인지 확인해야 한다. 근거: `cmdr_eval_driver.py:71~81`, `q_eval_cmdr.py:297~301`, 직접 stat·ZIP 검사 및 CPU 함수 시험.
- **확인됨 · 추가 운영 한계:** 현재 jobs는 주 분석 440개와 flat noise-off 55개, 총 495개다. 준비된 부모만 있으면 다른 모델의 flat을 기다리지 않고 부모의 다른 지형으로 진행할 수 있다. 실패 작업은 pending에서 이미 제거된 뒤 `skipped`로 남고 전체 프로그램은 정상 종료할 수 있다. 집계에는 5 checkpoint×family×cell×noise의 완료 행렬을 넣고 누락을 0%나 완료로 취급하지 않아야 한다. 근거: `cmdr_eval_driver.py:163~172,195~214`, AST `jobs()` 직접 계산.
- **확인됨 · 운영 조건 확인:** 메모리 guard는 GPU 1·4096MiB로 맞지만, 메모리를 약 200ms 간격으로 감시하는 방식이지 선예약은 아니다. 다른 드라이버 종료 여부도 `unseen_driver.py` 이름만 확인하며 고아 평가 프로세스·다른 GPU 작업의 부재를 증명하지 않는다. `--until` 기본은 14시이며 시험·실행·재시도 중에는 deadline을 검사하지 않으므로 엄격한 종료 시각도 아니다. ASTRA 7의 9시 사용 경계가 여전히 유효하면 그 예산을 재확인하고 다음 작업을 시작하지 않는 외부 운영 조건을 정해야 한다. 이 검증에서 프로세스를 종료하거나 연장 승인을 대신하지 않았다. 근거: `cmdr_eval_driver.py:60~68,84~97,176~196`, `gpu_guard.py:17,29~47`, `VERIFY-astra-7.md` 2(a).

## 3. 초기 짝과 표본

- **확인됨:** 같은 family·cell·100episode·seed·noise·difficulty·spawn·policy·코드 판으로 다섯 checkpoint를 따로 실행하는 설계는 ASTRA 7과 맞는다. 지형 seed와 env seed가 고정되고, `epi%8` 출발 행과 명령별 yaw를 배정한 뒤 같은 seed로 reset한다. 다만 설계가 같다는 것과 실제 fingerprint 일치는 구분해야 한다. 근거: `q_eval_cmdr.py:217~230,267~278,316~370`.
- **확인됨 · 수정:** 드라이버는 다섯 모델의 `pairing_sha256_ext`를 한 번도 비교하지 않는다. 집계 전에 `(family, cell, noise, eval_seed, episodes, difficulty, spawn, terrain_set)`로 묶고 부모를 기준으로 off/on 22000·24000의 아래 항목을 대조하는 실패 관문을 추가해야 한다. 근거: `cmdr_eval_driver.py:195~210`, `q_eval_cmdr.py:380~440,625~627`.
  - **확인됨:** `pairing_sha256`의 root pose·joint position·masses·stiffness와 `pairing_sha256_ext`의 COM·재질·actuator 강성/감쇠·delay·motor zero offset은 **key 집합과 값 모두** 같아야 한다. 없는 key를 비교에서 빼거나 `{}`끼리 같다고 통과시키면 안 된다. 근거: `q_eval_cmdr.py:399~439`.
  - **확인됨:** terrain mesh가 실패 문자열/빈 목록이 아닌지 확인하고 mesh hash·terrain origins·실제 `env_origins.npy`도 비교한다. NPZ의 `fam/cel/epi/cmd_a/cmd_b/sw`와 meta의 실제 cell 정의·순서를 맞춘다. 각 파일에서 `cel=0`이라도 그것이 같은 명령인지 이름까지 확인한다. 근거: `q_eval_cmdr.py:103~106,316~337,380~397,625~627`.
  - **확인됨:** 같은 그룹 안의 GPU UUID, N/T, noise enable 값, heading hold, 관측 shapes·policy 경로, dependency hash가 같아야 한다. 서로 다른 checkpoint의 **rollout 전체 traj·명령 추종·action**이 같을 필요는 없다. checkpoint hash는 의도된 차이이고, 초기 조건과 측정 계약이 같아야 한다. 근거: `q_eval_cmdr.py:281~313,377~378,565~567`.
- **확인됨 · 한계:** 기존 fingerprint 일부는 5~6자리 반올림 hash이고 초기 root/joint velocity, 관측 history 원자료와 CPU/CUDA RNG 전부를 담지는 않는다. 그 값들의 일치는 「기록된 초기 상태·DR의 일치」이며 모든 내부 상태의 bitwise 동일성까지 뜻하지 않는다. 초기 `traj[0]`의 실제 속도도 대조하고, 더 강한 재현 주장이 필요하면 초기 velocity·obs/RNG hash를 별도 고정본에 보완한다. 종료 시점이 달라 reset 난수 소비가 갈라질 수 있으므로 이후 noise 시퀀스 전체가 계속 같은 것도 미확인이다. 근거: `q_eval_cmdr.py:399~440,550~569,605~607`.
- **추정 · 표본 제안:** seed 1000×100episode로 시작하는 것은 선별 평가로 적절하다. 확장 목록은 결과를 보기 전에 **[1000, 1001, 1002, 1003, 1004]**, seed당 100episode로 고정하는 안을 권한다. 모든 checkpoint에 같은 목록을 적용하고 seed를 포함한 tag/manifest를 써야 한다. 현재 tag에는 seed가 없어 확장하면 이전 결과를 완료로 오인할 수 있다. seed1042/1043은 학습 분기 반복이고 이 평가 seed 목록과 별개다. 근거: `VERIFY-astra-7.md` 2(b), `cmdr_eval_driver.py:100~107,203~205`, `q_eval_cmdr.py:44,218,275`.
- **확인됨 · 해석 제한:** seed 변경은 시작 난수뿐 아니라 지형도 바꾸므로 배치 내 checkpoint끼리 짝을 맞추고 seed·출발 행별 차이를 함께 보고해야 한다. 같은 seed 재실행은 재현성 확인이지 새 독립 표본 100개가 아니다. 100회 결과만으로 5%p 비퇴행 확정이나 seed1042 한 번으로 일반적 CMD-R 효과를 주장하면 ASTRA 7의 범위를 넘는다. 근거: `VERIFY-astra-7.md` 2(b)·2(c), `q_eval_cmdr.py:275,321~323,370`.

## 4. bundle 대조기

- **확인됨:** 현재 bundle schema에는 adapter 호출 수가 없다. `adapter_calls`는 별도 rollout 결과에만 있고 `bundle.json`은 첫 rollout 전 상태다. 처음 episode 나이가 모두 0이면 CMD-R on이 그 나이를 다시 0으로 보게 해도 관측·commands·RNG가 달라질 이유는 없다. 따라서 현재 schema에서는 허용할 추가 차이를 찾지 못했다. 처리군의 state 차이를 adapter의 당연한 차이라고 넓혀 허용하면 안 된다. 근거: `branch/branch_run.py:195~205,250~263,301~308`.
- **확인됨:** 저장된 4096-env 관문 짝을 직접 다시 비교했다. `cmdr_off` 대 `cmdr_on`은 허용된 세 경로 외 차이 0·배열 차이 0이었다. `gate_c1` 대 `cmdr_on`은 예상 밖 JSON 차이 26·배열 차이 7이었다. 의뢰서의 두 시험 결과는 재확인됐다. 근거: 해당 폴더 `bundle.json`·`bundle.npz`, `cmdr_bundle_compare.py:19~46`과 같은 순수 비교 로직의 CPU 재실행.
- **확인됨 · 수정 1:** 「허용」 차이 셋이 **모두 반드시 달라야** SAME이 된다. 다른 조건이 같은 정상 off/on 짝의 `t_start`를 같게 만든 인공 입력은 DIFFERENT였다. 허용집합은 차이 경로의 상한이어야 하며, 꼭 달라야 하는 실험 arm 값과 단순 출처 값을 구분해야 한다. 근거: `cmdr_bundle_compare.py:16,34~46`, CPU 인공 입력 시험.
- **확인됨 · 수정 2:** 허용 경로의 **값**은 확인하지 않는다. 인공 입력에서 오른쪽 cmdr를 `on` 대신 `typo`로 바꿔도 SAME이었다. 왼쪽 `off`·오른쪽 `on`, 기대 parent hash·seed·8192 env·4000 updates 등의 규약과 필수 schema를 별도로 확인해야 한다. 두 군이 똑같이 잘못된 설정이면 equality만으로는 걸러지지 않는다. 근거: `cmdr_bundle_compare.py:30~46`, CPU 인공 입력 시험, `TASK-astra-7-night-cmdr.md`의 실험 조건.
- **확인됨 · 수정 3:** DIFFERENT여도 명시적 nonzero exit가 없고, 현재 평가 드라이버는 이 비교 결과를 읽지 않는다. JSON/배열 누락·불일치에 실패 종료를 전달하고, 해당 밤 run의 새 보고서·입력 bundle hash·기대 arm 확인을 짝 승인 조건으로 연결해야 한다. 시험용 대조도 고정 `cmdr_bundle_compare.json`을 덮으므로 오래된 4096-env 시험 보고서를 이번 8192-env 승인으로 쓰지 않도록 입력 식별이 필요하다. 근거: `cmdr_bundle_compare.py:47~50`, `cmdr_eval_driver.py:114~214`.
- **확인됨 · 기록 범위:** JSON의 model·두 optimizer·DR·관측·RNG hash, NPZ 전체의 key·dtype·shape·bytes 대조는 유용하다. 다만 두 bundle 모두에서 빠진 field는 잡지 못하고, hash가 없는 전체 물리 상태까지 복원하는 검사는 아니다. 예컨대 초기 joint/root velocity와 solver/contact 내부 상태는 raw bundle에 없다. JSON의 기록 hash와 NPZ의 대응 배열이 서로 일관적인지도 현재는 교차 검증하지 않는다. 최소 필수 key/schema와 대응 hash를 확인하고 「전체 simulator 동일」로 확대 표현하지 않는다. 근거: `branch/branch_run.py:215~263`, `cmdr_bundle_compare.py:19~46`.

## 5. 아침 집계에 필요한 출력

| 항목 | 현재 출력으로 가능한가 · 집계 규칙 |
|---|---|
| stop03 span | **확인됨 · 가능:** `episodes.csv`의 `span_q2_pass`, `span_q2_stop_only`, `span_stop_t`, `span_stop_dist_m`, `span_survived`, `span_q2_cat`를 쓴다. cells의 기본 `pass_rate`는 n50이므로 span 판정과 혼용하지 않는다. t=5.00의 j=250을 기준으로 j≤300에서 51개 연속 표본이 평면 속도 <0.05·yaw rate <0.10이어야 한다. 생존·전진 추종·정지창 시작까지 순변위 ≤0.20m를 함께 본다. 근거: `q_metrics.py:25~51,269~301`, `q_post.py:18~19,37~46,81~90`. |
| 저속 MAE | **확인됨 · 가능:** fwd01/fwd02의 명령 축 한도는 0.05/0.10m/s, 다른 선속도 축은 0.15·yaw는 0.20이다. CSV의 `q1a_pass` 또는 span 규약을 택하면 `span_q1a_pass`와 MAE 원값을 집계한다. cells의 `q1a_pass_rate`는 n50 집계이며 `span_q1a` 집계 열은 따로 없으므로 CSV에서 계산해야 한다. 원래 `q1_pass`로 대신하면 서 있는 fwd01을 통과시킬 수 있다. 근거: `q_metrics.py:176~215`, `q_post.py:18~19,44~46,78~86`. |
| 0~1초 추종 응답 | **확인됨 · 가능:** CSV의 MAE는 처음 1초를 제외하므로 원시 `traj.npz`를 사용한다. 50개의 0.02초 구간에 대해 `traj[j,:,4:6]`와 `cmd_hist[j,:,:2]`, `traj[j,:,9]`와 yaw 명령의 절대오차를 적분한다. `cmd_hist[j]`는 state j를 만든 action j−1의 명령이다. 최대 yaw-rate 추종 오차와 unwrap한 heading의 명령 적분 대비 오차를 구분해 낸다. 근거: `q_eval_cmdr.py:550~569,583~607,625~627`, `q_metrics.py:10~17,176`, `q_post.py:37~43`. |
| 시작 접촉·0~5초 생존/전진 | **확인됨 · 제한적 가능:** 현재 termination은 base 접촉 >1N이므로 `term[1:51]`로 첫 1초의 해당 접촉 종료를 확인할 수 있다. `term`·gravity·height로 5초까지 Q 생존을 계산하고 world 위치를 명령 방향에 투영해 진행량을 낸다. 종료가 난 state j는 이미 reset된 값이므로 최초 무효 state 이전만 사용한다. 조기 실패 episode를 평균에서 버리지 말고 실패율·관측된 길이·그때까지의 오차를 별도 보고한다. 근거: `S/robot_lab/robot_lab/tasks/go2/env_cfg.py:437~446`, `q_metrics.py:118~144,165~170,217~239`, `q_eval_cmdr.py:605~607`. |
| 접촉의 힘·약한 접촉·5ms 피크 | **미확인 · 현재 출력으로 복원 불가:** term은 임계값을 넘은 종료의 표지이며 전체 접촉 힘이나 발 힘이 아니다. 50Hz state에 없는 200Hz 순간 피크도 복원할 수 없다. 이것까지 필요한 경우 별도 고정 평가본에서 env별 base force/history·개별 종료 원인·시각을 기록해야 한다. 현재 `--full_record`도 발 force와 종료 flag 중심이므로 단순히 그 옵션만 켜면 base force 전체가 생기는 것은 아니다. 근거: `q_eval_cmdr.py:550~559,571~574`, `full_record.py:25~45`. |

- **확인됨 · 알려진 입력 시험:** 새 평가 없이 순수 `q_metrics`에 인공 궤적을 넣었다. t=6.00부터 정지 50표본은 n50만 통과, 51표본은 span도 통과, t=6.02 시작은 실패, 속도가 정확히 0.05인 구간은 실패했다. fwd01에서 속도 0은 기존 Q1 통과·q1a 실패, 속도 0.06은 q1a 통과였다. fwd02 속도 0.12도 MAE 0.08로 q1a 통과했다. 경계와 저속 기준 구현은 제안한 계산과 맞는다. 근거: `q_metrics.py:113~115,198~213,269~297`, CPU 인공 입력 시험.
- **추정 · 추가 계측 없이 먼저 할 일:** 필요한 것은 새 시뮬레이션보다 **판을 명시한 읽기 전용 집계기**다. 위 span·저속·startup 지표를 5 checkpoint의 같은 episode 키로 나란히 내고, on−off와 부모 대비 변화, 실패 episode, confidence interval, 누락 셀을 분리한다. 정지 시간·변위는 성공한 episode의 평균만 제시하지 않는다. 제안선과 확정선도 구분한다. 근거: `VERIFY-astra-7.md` 2(c)와 현재 CSV/NPZ schema.
- **확인됨 · 실행 담당자에게:** 현재 학습을 중단해야 할 결함을 새로 확인한 것은 아니다. 이 판정은 평가 자동 진행·집계 승인 전에 고칠 항목이다. 실행 중 파일은 수정하지 않았으며, 위 변경은 lead가 기존 실행을 보존하는 별도 판·재개 절차로 적용해야 한다. 근거: 의뢰의 읽기 전용 조건 및 위 코드 검증 범위.
