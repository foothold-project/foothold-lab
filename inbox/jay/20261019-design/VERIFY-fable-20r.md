> 분류: A/정책학습 · 설계 반영 (fable 20r · sonnet DESIGN-policy-node 7b5cf869 공식 경로 조사 · 통신 관제 체크리스트 · 판단층 날짜를 42 · 23 · 50 · 31 에)
> 작성: fable 세션 · lead 의뢰 20r · 10/20 13:5x
> 근거: sonnet-code 사본 커밋 7b5cf869 `foothold_s2/deploy/DESIGN-policy-node.md` §1 · §2 · §4 · §5 · §7 · §8(`git show` 로 읽음) · lead 20r 의뢰문(체크리스트 9 항 · 장면 4 · 31 날짜) · 설계 42 · 23 · 50 · 31 · 70 §1 의 기존 문장
> 요지: lead 지시 4 항(공식 경로 · 관측 · 상태기계 · FIXSTAND 자세)을 42 §1.2 새 절 · §2 · §5, 23 §1 · §4 · §5 · §8 · §10, 50 S1-x 행에 적고, 42 §1.1 체크리스트를 9 항 · 장면 4 로 채우고, 31 §3 날짜를 채웠다. 시험 방법 · 통과 기준 칸과 「제때」 정의는 가정으로 표시. sonnet 의 공식 저장소 조사(Ubuntu 전제 · 관측 목록 · FixStand 값 · 관절 순서)는 fable 이 재지 않았다(미재측 · sonnet 근거 그대로 인용)
> 상태: 완료 · 미커밋(lead 커밋) · 코드 · 학습 · GPU · Kit 없음

# VERIFY-fable-20r · sonnet 정책 노드 조사 · 체크리스트 · 판단층 날짜 반영

## 1. 반영 표

| # | lead 지시 | 반영 자리 | 무엇을 |
|---|---|---|---|
| (1) | 공식 경로 = Isaac Lab → unitree_mujoco sim2sim → ctrl --network eth0, unitree_sdk2 는 Ubuntu 전제 → sim2sim · sim2real 은 Linux 이전 뒤 | 42 §1.2 표 「공식 경로」 행 · §5 선행 조건 새 행 · 23 §1 · §5 1 항 · 50 S1-x 행(「Linux 에서」) | Linux 이전 날짜는 70 §1 의 10/22~23 을 그대로 가리킴. Windows 네이티브 불가 · WSL2 미확인은 sonnet §1 그대로 |
| (2) | 공식 배포 관측에 base_lin_vel · 높이 스캔 없음 → 실기에는 우리 정책 노드, 공식 ctrl 은 형식만 참고 | 42 §1.2 「공식 배포 관측」 · 「우리 경로」 행 · 23 §1 · §8 1 항 | deploy.yaml 필드 · policy.onnx · 관절 순서 FR FL RR RL(SDK) ↔ Isaac 변환. 공식 C++ ctrl 이 495 이력 입력을 읽는지 미확인(23 §10) |
| (3) | 상태기계 PASSIVE → FIXSTAND → POLICY → HOLD → SPORT(실기만) → DAMP(평지만), deadman 0.3 s · hb 1.0 s 는 가정 | 42 §1.2 「상태기계」 행 · §2 새 bullet · 23 §4 새 행 · deadman · heartbeat 행 출처 칸에 「가정」 | HOLD · SPORT · DAMP 를 23 §4 후보 ① ② ③ 과 같은 것으로 묶음 |
| (4) | FIXSTAND 목표 = 우리 default_joint_pos(공식 0.0/0.8/−1.5 와 다름) | 42 §1.2 · §2 · 23 §4 | 우리 값은 sonnet §4 표(Isaac Lab Go2 hip ±0.1 · thigh 0.8/1.0 · calf −1.5) 인용 |
| 체크리스트 | 9 항 · 장면 4 | 42 §1.1 표 둘(C1~C9 · 장면 1~4) · 묶음 규칙 · 42 §4 측정값 흐름 한 줄 | 항목 · 장면은 lead 문구 그대로. **시험 방법 · 통과 기준은 fable 가정**(2 절) |
| 31 날짜 | 1 단계 11/3~11/16 · 지연 측정 첫 주 · 2 단계 관문 11/17(조언 제때 ≥ 95 % · 규칙보다 위험 장면 더 잡음) · 시뮬 11/18~24 · 실기 11/25~ · 3 단계 11/30 뒤 | 31 §3 표 마지막 열 4 칸 · 단계별 권한 문단 · §10 | 20q 의 「(lead 날짜)」 자리 0 개 남음(확인) |

4 파일 65 + / 20 − · em dash 0 · LF · 상태 줄 stamp(42 · 23 · 31 은 20q 뒤에 20r, 50 은 20r 만).

## 2. 가정으로 표시한 것 (lead · 현민 확정)

- 42 §1.1 C1~C9 의 시험 방법 · 통과 기준 칸 전부. 설계에 이미 있는 값만 썼다: deadman 0.3 s · hb 1.0 s(23 §4 · 이제 가정) · ±0.1 s(H42-4) · 명령 상한 0.3 m/s(42 §2) · T0 ②(리모컨 · SDK 미확인). 지연 문턱 · 정지 거리 기준 · 배터리 여유는 「기준은 lead」 로 비워 둠.
- 장면 날짜: 1 · 2 는 「Go2 도착 첫 주(42 §5)」, 3 은 lead(무대 예행 일정), 4 는 각 장면에서 1 회.
- 「④ 통과 전 T6 금지」(20q 가정 유지).
- 31 2 단계 관문의 「제때」 시한(§6 판단층 허용 지연 기준인지)과 위험 장면 집계 방식.

## 3. 미재측 (sonnet 조사를 그대로 인용한 것)

sonnet 7b5cf869 §1 · §2 · §4 의 근거는 「공식 저장소 얕은 clone(unitree_mujoco 1eb6642 · unitree_sdk2 d1abf00 · unitree_sdk2_python 814556d · unitree_rl_lab 4960b84)」 이다. fable 은 그 clone 을 열지 않았다. 재야 할 것: unitree_sdk2 README 의 OS 줄, `unitree.py` 의 `joint_sdk_names` 순서, `State_RLBase.cpp` 의 FixStand `qs` · `bad_orientation` 값, `observation_manager.h` 의 관측 목록 · `history_length`. 설계에는 전부 「sonnet 7b5cf869」 출처로 적었다.

## 4. 기록 (판정 아님)

- 7b5cf869 는 sonnet SC-6 커밋(「정책 노드 설계 초안 · Windows 가능 여부 판정」). 문서 상태 줄은 「초안 · lead 검토 전 · 실행한 것 없음」.
- 13 §6 수출 행(ONNX → Orin NX TensorRT)은 lead 범위 밖이라 안 고쳤다. deploy.yaml 내보내기(sonnet §4)를 13 §6 에 적을지는 lead 판단.
- 미커밋(lead 커밋) 20 파일: 설계 12 · 13 · 14 · 15 · 16 · 17 · 18 · 52 · 42 · 23 · 41 · 31 · 53 · 90 · 50 + VERIFY-fable-20m · 20n · 20o · 20q · 20r.
- 코드 · 학습 · GPU · Kit · 커밋 없음.
