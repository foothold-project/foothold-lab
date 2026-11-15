# 열린 이슈 132건 판정 (2026-10-07)

> 분류: 운영
> 작성: 오흥재 · 2026-10-07 18:40
> 근거: 읽기 전용 조사 4묶음 (이슈 본문 · 댓글 · 연결 PR · main 파일 실측)
> 요지: 팀장 계정으로 열린 132건을 완료 45 · 폐기 28 · 진행 8 · 대기 51 로 판정했다. 확신 낮음 8건은 팀장 확인 전 손대지 않는다.
> 상태: 검토중

| # | 판정 | 확신 | 보드(10/7 오후) | 제안 | 제목 | 근거 |
|---|---|---|---|---|---|---|
| #29 | 완료 | 중간 | Todo | 닫기 (완료) | [작업] 에셋 팩 수령과 HDRI 렌더 테스트 | HDRI PT 실증 · vMaterials·Sample Scenes 수령 · 남은 체크는 ACC 방향과 안 맞음 |
| #65 | 완료 | 낮음 | In Progress | 팀장 확인 | [작업] 실패 지형 gap: 진단 -> 레시피 (임석헌) | gap 은 v1/v2 로 풀림(v2 보고서 238행 100%) · 레시피 카드 형식은 없음 |
| #66 | 완료 | 중간 | In Progress | 닫기 (완료) | [작업] 실패 지형 rails: 진단 -> 레시피 (맹라현) | rails-diagnosis.md v1.4 · 스윕 설계 · rails 46.3→99.7% |
| #74 | 완료 | 높음 | Todo | 닫기 (완료) | [작업] 일정 시스템 구현 (8/26 설계안이 통째로 증발했다) | 주간 템플릿 · hub3.py:417 · ia.py:471 · 라벨 |
| #76 | 완료 | 중간 | Todo | 닫기 (완료) | [작업] 사이트 온톨로지 정의 (무엇이 무엇의 상위인가) | doc-graph · info-model · doc-graph.json 120 · docs_pages.py:750 |
| #78 | 완료 | 중간 | In Progress | 닫기 (완료) | [주간] W35 팀 목표 (8/24~8/30) | W35 다이제스트 · 주간 종료 |
| #79 | 완료 | 높음 | In Progress | 닫기 (완료) | [주간] W36 팀 목표 (8/31~9/6) · 기획발표 주 | 9/4 산출물 확정 · WBS 웹 · rails PR #140 |
| #89 | 완료 | 중간 | Todo | 닫기 (완료) | [작업] v2.0.0 적용 완료 점검 · 여덟 가지를 실측으로 확인한다 | 9/1 실측 · v2.0.0 확정 · e11e4146 (2번만 안 함) |
| #93 | 완료 | 중간 | Todo | 닫기 (완료) | [작업] PRD-WEB 정렬 패스 · 기준 한 장대로 전 화면을 맞춘다 | 체크 1·2·3·5·6 · 4번은 #95 · 7번 증거 없음 |
| #95 | 완료 | 높음 | Todo | 닫기 (완료) | [작업] 표지를 타겟 기준으로 재구성 · 온톨로지의 마지막 축을 쓴다 | 8/31 6/6 완료 · 3d8b1d4a · 5ce884cb |
| #100 | 완료 | 낮음 | Todo | 팀장 확인 | [작업] 평가 지표 3종(평균 리턴 · 에피소드 길이 · 성공률) 적용과 판정 기준 문서화 | eval-protocol-v2 v2.1 · 평균 리턴 지표는 없음 |
| #101 | 완료 | 중간 | Todo | 닫기 (완료) | [작업] MuJoCo ↔ Isaac Sim 관측 차원 차이 조사: 결과를 어디까지 근거로 쓸 것인가 | roles-responsibilities.md:200 MuJoCo 참고 · 7% 일치 |
| #108 | 완료 | 높음 | In Progress | 닫기 (완료) | [작업] RunPod 영속 볼륨 경로 정정: 웹에 게시된 /workspace 안내 3곳을 /data 로 | /data 경로 반영 2baacca4 · runpod-setup.md |
| #111 | 완료 | 중간 | Todo | 닫기 (완료) | 웹 문서에 출처 이슈 표기 | docs_pages.py:417·568 · docgraph.py:70 (metacheck 경고는 없음) |
| #115 | 완료 | 중간 | Todo | 닫기 (완료) | Go2 관절 각도 한계 기구학 계산 (5 cm 벽) | go2-joint-limits.md v1.1 · 발 높이 31.0/30.1 cm |
| #119 | 완료 | 높음 | Todo | 닫기 (완료) | 팀원 포지션 키워드 신설과 대외 화면 반영 | ROLES.md:73-109 포지션 · hub-proposal |
| #120 | 완료 | 중간 | Todo | 닫기 (완료) | 웹 v2.0.0 확정과 공지 | v2.0.0 공지 docs/notices/2026-09-02.md · DECISIONS.md:107 · #89 #93 #95 는 열려 있음 |
| #128 | 완료 | 높음 | Todo | 닫기 (완료) | 프로젝트 페이지 검색의 본문 색인 누락 (절 1500자 잘림) | searchbox.py:550 절단 제거 · 관문 · 9/9 라이브 실측 보고 (PDF 색인만 남음) |
| #133 | 완료 | 중간 | Todo | 닫기 (완료) | 발표 스토리라인 v1.0 검토 · Codex 수정 지시 (WBS 축 · fine-tuning 표현 · 신규 실측) | proposal-deck-presented.html(#262) · 9/4 발표 완료 |
| #137 | 완료 | 높음 | Todo | 닫기 (완료) | [작업] 빌드 실행 순서 결함 2건 수정과 생성물 커밋·정상 배포 | 9/3 네 단계 PASS 보고 · 독립 검수 · PR #141 머지 |
| #138 | 완료 | 중간 | Todo | 닫기 (완료) | 험지 4종이 전역 np.random 을 써서 env 밖 굽기가 재현되지 않는다 | flat-10m-spec20s README §4-3 · eval-protocol-v2 · eval_generalization.py:220 |
| #155 | 완료 | 높음 | Todo | 닫기 (완료) | [작업] 일정 허브 멘토링 D-day 주간 반복 반영 · 빌드 시점 고정값 제거 | hub3.py:296-401 · hub-schedule.html mentor-dday |
| #156 | 완료 | 높음 | Todo | 닫기 (완료) | [작업] 연구 허브 「후속 과제」 라벨 수와 칩 수 불일치 해소 · 상한 초과분 표기 | hub3.py:215 CHIP_MAX · build.py:920 chipcheck |
| #183 | 완료 | 중간 | Todo | 닫기 (완료) | [작업] 연구 허브 험지 카드 후속 과제 중복 제거 · 5열 배치 · 칩 작성자 시각 표기 · 미분류 8건 분류 | hub3.py:567 · :693 · terrain5.py:237 · 미분류 8→3 |
| #346 | 완료 | 높음 | Todo | 닫기 (완료) | 원장 관문 [3.8] 과 ledger-sync 봇의 경합으로 인한 배포 중단 | ledgercheck.py:69·121 · 원장 봇 매일 커밋 |
| #363 | 완료 | 중간 | Todo | 닫기 (완료) | [작업] 평가 프로토콜 정본 1장 작성 · 난이도 주축과 고정값 확정 | eval-protocol-v2 v2.1 §07 (⑧ ⑨ 없음) |
| #380 | 완료 | 높음 | Todo | 닫기 (완료) | [작업] authorcheck.py 의 ROLES.md 부재 시 진단문 유실 | cb4eaa97(#361) authorcheck.py:158·195-210 |
| #395 | 완료 | 높음 | Todo | 닫기 (완료) | [작업] 갤러리 컷 포스터 이미지 생성과 목록 지연 로딩 | 70030aad 포스터 생성 · gallery_manifest.py:549-556 · view 898-914 |
| #407 | 완료 | 중간 | Todo | 닫기 (완료) | [작업] 주간 다이제스트 2주 밀림 해소와 cron 밀림 내성 확보 | a6cf8843 월요일 되돌림 수정 · W36·W37 초안 (컨펌·W38~W40 남음) |
| #422 | 완료 | 중간 | Todo | 닫기 (완료) | [작업] 종합보고서와 평가 정본의 역할 분리 · 첫머리를 핵심 발견으로 | report/page.py:279·449·501 · 가리키는 절 번호 낡음 |
| #428 | 완료 | 중간 | Todo | 닫기 (완료) | [작업] 레시피 계보 기록 · A·B 출발점과 설정 diff | 9/17 계보·diff · 보고서 03절 · policy_provenance (A 설정 파일만 미확인) |
| #430 | 완료 | 높음 | Todo | 닫기 (완료) | [작업] 3DGS 지형 PoC · 스마트폰 영상 지면 메시화와 Isaac Sim Go2 보행 검증 | PR 437 · RESEARCH v1.4 · RESULTS v1.10 · Go2 보행 |
| #435 | 완료 | 높음 | Todo | 닫기 (완료) | [작업] gap 참여도 표시 정정 · 0.03 % 표본 숫자가 100 % 표본과 같아 보이는 문제 | gallery.js:181-190 · measure.py:292 (안 ② 는 의도적으로 열어 둠) |
| #441 | 완료 | 높음 | Todo | 닫기 (완료) | [작업] 명령 능력 복원 D 학습 · 정지·저속·회전 프로브 신설과 기준선 측정 | 20260918-D-axis1 · command-baseline · PR 444 |
| #452 | 완료 | 높음 | Todo | 닫기 (완료) | [작업] E 환경 설정과 Isaac Lab 등록 | gap_e_env_cfg.py · 20260920-E-axis1 · gallery/E |
| #454 | 완료 | 높음 | Todo | 닫기 (완료) | [작업] E 정책 비교 영상 13종 촬영 | 20260920-E-videos 13편 · gallery/E 30컷 |
| #456 | 완료 | 높음 | (보드에 없음) | 닫기 (완료) | [작업] F·G 학습 설정과 고리 도랑 지형 구현 및 기하 노출 측정 | gap_f/g_env_cfg · omni_gap_terrain · gap_exposure · 20260920-FG-exposure.json |
| #459 | 완료 | 높음 | Todo | 닫기 (완료) | [조사] 지각 논문 MARG · HiPAN · AME-2 정밀 검토 | RESEARCH-codex.md main · 137c6dfa |
| #462 | 완료 | 높음 | Todo | 닫기 (완료) | [작업] 정책 계보·판정 기준 2차 독립 감사 | AUDIT2-astra.md 「감사 완료」 a46fb689 |
| #464 | 완료 | 높음 | Todo | 닫기 (완료) | [작업] 학습 device 교란과 재현성 6차 독립 감사 | AUDIT6-astra-device.md 「검증 완료」 20a432fa |
| #466 | 완료 | 높음 | Todo | 닫기 (완료) | [작업] 학습량·발 보상·신경망 실험 우선순위 감사 | AUDIT8-plan.md 「검증 완료」 b23299b9 |
| #467 | 완료 | 높음 | Todo | 닫기 (완료) | [검증] 처음부터 학습 전환의 계보·통계·실험 조건 감사 | VERIFY-scratch-astra.md 「검증 완료」 01149e24 |
| #490 | 완료 | 높음 | Todo | 닫기 (완료) | [작업] MVP 발표 서사·목차 설계와 합의사항 기록 | PR #504 설계 문서 묶음 · 10/2 발표 |
| #494 | 완료 | 중간 | Todo | 닫기 (완료) | [승격 검토] inbox/meang/20260818-rough-terrain-rl-study.md | 대표 파일 이미 승격(terrain-rl-study-plan-0818.md) |
| #503 | 완료 | 중간 | In Progress | 닫기 (완료) | [조사] GitHub Star 저장소 용도와 발표 시각화 후보 정리 | STARRED-REPOS · RESEARCH-REPO-REFERENCES main(PR #504) · PR #517 머지되면 자동 닫힘 |
| #67 | 폐기 | 중간 | Todo | 닫기 (not planned) | [작업] 실패 지형 stepping_stones: 진단 -> 레시피 (오현민) | 담당 중단(9/16) · v2 에서도 디딤돌 실패 · v2c·v2d 중단 · #512 로 |
| #68 | 폐기 | 중간 | In Progress | 닫기 (not planned) | [작업] 실패 지형 pit: 진단 -> 레시피 (이민우) | pit 은 전용 레시피 없이 v1/v2 로 100% |
| #69 | 폐기 | 중간 | Todo | 닫기 (not planned) | [작업] 실패 지형 floating_ring: 진단 -> 레시피 (오흥재) | floating_ring 은 학습 없이 v2 로 99.7% |
| #80 | 폐기 | 중간 | In Progress | 닫기 (not planned) | [주간] W36 오흥재 개인 목표 | W36 개인 목표 · 주간 종료 · 주간 이슈 체계 끊김 |
| #81 | 폐기 | 중간 | Todo | 닫기 (not planned) | [주간] W36 맹라현 개인 목표 | W36 개인 목표 · 주간 종료 |
| #82 | 폐기 | 중간 | Todo | 닫기 (not planned) | [주간] W36 오현민 개인 목표 | W36 개인 목표 · 주간 종료 |
| #83 | 폐기 | 중간 | Todo | 닫기 (not planned) | [주간] W36 임석헌 개인 목표 | W36 개인 목표 · gap 은 v1/v2 로 풀림 |
| #84 | 폐기 | 중간 | Todo | 닫기 (not planned) | [주간] W36 이민우 개인 목표 | W36 개인 목표 · 9/4 제출 끝 |
| #103 | 폐기 | 중간 | In Progress | 닫기 (not planned) | [작업] 오늘 하루 진행 관리: 이슈 상태를 In Progress 로 유지하며 작업 | 9/1 하루 진행판 · 기간 끝 |
| #123 | 폐기 | 중간 | Todo | 닫기 (not planned) | 공개 문서 금액 표기 정정과 redact 금액 탐지 개선 | 9/4~9/5 대외비 범위가 대여 금액만으로 좁아짐(WORKFLOW.md:177 · scan.py:116) |
| #157 | 폐기 | 중간 | Todo | 닫기 (not planned) | [작업] 험지 원자료 CSV 열과 정본 요약의 최대 80 포인트 불일치 해소 · 판정 임계 표기 | 폴더 README 「규격 2 를 보라」(21748a5e) · DECISIONS.md:126 |
| #188 | 폐기 | 중간 | Todo | 닫기 (not planned) | [작업] 9/4 기획 발표 벡터 도해 4종 제작 | 9/4 발표 끝 · 벡터 도해 산출 없음 |
| #287 | 폐기 | 낮음 | Todo | 팀장 확인 | [계획] 발 높이의 상수에서 명령으로의 전환 설계 | 보상 쪽은 v2 feet_air_time 0.1 로 흡수 · 관측 확장은 10/6 결정과 안 맞음(추정) |
| #397 | 폐기 | 높음 | Todo | 닫기 (not planned) | [작업] 지형 집합과 모델별 학습 노출의 분리 | 9/12 팀장 확정: 경험 여부 딱지 안 붙임(#399 댓글) |
| #399 | 폐기 | 중간 | Todo | 닫기 (not planned) | [계획] 실패 지형 공략 뼈대의 N차 누적 전환과 연구 보드 축 재구성 | 커밋 0 · 10/6 v2c·v2d 중단 · 보행 개선은 #512 |
| #426 | 폐기 | 중간 | Todo | 닫기 (not planned) | [작업] 500 iter 실행 기록 복원 · 레시피 중간 단계 | 전제 바뀜(#428 9/17: A·B 는 NVIDIA 에서 1,500 iter) |
| #447 | 폐기 | 높음 | Todo | 닫기 (not planned) | [승격 검토] inbox/jay/20260916-3dgs-test/20260916_prompt_01.md | #500 과 중복 |
| #453 | 폐기 | 중간 | Todo | 닫기 (not planned) | [승격 검토] inbox/jay/20260920-E-run-status.md | 9/20 H 진행 스냅샷 · 연구 문서 아님 |
| #458 | 폐기 | 중간 | Todo | 닫기 (not planned) | [승격 검토] inbox/jay/20260921-two-axes-guide.md | 두 축 가이드 미승격 · 낡음(196행 철회됨) · v2 보고서 8~9절과 eval-protocol-v2 가 대신 |
| #465 | 폐기 | 중간 | Todo | 닫기 (not planned) | [판정] 후보 1 · v2b-r iter2500 · 축 2 첫 9/9 (확정 후보 아님) | 후보 v2b-r 은 9/29 foothold-v2 정본으로 대체 · 판정 기록 CANDIDATE-1.md |
| #468 | 폐기 | 낮음 | Todo | 팀장 확인 | [실험] 처음부터 학습 전환 · fs1·fs2 와 장치 교차 짝 | 1회차 끝 · 2회차 흔적 0 · v2 는 resume 계보 정본 · 10/6 재설계 · 팀장 확인 필요 |
| #492 | 폐기 | 중간 | Todo | 닫기 (not planned) | [승격 검토] inbox/meang/20260904-rails-난이도격자/20260904-rails-난이도격자.md | 승격된 rails-speed-tracking-diagnosis 7-1 에 들어감 · rails 99.7 % |
| #493 | 폐기 | 중간 | Todo | 닫기 (not planned) | [승격 검토] inbox/lim/20260910-최종 후보 선택.md | baseline 후보 선택이 v1(9/12) · v2(9/29) 배포로 대체 |
| #495 | 폐기 | 중간 | Todo | 닫기 (not planned) | [승격 검토] inbox/meang/20260910-레일즈-학습레시피.md | rails 레시피가 v2 로 대체 · 추가 학습 10/6 중단 |
| #497 | 폐기 | 중간 | Todo | 닫기 (not planned) | [승격 검토] inbox/oh/20260916-RL작업-상태정리-인계.md | 9/16 RL 인계(운영) · 승격 대상 아님 · 이슈만 닫음 |
| #501 | 폐기 | 중간 | Todo | 닫기 (not planned) | [승격 검토] inbox/jay/20260929-mvp-submission/CONTENT-MAP.md | MVP 제출 끝 · 운영 문서 |
| #506 | 폐기 | 중간 | Todo | 닫기 (not planned) | [승격 검토] inbox/jay/20260930-mvp-brand/HANDOFF.md | 운영 인계 문서 · 승격 대상 아님 · 추적은 #505 |
| #522 | 폐기 | 중간 | Todo | 닫기 (not planned) | [승격 검토] inbox/jay/20261007-wip-request/TEMPLATE.md | TEMPLATE 은 팀원용 양식 · 승격 대상 아님 |
| #122 | 진행 | 중간 | In Progress | In Progress | WBS 구현 단계 층 신설과 사람별 기여 축 | PR #166 wbs-official.md v1.2 · 단계 이름·개수 팀장 확정 전 · build_wbs.py 3층 없음 |
| #408 | 진행 | 중간 | Todo | In Progress | [작업] 빌드 입력 트리 단일화 · _lab-main 후보 제거와 전수 순회 자리 정리 | PR 448 · 474 · _lab-main 존폐 · collab_page.py:31 남음 |
| #463 | 진행 | 높음 | Todo | In Progress | [작업] 판정 코드에 CRITERIA v1.3 반영 · 제외 규칙 철회와 요약 병합 신원 검사 | 고칠 것 1 은 로컬 브랜치 fix/retract-stones-exclusion 00dabb26 에만 · main 그대로 |
| #505 | 진행 | 중간 | Todo | In Progress | [후속] 브랜드 영상 기존 자산 인계와 제작 재개 | 10/1 재개 · 13컷 대부분 미완 · 10/2 뒤 커밋 없음 |
| #511 | 진행 | 높음 | Todo | In Progress | [선행] 사이트 영상을 NAS 로 옮기고 웹은 그대로 보이게 (Vercel 무료 배포 저장소 10 GB 100 %) | 착수 · PLAN.md v0.1 · 서빙 경로 결정 대기 |
| #515 | 진행 | 중간 | Todo | In Progress | [덱 보강] 왜 필요한가 · 명확한 사용자 · 비즈니스 연결 · 서비스 앱 (MVP 피드백 · ASTRA-MVP 와) | 라현 PR #519 (서비스 방향 검토) · 덱 보강 자체는 아직 |
| #516 | 진행 | 높음 | Todo | In Progress | [설계] 세션·폴더·파이프라인을 한 공간으로: 공용 판 · 메모리 · 오케스트레이션 후보 + 지난 구조 회고 | 5번 super 진행 · 1~4번 손대지 않음 |
| #520 | 진행 | 높음 | Todo | In Progress | [요청] 10/7 팀원 진행 상황 보고 · 무엇을 · 기술적으로 어떻게 · 어디까지 | 양식·공지 머지 · 제출 0/4 (마감 10/8 18:00) |
| #6 | 대기 | 중간 | In Progress | Todo 유지 | [작업] 도구 백과 · 우리가 쓰는 도구들을 그림과 함께 | tools.html 없음 · 8/28 범위 재정의 뒤 커밋 0 |
| #28 | 대기 | 낮음 | Todo | 팀장 확인 | [작업] RoboGauge 공개 정책 4종: 우리 평가에 붙이기 | 매핑·로드 검증만 끝남 · 본 벤치마크 없음 · 담당(현민) 9/16 미착수 · #512 흡수 여부 팀장 판단 |
| #30 | 대기 | 중간 | Todo | Todo 유지 | [인프라] Vaultwarden 개통 + NAS 폴더 구조 | Vaultwarden · NAS 폴더 체크 전부 미완 · #511 과 겹침 |
| #31 | 대기 | 중간 | Todo | Todo 유지 | [작업] 우분투 전환 후 DDP 재측정 | 우분투 이관 선행 · DDP 실측 없음 · 22.04 → 24.04 로 다시 써야 함 |
| #88 | 대기 | 중간 | Todo | Todo 유지 | [작업] 강의 저장소 감시가 알림만 한다. 미러까지 하게 | lecture-watch 미러 안 함 · 안 A 팀장 결정 필요 |
| #96 | 대기 | 중간 | Todo | Todo 유지 | [작업] 멘토링 질문 사전 취합 · 노션 설계안의 빠진 조각 | 3번 일지 표 없음 · 멘토 교체로 질문 낡음 · 9/1 뒤 멈춤 |
| #97 | 대기 | 높음 | Todo | Todo 유지 | [작업] 기술 허브 확장 3편 집필: Isaac Lab 실전 · MuJoCo · Omniverse | 가이드 세 편 없음 · hub-tech 「확장 예정」 |
| #102 | 대기 | 중간 | Todo | Todo 유지 | [작업] 일정 허브 대시보드화: 전체 일정 + 개인 일정 도식 · 프로젝트 보드 연동 | 일정 허브 19주 타임라인·보드 연동 없음 · gh project 권한 막힘 뒤 멈춤 |
| #124 | 대기 | 중간 | Todo | Todo 유지 | 저장소 역할 재정의를 운영 문서에 반영 (lab 개발 · go2 공개 승격) | README · COLLAB · AUTOMATION 이 옛 모델 · lab PUBLIC 전환으로 전제 재검토 필요 |
| #126 | 대기 | 중간 | Todo | Todo 유지 | 실험 템플릿 lab 이관과 「승격」 용어 분리 (저장소 재정의 여파) | 02-experiment.yml 없음 · AUTOMATION.md:63 「실험 기록 -> go2」 |
| #148 | 대기 | 중간 | Todo | Todo 유지 | [승격 검토] inbox/jay/20260903-report-v2-개정안.md | 9/14 팀장 「보류」 · REPORT.md v1.0 · 이후 결정 반영해 다시 써야 함 |
| #253 | 대기 | 높음 | Todo | Todo 유지 | [작업] 웹에 남은 ASCII 도식 3블록의 SVG 전환 | ascii_grandfather.txt 에 tech-cv · notice-20260826 남음 |
| #316 | 대기 | 중간 | Todo | Todo 유지 | [작업] 워크플로 15군데 em dash 정리와 관문 확장 | 5번 실물 확인 · 6번 promote.yml ASCII 관문 남음 |
| #341 | 대기 | 높음 | Todo | Todo 유지 | [작업] 문서 그래프 표의 인용 절단이 백틱 짝을 깨뜨린다 | doc-graph.md 백틱 홀수 행 4개 |
| #350 | 대기 | 중간 | Todo | Todo 유지 | [작업] 평가 하네스가 죽어도 종료코드 0 을 내는 문제 | eval_generalization.py 종료 처리 그대로 |
| #354 | 대기 | 높음 | Todo | Todo 유지 | 코드블록 위젯 CSS 의 토큰 밖 색상 19개 · 배포본 130장 공통 | brand_grandfather.txt hex 20(늘어남) |
| #364 | 대기 | 높음 | Todo | Todo 유지 | [작업] 벤치마크 관문의 성공 조건과 종료코드 계약 문서화 | 종료코드 계약 문구 없음 |
| #365 | 대기 | 중간 | Todo | Todo 유지 | [작업] 팀 제출·완결 조건의 문서화 · 개인 위키 게재의 지위 정리 | 「위키 게재는 완결 조건이 아니다」 문구 없음 |
| #366 | 대기 | 중간 | Todo | Todo 유지 | [작업] 용어 범위 · KPI 고정 시점 · PRD 근거 정정 셋의 결정 로그 반영 | DECISIONS 에 해당 행 없음 · KPI 고정은 기록 의미만 |
| #367 | 대기 | 높음 | Todo | Todo 유지 | [작업] RoboGauge 점수표 기여 철회의 문서 반영 · 한 문서 안 두 판 정리 | go2-pretrained-policies.md:17 「처음 올릴 수 있다」 남음 |
| #368 | 대기 | 중간 | Todo | Todo 유지 | [작업] 발표 서사 정본과 계획 WBS 세로축의 결정 로그 반영 | 스토리라인 정본 등 없음 · 발표 서사는 기록 의미만 |
| #369 | 대기 | 높음 | Todo | Todo 유지 | [작업] 관문 코드에만 사는 웹·운영 규칙 넷의 문서 이관 | DESIGN-GUIDE.md:32 localStorage 등 그대로 |
| #370 | 대기 | 높음 | Todo | Todo 유지 | 배포본 diff 에서 빌드 시각을 걷어낸 «진짜 변경» 수 표시 | 「진짜 변경」 집계 없음 |
| #374 | 대기 | 높음 | Todo | Todo 유지 | [작업] deadline-alert.yml 보드 조회의 쪽 나눔과 훑은 건수 표기 | deadline-alert.yml:38 · :87 그대로 |
| #375 | 대기 | 높음 | Todo | Todo 유지 | [작업] weekly-report.yml 의 전송 판정·쪽 나눔·바이트 자르기·상수 output 정리 | weekly-report.yml 그대로 |
| #376 | 대기 | 높음 | Todo | Todo 유지 | [작업] lecture-watch.yml 스냅샷 저장 시점의 알림 뒤 이동 | lecture-watch.yml 10/6·10/7 failure |
| #377 | 대기 | 높음 | Todo | Todo 유지 | [작업] issue-dates.yml 필드 id 미확보 시 성공 표기 차단 | issue-dates.yml 그대로 (48·78·87행) |
| #378 | 대기 | 높음 | Todo | Todo 유지 | [작업] merge-on-comment.yml 텔레그램 HTTP 코드 판정 추가 | merge-on-comment.yml:116 HTTP 판정 없음 |
| #396 | 대기 | 중간 | Todo | Todo 유지 | [작업] 대조컷 선택 정책의 코드화와 색인 기록 | selection_policy 코드 0건 |
| #398 | 대기 | 중간 | Todo | Todo 유지 | [작업] 갤러리 컷의 안정 식별자와 재촬영 이력 기록 | clip_id·재촬영 이력 필드 0건 |
| #404 | 대기 | 높음 | Todo | Todo 유지 | report-v1 의 검색 단추·바닥 도장 누락 해소와 완비 관문 예외 철회 | completecheck.py:281-295 report-v1 예외 그대로 |
| #423 | 대기 | 중간 | Todo | Todo 유지 | [작업] 「판」 잔여 74곳 정리와 예외 규칙 확정 | 74곳 정리 끝 · 「숫자+판」 관문 미착수 · 「100판」 재유입 |
| #427 | 대기 | 중간 | Todo | Todo 유지 | [작업] 40일 넘게 안 고친 「지금을 말하는 문서」 3장 갱신 | brief 에 foothold-v2 0건 · setup.base 9/13 뒤 수정 없음 |
| #436 | 대기 | 낮음 | Todo | 팀장 확인 | [승격 검토] inbox/jay/20260904-launch/keyvis/20260914-session1/astra/chars | 승격 결정 없음 · 런칭 키비주얼 메모 (보류 종결 후보) |
| #438 | 대기 | 낮음 | Todo | 팀장 확인 | [작업] 트윈 렌더 마스터 14컷 전멸 · CUDA_VISIBLE_DEVICES 로 인한 RTX 렌더러 GPU 스킵과 프레임  | render_masters 미커밋 · 시연물 FINAL 로 · ACC 트윈 결정으로 폐기 후보 |
| #442 | 대기 | 중간 | Todo | Todo 유지 | [승격 검토] inbox/jay/20260918-v2-command-restore.md | 승격 결정 없음 · rl-lineage.md:90 인용 (보류 종결 후보) |
| #443 | 대기 | 중간 | Todo | Todo 유지 | [작업] 학습 명령 범위와 평가 범위 대조 관문 · 범위 밖 평가점 부재 시 배포 차단 | range_gate.py 있으나 빌드 미연결 · 성적표 분리 미착수 |
| #445 | 대기 | 중간 | Todo | Todo 유지 | [승격 검토] inbox/jay/20260916-3dgs-test/DESIGN-real-to-sim.md | DESIGN-real-to-sim.md 검토중 v1.5 · ACC 트윈 직결 |
| #449 | 대기 | 중간 | Todo | Todo 유지 | [승격 검토] inbox/jay/20260918-why-gap-fell-rails-rose.md | 승격 결정 없음 · rl-lineage.md:127 인용 (보류 종결 후보) |
| #450 | 대기 | 중간 | Todo | Todo 유지 | [승격 검토] inbox/jay/20260919-E-design.md | 승격 결정 없음 · E 학습·평가 끝 (보류 종결 후보) |
| #455 | 대기 | 중간 | Todo | Todo 유지 | [승격 검토] inbox/jay/20260920-FG-design.md | 승격 결정 없음 · F·G 끝 · rl-lineage.md:148 인용 (보류 종결 후보) |
| #457 | 대기 | 중간 | Todo | Todo 유지 | [승격 검토] inbox/jay/20260921-v2-design.md | 승격 결정 없음 · v2a·v2b 설계 · v2 배포됨 (보류 종결 후보) |
| #469 | 대기 | 중간 | Todo | Todo 유지 | [평가] 축 2 문턱이 잡음보다 좁다 · n=64 에서 fell_ratio 0.10 판정 재설계 | 문턱 verdict_manifest.py:81 그대로 · 분석·재측정만 함 |
| #491 | 대기 | 낮음 | Todo | 팀장 확인 | [승격 검토] inbox/meang/20260909-영상재현-외부문헌/20260909-영상재현-외부문헌.md | 승격 결정 없음 · 쓸모 미확인 |
| #496 | 대기 | 중간 | Todo | Todo 유지 | [승격 검토] inbox/oh/20260826-cv-단계별-계획과-환경.md | B/인지 계획 · 승격 결정 없음 · NAV 11/7 까지 유효 |
| #498 | 대기 | 중간 | Todo | Todo 유지 | [승격 검토] inbox/meang/20260916-3DGS-실측정리.md | 3DGS 실측 · ACC 트윈(#514)과 이어짐 · 승격 결정 없음 |
| #500 | 대기 | 중간 | Todo | Todo 유지 | [승격 검토] inbox/jay/20260916-3dgs-test/RESEARCH-3dgs-terrain.md | 3DGS 결과 · ACC 트윈과 관련 · 승격 결정 없음 |
| #502 | 대기 | 중간 | Todo | Todo 유지 | [승격 검토] inbox/jay/20260921-perception-research/BRIEF-codex-astra.md | 작업서는 승격 대상 아님 · SYNTHESIS·NETWORK-anatomy·CRITERIA 는 #512 에 쓰일 자료 |
| #512 | 대기 | 중간 | Todo | Todo 유지 | [이후 과제] 험지 극복 · 일반화 보행 모델: star 논문 + 탐색 → 직접 구현 → 우리 시스템 적용 판단 (ASTRA- | 생성 뒤 활동 0 · PR #517 만 열림 |
| #513 | 대기 | 중간 | Todo | Todo 유지 | [이후 과제] 앱 + 전체 시스템 아키텍처: ROS2 - SLAM - Nav2 - 경로 탐색 · 미션 앱(로봇↔사용자) · 빠 | 생성 뒤 활동 0 |
| #514 | 대기 | 중간 | Todo | Todo 유지 | [이후 과제] 디지털 트윈 방법의 실제 적용 (ASTRA-MVP 와) | 생성 뒤 활동 0 · ACC 트윈과 관련 높음 |
