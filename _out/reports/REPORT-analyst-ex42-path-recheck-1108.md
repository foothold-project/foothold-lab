> 분류: 독립 코드 재점검
> 작성: analyst · 2026-11-08
> 근거: detached eae0bed799dce0e39b04d157ad4e3e79ecb87653 · 실제 EX-41 m6000 · isaac311 CPU 시험
> 요지: H1~H5와 model_50 기록 오류 닫힘 · 해당 경로에서 확인된 실행 막음 0 · 별도 registry 불일치 1 유지
> 상태: 읽기·CPU 재점검 완료 · Kit 첫 갱신·실제 model_50 생성 및 재로드는 미실행

# EX-42 0 단계 수정본 재점검

**물음 1: H1~H5·model_50 모두 CPU 계약 수준에서 닫혔다. 물음 2: 수정으로 새로 생긴 실행 막음은 찾지 못했다. 물음 3: 첫 update~50회 저장 경로의 이번 지적분 실행 막음은 0이다.** 이 판단은 학습 기동 승인이나 실제 Kit 50회 완주 판정이 아니다. 아래의 기존 registry 불일치와 기록·이어받기 한계는 남아 있다.

원본을 직접 고치지 않고 새 detached 사본 `D:/mai-wt/foothold-lab/analyst-ex42-recheck-eae0bed7`을 만들었다. HEAD eae0bed7, 시험 전후 git clean. 분석 산출물은 자기 보고 가지와 `D:/mai-tmp/analyst`에만 썼다. R15·R20에 따라 runner의 113 PASS 주장을 대체 근거로 쓰지 않고 관련 16개 시험과 독립 점검을 직접 실행했다.

## 닫힘 표

아래 소스 줄은 모두 eae0bed7 기준이다.

| 지적 | 이번 직접 확인 | 판정·코드 근거 |
|---|---|---|
| I46 Gym wrapper | 실제 `gymnasium.wrappers.OrderEnforcing`에는 num_envs·device가 없지만 unwrapped로 접근하면 정상 | 닫힘. `scripts/ex42_training_entry.py:181`~191의 raw.num_envs·raw.device |
| H1 명령 5/13칸 충돌 | 실제 T0′ 설정·seed42·3072개 추출. 실제 configure helper 적용 뒤 13칸 누적이 정상이고 합 3072. 카운트는 이전 반례와 동일 | 닫힘. `scripts/train_start.py:844`~847이 첫 reset 862보다 앞. configure helper는 실제 `scripts/ex41_startup.py:68`~91 |
| H2 W86 직렬화 | 실제 W86Runtime 타입을 별도 유지하고 새 readback builder 결과 전체를 JSON 왕복. w86_attached=true, 가중 계약·DR·밀기·lin_vel_z 숫자가 직렬화됨 | 닫힘. `scripts/ex42_training_entry.py:296`~324. 실제 attach_runtime을 사용하는 관련 회귀도 통과. 독립 검사는 물리 adapter를 실행하지 않음 |
| H3 step hook 누락 | 실제 EX42StageZeroRuntime에서 50개 update 번호 × 24개 pre/post callback을 호출. 각각 1200, state_dict 왕복 일치. 중복 pre·잘못된 done 크기 반례는 관련 시험으로 거절 확인 | 닫힘. `scripts/ex42_training_entry.py:217`~232. 호출 순서는 StartRunner의 pre→env.step→post와 대조. **1200번 물리 step 또는 PPO 학습을 했다는 뜻은 아님** |
| H4 lin_vel_z −2 잔류 | 실제 부모 SHA 확인 뒤 cfg −2→0. 설치 RewardManager의 get/set 메서드 본문으로 live manager 계약을 대조, 새 helper 적용 뒤 0 | 닫힘. `scripts/ex42_training_entry.py:334`~365, `train_start.py:752`~757 및 857~861. 설치 `reward_manager.py:215`~244는 가중치 0이어도 항을 등록하므로 get/set이 가능함. Kit의 실제 manager 생성은 아직 미실행 |
| H5 부모 밀기·DR 연결 | 실제 부모 continuous_curriculum에서 Vmax=2.0을 읽음. 실제 RuntimeReadback+EX42StageZeroDRReadback 조합으로 1~50회 매번 DR=1, Vmax=2, 지연 상한 0.015 유지. 실제 방사형 표본 함수 4096개 검사에서 크기 상한 이하 | 닫힘. `scripts/ex42_training_entry.py:371`~402, `train_start.py:848`~855·941. legacy DR 스케줄 함수 호출 뒤 실제 소비 전에 상수1로 복구됨을 확인. 새 물리 표본을 측정한 것은 아님 |
| model_50 완료 회차 | 실제 StartRunner._manifest_checkpoint에 it=50, EX42 runtime을 넣고 게시 인자를 기록. 완료50, 경험3,686,400 | 닫힘. `runners/start_runner.py:964`~973. 모델50 **파일을 생성한 시험은 아님**. 50×24×3072와 일치 |

