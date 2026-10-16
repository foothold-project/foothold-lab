> 분류: A/정책학습 · ASTRA 의뢰 17ah · A3.3 (학습 환경 RobotLab-Go2-v0 로 옮긴 0단계) 수집과 배관 재시도의 허용 범위
> 작성: 오흥재 (lead 세션 · Claude 작성) · 2026-10-16 15:50
> 근거: 10/16 14:15 4차 수집 · 14:17 첫 배관의 실제 결과(`night-tools-20261013/s2_stage0_first_collection/attempt4_20261016_1415/` · `plumbing_A_first_20261016_1417/`) · sol step10 보고 `REPORT-s2-step10.md` (사본 `night-tools-20261013/s2_step10/` · `s2_step4a33/`, 저장소 사본 반영됨, lead 재실행은 진행 중) · VERIFY-astra-17af 2절 · 17ag
> 요지: 4차와 배관이 실제 Kit 에서 돌아 설정 불일치 둘을 드러냈다. 하나는 배관 게이트 이름(`base_contact` 대 `illegal_contact`), 다른 하나는 0단계가 학습 환경과 다른 환경(`Isaac-Velocity-Rough-Unitree-Go2-v0`)에서 돌았다는 점. sol 이 CPU 에서 고쳤다. 다음 GPU 단회 두 개의 허용 범위와 조건을 묻는다
> 상태: 의뢰 (GPU 둘 다 계산 0 · 승인 json 없음 · 팀장의 새 직접 동의는 이 판정 뒤)

# ASTRA 17ah

비판적이면서도 냉정하고 현실적인 전문가로서 답해 주십시오. 분량 `VERIFY-astra-17ah.md` 한 파일, 첫 줄 한 문장 판정. 코드 수정 · GPU · Isaac · 커밋 금지, em dash 금지. 확인됨 / 추정 / 미확인을 나눠 주세요. 17af · 17ag 에서 닫힌 것은 다시 보지 말고 아래만 봐 주세요.

## 사실 (lead 가 원자료에서 읽은 것)

- 4차(A3.2, 14:15:29, 36초): FULL_ROWS_HOLD, 정상 256 step, 장치 결박 verified, edge 불일치 0, hit mask 불일치 0, 높이 최대 오차 4.58e-6 m. HOLD 이유 셋(`mesh_evidence_content` · `fixed_pose_evidence` · `case_assignment`)의 원인은 둘: (a) PhysX 질의가 모든 표본에서 miss(sol 계산: 103,224개 전부 status 0, RayCaster 유한 hit 은 101,844개) (b) env 6(stones_0) 첫 16 step `root_quat_w` x 성분 편차 0.00484 > 0.002. 독립 관찰자 PASS.
- 첫 배관(10/16 14:17:42, 17초): `PlumbingHold: training_cfg_physics_unknown`, 학습 0.
- 원인 1: 게이트가 `terminations.base_contact` 를 읽는데 RobotLab-Go2-v0 와 E1 `params/env.yaml` 의 종료 항은 `time_out` · `illegal_contact`.
- 원인 2: 0단계 번들은 `BASE_TASK = Isaac-Velocity-Rough-Unitree-Go2-v0` (Isaac Lab 기본 Go2, S3 자산, 보상 11항). B 학습은 `RobotLab-Go2-v0` (URDF Go2 로컬 변환).
- sol step10 (CPU): `s2_task_contract.py` 한 곳에 task → 접촉 종료 항 이름 표(미등록 거절), 배관 게이트 · entry 비교 경로가 이 표를 사용. 실제 소스 AST 대조 시험과 이름 회귀 변이 2/2 CAUGHT. `s2_step4a33/` = A3.2 49개 파일 복사에서 `BASE_TASK` 와 자산 · 종료 항 · 명령 설정만 RobotLab 로 옮김(지도 · 어댑터 · runner · tracker · 정책 · PPO · 점검 코드 · 메시 프로브 · 장면 답은 A3.2 와 바이트 동일, lead 가 cmp 로 확인). 계약은 URDF 자산 경로와 `expect_conversions == 1` 을 요구. 두 환경 `height_scanner` 설정은 소스상 항목별 동일. sol 의 시험 수치: B 39/39 파일 331 PASS 변이 70/70 · A3.3 23/23 작업 208 PASS 변이 50/50 (lead 재실행 진행 중, 결과는 #550 에 따로).
- 미확인: 실제 RobotLab Kit 기동, 실제 URDF 1회 변환, A3.3 256 step 판정, PhysX 전부 miss 의 단일 원인(sol 순위: scene query 가 collider 를 못 봄 · 호출 형식 · collision group 필터), env 6 의 발 접촉 원인.

## 질문

1. **A3.3 수집의 허용 조건.** 같은 형식의 참석 단회(정보 수집 전용, 256 step, 최대 15분, 재시도 0)를 RobotLab-Go2-v0 에서 해도 되는가. 17ab · 17ac 의 기동 전 조건에서 새로 필요한 것은 무엇인가(최초 URDF 변환 1회의 USD 증거 · USD 잠금 · 변환 시간 상한 · 자산 해시 · 요청의 `expect_conversions`). PhysX 질의 전부 miss 와 자세 편차가 같은 모양으로 다시 나오면 그 결과를 어떻게 분류하고 어디까지를 학습 경로 증거로 쓸 수 있는가. 17af 2절 표로는 「mesh 충돌 증거」와 「고정 자세」가 이번 학습에 적용되지 않는 별도 항목인지 ASTRA 판단이 필요하다.
2. **배관 재시도.** 이름 표 수정은 17ae 3절의 「좁은 후속」 범위(lead 검증 기록 + 팀장의 단회 직접 동의)인가, 아니면 `s2_task_contract.py` 신설과 contract 코드 묶음 변경 때문에 ASTRA 가 새 바이트를 봐야 하는가. 후자라면 볼 파일과 줄, 필요한 CPU 증거. 두 번째 실행 때 같은 실패가 반복되지 않았다는 증거로 요구하는 것(예: Kit 안에서 cfg 이름을 한 줄 점검만 하고 멈추는 단계)이 있는가.
3. **연속 동의 한 메시지로 A3.3 수집과 배관 재시도를 이어서 해도 되는가.** 17af 5절 형식을 그대로 쓴다면 두 번째 조건(「관찰자 정리 PASS」)이 첫 실행의 HOLD 종류와 무관한지 확인.
4. **PhysX 전부 miss 와 env 6 자세 편차의 판별 단회.** sol 안: 학습 0, 8 env × 16 step, 알려진 지면 3광선을 step 전후에 질의하고 `carb.Float3` 인자 형식 · 반환 원형 · scene path · 필터를 기록, 첫 16 step 의 발 접촉력과 root 각속도 기록, 허용치 0.002 는 그대로. 이 판별이 A3.3 수집과 같은 Kit 기동 안에 들어가도 되는가(한 번의 동의로 두 기록) 아니면 별도 단회여야 하는가. 판별 도구가 만들어야 하는 CPU 증거와 변이 항목.
5. **짧은 A/B 와의 연결.** 위 조치가 끝나면 17af 2절 표에서 「범위를 명시한 탐색 short」 로 갈 수 있는 최소 증거 목록(격자 순서 · 좌표/offset · yaw/pose · hit/miss · 시간/episode 중 A3.3 로 닫히는 항목과 닫히지 않는 항목).

## 하지 말 것

- 무인, 자동 재시도, 후속 학습, 200 update smoke 허용으로 읽히는 표현. 17z 무인 보류는 유지.
- 이 의뢰에서 17af 의 단회 2,000회 계약을 다시 심사하지 말 것.
