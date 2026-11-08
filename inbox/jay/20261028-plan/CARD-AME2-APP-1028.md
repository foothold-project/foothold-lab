> 분류: 실행 카드
> 작성: 오흥재 (lead) · 2026-10-28 19:5x
> 근거: 팀장 19:3x 지시(lead 창) · RunPod 네트워크 저장소 s3://rzklpc35sl · leggedrobotics/ame2_minimal · foothold-project/foothold-app
> 요지: 다른 팀원 실험 · 앱 · 내비 자료를 실제 데이터로 읽어 우리 다음 학습 논의 자료를 만든다
> 상태: 의뢰

# 카드 A · analyst: 임석헌 AME-2 학습 분석 + ame2_minimal 대조

목표: 「코드를 따라 하자」 가 아니다. 그 실험이 **어떤 문제를 어떻게 풀었고, 우리가 문제를 풀 때 무엇을 고려해야 하는가** 를 실제 데이터로 뽑는다.

자료
- RunPod: `aws s3 ls s3://rzklpc35sl/limseokheon/ --endpoint-url https://s3api-eu-ro-1.runpod.io` (default 프로필. 키 값은 절대 출력 · 기록하지 않는다). 폴더: ame2 · ame2_br · ame2_dh1 · ame2_es20 · ame2_fp32 · ame2_geneval · ame2_m035 · ame2_nogap20k · ame2_spd · ame2_st · backups · foothold-lab · tools
- 받는 것은 설정 · 로그 · TensorBoard events · 평가 결과만. 큰 저장본은 이름 · 크기 · 수정 시각만 목록으로 적는다. 내려받기 자리: `C:/mai/wt/foothold-lab/analyst-ame2/` (D: 여유가 더 크면 `D:/mai-data/ame2/`).
- 원본 저장소: GitHub star `leggedrobotics/ame2_minimal` (같은 자리에 clone).

할 일
1. 판마다 표: 로봇 · 지형 구성(종류별 비율) · 회차 · 부모(이어 학습이면 어디서) · 정밀도(bf16 · fp32) · env 수 · PPO 설정(lr · epoch · minibatch · rollout) · 명령 범위.
2. 원본과 다른 점 전부(diff): G1→Go2 · 보상 가중치(특히 attention 위치가 가장자리로 갈 때 벌점 · 네 발 동시 공중 벌점) · 명령 · 관측. 파일 · 줄 번호로.
3. 구두로 전해 들은 흐름을 데이터로 확인하고, 각 줄에 「실측 확인 · 다름 · 자료 없음」 을 단다: no_gap 으로 시작 → 약 9,000 회 최고점 뒤 하락 → 9,000 에서 fp32 로 이어 학습하니 곡선 상승 → 20,000 까지 → stepping stones 약 5 % 넣고 5,000 회 더.
4. 곡선: 보상 · 지형 레벨 · 에피소드 길이 · 보상 항목별 · 정책 std. 전환 시점마다 무엇이 바뀌었나.
5. 앱 담당(오현민)에게 넘길 저장본 후보: stepping stones 판 마지막 저장본 경로 · sha256 · 관측 · 행동 규격.
6. 인사이트 절: 그들이 문제를 푼 방식 → 우리(START 기반 하위 보행, EX-35 의 제자리 회전 넘어짐 · 왼쪽 회전 약함)에 비춰 고려할 것. 「참고할 만한 구체 설정」 은 따로 표로. 우리 쪽 근거는 `inbox/jay/20261026-experiments/RESULT-EX35-1027.md` · `20261027-design/EVAL-AXES-v2.md` · `20261026-experiments/CURRICULUM-GATES.md`(fable-25a 브랜치).
7. 덤: 우리 쪽 bf16 대 fp32 비교가 실제로 돌았는지 찾는다. 계획은 `inbox/jay/20261019-design/AGENDA-LEAD.md:276`(J4 `bf16_compare`) · 설정 `astra2-n1/foothold_s2/scripts/start_s2m_G1_*bf16kl*.json` 이다. 결과 json · 곡선이 있으면 경로, 없으면 「안 돌았다」 와 그 근거.

산출: `inbox/jay/20261028-plan/ANALYSIS-AME2-seokheon.md`(머리 다섯 줄 · em dash 금지 · 팀장 발언 원문 인용 금지, 이 저장소는 공개). 숫자마다 출처(파일 · 태그 · 회차). 끝나면 status --name analyst 로 한 줄 「끝 · 경로 · 막음 n」.
이 카드 뒤에 W29(EX-35 연장 결과 · 회전 원인)를 이어서 한다.

# 카드 B · verifier: 앱 · 내비 연결 규격 조사

1. `foothold-project/foothold-app`(오현민): 정책을 어떻게 읽고 돌리나(foothold-v2.pt · MuJoCo 물리 · Three.js 화면 · 서버). 관측 벡터 순서 · 행동 크기(scale) · 기본 관절 자세 · 제어 주기 · 명령 입력(조이스틱 → vx · vy · yaw) · 정책 선택 기능 유무. 우리 START 기반 하위 보행이나 AME-2 정책을 끼우려면 맞춰야 할 것을 표로(파일 · 줄).
2. 이민우 자료: RunPod `s3://rzklpc35sl/leeminwoo/`(go2-slam-nav2 · ros2_ws · runs) 와 foothold-lab 저장소 안 민우 자료가 있는지. Nav2 의 planner · controller 플러그인 이름(설정 yaml 에서), 턱을 벽으로 보는 문제가 어느 costmap 층에서 생기는지.
3. 우리 설계 문서(상위 둘 = Nav2 전체 경로 + HiPAN 짧은 거리, 하위 = START 기반 속도 명령 정책)와 실제 코드가 어디서 맞고 어디서 어긋나는지.

산출: `inbox/jay/20261028-plan/ANALYSIS-app-nav-interface.md`. 키 값 출력 금지. 끝나면 status --name verifier 로 한 줄.