## 재현 범위와 원자료

| 항목 | 값·근거 |
|---|---|
| 실제 부모 | `C:/Users/AI-WS01/s2_lab/ex41_main_20261104_235522/main/EX-41-B-main_20261104_235522/model_6000.pt` |
| 실제 부모 SHA256 | `1c6af6319c823c718af4965064f1c312b0d25177f5223a49c323aab3b6f1e613` |
| 부모 차원 | actor 첫 층 512×98, critic 첫 층 512×666. 실제 파일 CPU 로드 |
| 관련 시험 | `test_ex42_training_entry_cpu.py` + `test_ex42_stage_zero_cpu.py`: **16 passed in 5.73s**, 실제 부모 경로 지정. SKIP 없음 |
| 독립 점검 | [audit.py](ex42-recheck-1108/audit.py) · [audit.json](ex42-recheck-1108/audit.json). 실제 클래스와 함수 사용. 물리 엔진만큼은 실행하지 않고 CPU 입력 계약으로 격리 |
| 설치 RewardManager 대조 | `C:/isaac/isaaclab/source/isaaclab/isaaclab/managers/reward_manager.py`의 get_term_cfg·set_term_cfg 본문을 AST로 가져와 실행. manager 생성·PhysX·공통 term resolver는 미실행이라고 명시 |
| 실제 DR 함수 | `RuntimeReadback.update_start/summary` 및 방사형 sampler 사용. 알려진 CPU 센서 버퍼를 쓴 계약 시험이므로 물리 readback 실측으로 해석하면 안 됨 |
| 실행 환경 | isaac311, CUDA_VISIBLE_DEVICES 빈 값, PYTHONDONTWRITEBYTECODE=1, PYTHONUTF8=1, TMP·TEMP·pytest basetemp 전부 D:/mai-tmp/analyst. GPU·Kit·학습·운영 파일 변경 없음 |

## 남은 것과 범위 밖 실패

1. **기존 registry 불일치 1건을 숨기지 않는다.** `test_experiment_registry_cpu.py:63`을 따로 실행해 1 FAIL을 재현했다. registry는 EX-40 m6000 SHA `d5e9ec40…`, 실제 EX42 0 단계 계획은 EX-41 local6000/cumulative12000 SHA `1c6af631…`이다. 두 문서 및 해당 시험은 이번 수정에서 바뀌지 않았다. 점검한 시작 경로의 train_start·ex42_training_entry·ex42_chain·runner manifest에는 이 registry 로더 호출이 없어, 이번 첫 50회 실행을 죽이는 신규 오류로 세지는 않았다. **정본 기록 불일치는 남으므로 별도 담당자가 맞춰야 한다.** 따라서 전체 시험 0 FAIL이라고 보고하지 않는다.
2. 오전 보고의 CLI self-resume 거절, 초기 snapshot의 iteration=0 조건, EX42 effective.reward_weights 누락, last_use_gt_frac 최신 기록 조건은 이번 수정 범위에 없고 여전히 남아 있다. 첫 50회 CPU 경로 닫힘과 운영·이어받기 계약 완성을 구별한다.
3. 실제 Kit에서는 첫 reset readback의 lin_vel_z=0·DR=1·Vmax=2.0, 실제 obs 98/666·pose_cmd, 첫 update, model_50의 torch 재로드·optimizer/RNG/curriculum·SHA·manifest 완료50을 확인해야 한다. 이번 CPU 결과가 그 실측을 대신하지 않는다.

원자료: [관련 시험 로그](ex42-recheck-1108/pytest.log), [별도 registry 실패 로그](ex42-recheck-1108/registry.log), [독립 점검 로그](ex42-recheck-1108/audit.log), [SHA256SUMS](ex42-recheck-1108/SHA256SUMS).
