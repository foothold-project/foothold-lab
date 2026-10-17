> 분류: A/정책학습 · ASTRA 의뢰 · 17al · 7차 A3.4 기록으로 B 지도 입력 증거가 학습 허용에 충분한지
> 작성: 오흥재 (lead 세션 · Claude 작성) · 2026-10-17 12:35
> 근거: 7차 실제 실행 `s2_lab/s2_step19_run/s2_runs/live-20261017-121223/` (12:12:23 ~ 12:13:09, 46.4 초) · `night-tools-20261013/s2_stage0_first_collection/attempt7_analysis_output.txt` · `VERIFY-astra-17ak.md` 2 절 (학습 조건: B 가 소비하는 좌표 · offset · hit/miss · pose/yaw · 시간/reset · 지형 대응이 유효하면 탐색 short 로 자동 전환) · `VERIFY-astra-17aj.md` 3 절 (고정 자세 조건 결과 뒤 넓히지 않기)
> 요지: 7차에서 USD 증거가 통과했고 지도 값은 정답표와 어긋남이 없다(경계 2173/2173 · 면 hit 마스크 불일치 0 · 세계 높이 최대 차 4.6e-06 m). 남은 HOLD 는 사전 등록한 「첫 16 걸음 고정 자세」 하나(와 그에 걸려 따라 붙는 case_assignment). 이것이 B 입력 증거를 막는지, 막는다면 최소로 무엇을 더 재야 하는지 묻는다
> 상태: 의뢰 (ASTRA 는 평생 탐구한 전문가로 · 비판적 · 냉정 · 현실적으로. 팀장은 학습 시작이 지연되어 격분했다. 허용 · 보류와 이유를 맨 위에 짧게. 보류하려면 구체 사고와 비용으로)

# ASTRA 17al 의뢰

## 1. 사실 (원자료는 lead 가 읽은 것, ASTRA 가 다시 읽는다)

- `check.json`: 판정 HOLD, 이유 `case_assignment`, `fixed_pose_evidence` 둘. `meta.json`: `mesh_collision_verified true`, `fixed_pose_verified false`, 장치 결박 verified, `terrain_assignment` 조건은 통과(HOLD 이유에 없음). 계수: live_steps 240 · fixed_steps 16 · miss 5120(gap 두 환경에서 각 2560) · boundary 2173 · deep_finite 5120.
- 코드상 `case_assignment` 은 `meta.cases` · `terrain_assignment_verified` · `mesh_collision_verified` · `fixed_pose_verified` 중 하나라도 true 가 아니면 걸린다. 지금은 `fixed_pose_verified` 만 false 다(lead 해석, 확인 요청).
- `fixed_pose_evidence`: 첫 16 걸음 root 위치 최대 변화 0.0080 m, root quaternion 성분 0.0616, scanner 위치 0.0080 m (허용 0.002).
- CPU 분석: 경계 지점 2173 = 2173, 환경별 불일치 0, 면 hit 마스크 불일치 0, 세계 높이 정답 최대 차 4.6e-06 m (2 mm 초과 0), episode 128 에서 8 환경 모두 reset, 센서 step = sim step.
- USD: 변환 1회(진입), 성공 1, `usd_evidence.json` 작성, 출력 usd 5개 해시.

## 2. 물음

1. 위 사실로 17ai 4절의 B 지도 입력 증거 다섯 줄(187 ray 순서 · offset/origin · yaw/pose 이동 · 실제 충돌 대비 hit/miss · 시간/부분 reset)이 어디까지 닫혔는지, 닫히지 않은 줄이 있다면 어느 줄이고 무엇이 더 필요한지.
2. 「첫 16 걸음 고정 자세」 실패가 B 입력 유효성에 어떤 영향을 주는지. 지도 값은 매 걸음 실제 pose 로 계산해 정답표와 대조했는데(세계 높이 차 4.6e-06 m), 로봇이 처음 16 걸음 동안 8 mm 움직인 것이 B 입력을 무효로 만드는가, 아니면 고정 자세 하위 시험만 실패한 것인가. 허용치는 넓히지 않는다.
3. 탐색 short(A/B 각 2,000 update)로 넘어가는 데 필요한 남은 선행 항목을 번호로. 특히 노드 2(합성 배관)와 N=1,024 자원 판독 이외에 막는 것이 있는지. 노드 3(평가기)과 4(발 광선)는 선행이 아니라고 lead 는 본다(17ak 2절), 틀렸는지.
4. 17ak 의 첫 노드 canary(무인 감시 canary)는 학습 전에 반드시 필요한지, 참석 모드로 이어 갈 때(현 코드)는 어떻게 되는지.

## 3. 형식

`VERIFY-astra-17al.md`. 맨 위에 「닫힘 · 부분 · 불충분」 한 줄과 이유, 아래에 물음별 답.
