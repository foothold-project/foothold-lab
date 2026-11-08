> 분류: A/평가 · 이어 가기 경로 독립 점검
> 작성: analyst · 2026-11-08
> 근거: lead 15:2x 의뢰 · W65-WINDOWS-HANDOFF-1108 · 실제 model_350.pt · 오전 audit.py
> 요지: 실제 저장본과 반례 목록을 준비한다. runner 새 고정 HEAD에서 복원 소비까지 확인한다.
> 상태: 준비 · 새 고정 HEAD 대기 · 이어 가기 통과 판정 없음

# EX-42 0 단계 자기 이어 가기 독립 점검

R6·M15에 따라 실제 설치 클래스와 실제 체크포인트를 사용한다. M14에 따라 이름·SHA·회차·상한을 어긋나게 한 입력도 거절되어야 한다. 원 학습 run, manifest, runner 작업 사본은 읽기만 한다. CPU 시험 결과를 실제 Kit 재개 성공으로 부르지 않는다.

## 고정 입력

- 현재 실행 소스: `eae0bed799dce0e39b04d157ad4e3e79ecb87653`. 새 자기 이어 가기 구현은 이 판과 다르므로 이 판으로 통과를 선언하지 않는다.
- 실제 저장본: `C:/Users/AI-WS01/s2_lab/ex42_main_20261108_123914/main/EX-42-B-stagezero_20261108_123914/model_350.pt`.
- SHA256: `7c01f11657b2d66b5fe3b5324f889aea5749c0cebb00333472fb6322342ca75c`. 직접 재계산. manifest의 같은 파일 이름 항목과 대조.
- 학습 run은 계속 움직인다. manifest 전체 SHA·최신 completed는 읽은 시점 값이며, 특정 저장본의 SHA와 구별한다.
- 입력별 텐서·optimizer·난수 해시와 실제 상태: [checkpoint_inventory.json](ex42-resume-1108/checkpoint_inventory.json). 생성기 [inventory.py](ex42-resume-1108/inventory.py).

## 새 HEAD를 받으면 적용할 점검표

| 물음 | 답을 아는 입력과 소비 확인 | 닫는 조건 |
| --- | --- | --- |
| 같은 run · 정확한 저장본 | 실제 model_350·manifest 항목 사용. 다른 run·SHA 변조·이름/iter 불일치·EX41 부모 입력 반례 | 같은 run의 manifest 고정 저장본만 허용. 현재 manifest가 더 앞서 있으면 중복 학습 위험 처리 방식 명시 |
| 정책·지각 복원 | 실제 actor 98·critic 666 정책, TR-Net/추정기 state_dict, std, 정규화 상태 전부 대조 | 실제 수신 객체의 저장 후 상태 해시 일치. 누락·shape 변경은 거절 |
| 학습 상태 복원 | policy Adam·perception Adam·PPO learning_rate·AdaSmpl·force_gt·last_use_gt_frac | optimizer exp_avg/exp_avg_sq/step와 param_groups·스칼라가 실제 파일과 일치 |
| RNG·지도 선택 | torch CPU·numpy·python·명령 generator·map-switch generator·p_map_off·변경 이력 | 실제 CPU 복원과 다음 난수 표본 일치. CUDA RNG는 저장 배열/호출 경로만 CPU로 확인, GPU 복원 실측은 미확인 |
| 지형·커리큘럼 | terrain levels/types·command state·curriculum counters·plan/approval/parent SHA·DR·밀기 | 실제 runtime.load_state_dict 왕복 및 환경 복원 소비 확인. 물리 자세·episode history 미저장 범위 별도 기재 |
| local/누적 번호 | 저장350 → 첫 update351 → 누적12351 → 다음 정기저장400 | learn 루프와 curriculum_update_number를 함께 실행해 350 중복·352 건너뜀 없음. manifest 경험수도 24×3072×완료회차 |
| 승인 상한 | 350에서 남은650, 마지막1000. max1001·완료1000·잘못된 remaining 반례 | 1000 초과 불가. 완료1000은 재학습하지 않음. 1001번째 훅/저장 생성 없음 |
| 부모 재로드 방지 | 자기 이어 가기 분기에서 load_ex42_stage_zero_parent를 호출하면 실패하는 spy | EX41 parent 이식·iteration0·새 manifest/params 덮어쓰기 경로로 빠지지 않음 |
| 환경·경로 차이 | CPU 설치 isaac311/rsl_rl 소스와 실제 호출 대조. Windows→Linux 경로·GPU ordinal 차이 기록 | 검증된 논리 재개와 플랫폼 물리 동등성 주장을 구분. Linux 실제 재개는 미확인 |

## 준비에서 확인한 주의점

실제 m350에는 policy·perception optimizer 둘, `ppo_learning_rate`, `adasmpl`, `rng`, `map_switch`, `continuous_curriculum`, `env_state`가 있다. 단순히 파일에 있다는 것과 소비자에 복원됐다는 것은 다르다. `ex41_w86_reward_weights=None`이므로 실행 설정의 보상 연결을 별도로 대조한다.

기존 `StartRunner.learn`은 `_resumed`와 curriculum 종류에 따라 loop 시작 번호를 조정한다. 기존 일반 CLI의 remaining 산식도 iter+1을 쓰므로, EX42의 완료 회차 의미와 함께 검사한다. 기존 `load`가 다루지 않는 `ex42_parent_transfer`와 초기화 때 난수를 다시 소비하는 reset·map-switch 경로도 새 구현에서 살핀다. 이는 새 HEAD의 결함 판정이 아니라 감사 목록이다.

새 고정 HEAD 도착 후 이 문서를 실제 결과·코드 줄·막음 목록으로 갱신한다. 준비 상태를 막음 0으로 보고하지 않는다.
