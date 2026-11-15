> 분류: A/평가 · ASTRA 의뢰 17e · CMD-R 미경험 진단 재검사기 · v4 · full 기동 여부
> 작성: 오흥재 (lead 세션 · Claude 작성) · 2026-10-13 23:30
> 근거: VERIFY-astra-17c.md §2.4 · §5 · §6 · VERIFY-astra-17d.md §3 「0 절의 운영 판단」 · night-tools-20261013/uncr_v4/ (사본 · SHA256SUMS · 재검사 보고 사본)
> 요지: 17c 가 요구한 「동결 묶음 재검사 → 진단 보고 → 묶음에 연결된 관문 → full 여부」 중 앞의 셋을 만든 판이 맞는지, 그리고 GPU 1 에서 full 을 지금 띄워도 되는지 판정해 달라
> 상태: 의뢰

# ASTRA 17e · 미경험 진단 재검사기 · v4 · full 기동 여부

## 답하는 자세 (팀장 지시 · 모든 사항에 적용)

비판적이면서도 냉정하고, 현실적이면서도 아주 전문성이 높은, 이 분야를 평생 탐구한 전문가로서 답해 주십시오. 하위 작업과 lead 가 시험을 통과시켰다고 해서 맞다고 가정하지 마십시오.

## 1. 그 사이 일

- 20:08 에 lead 세션이 사용 한도로 멈췄고, 하위 작업 넷이 20:15 무렵 중간에 끊겼습니다. 23:30 에 다시 이었습니다. 그동안 GPU 1 은 19:28 부터 비어 있었습니다 (lead 실수: 한도 해제 뒤 자동 재개 장치를 걸지 않음).
- GPU 0 의 1043 학습은 그대로 돌았습니다 (23:29 기준 off 23,413 / 24,000).
- `out_uncr/STOP` 은 19:28 에 lead 가 만든 그대로 있습니다. full 은 그 전에 두 실행 (부모 · off 의 discrete_obstacles · fwd05) 만 돌았습니다.

## 2. 검사할 것 (사본과 해시: `night-tools-20261013/uncr_v4/SHA256SUMS.txt` · 실행본은 `_eval/` 같은 이름)

| 파일 | 하는 일 | 하위 작업 보고 |
|---|---|---|
| `uncr_revalidate.py` | 동결 묶음 재검사. 채널 0 ~ 10 필수 · 11 지면 높이 추정. 판정 구간 = 시작 ~ 낙상 직전. invalid / hold / valid. 지문 형식 먼저 · 짝 비교에 env_origins · traj[0] · 수집 코드 해시. USD 는 경로마다 루트 아래. stamp 를 덮지 않고 지금 해시를 옆에 · q_post 는 「출처 미확인」 과 재생성 바이트 대조 | 시험에 포함 |
| `unseen_driver_cmdr_v4.py` | post 단독에도 manifest · full 은 `--reval` 보고의 묶음 해시 · 재검사기 코드 · diag 7 valid · 수집 코드 · 체크포인트 동결본과 묶임 (diag_gate 불리언은 안 읽음) · CODE 에 q_post · 재검사기 · 시작 · 띄우기 전 · 실행 뒤 · 끝 대조 · scan_dirs 에 out_branch · 재사용은 재검사 valid 만 | 시험 46/46 · 변이 35/35 ALL CAUGHT |
| `revalidate-20261013-201422.json` | 실제 out_uncr 재검사 보고. 입력 253 개 · 묶음 해시 e5597517…ef2b58 | diag 7 칸 valid · 21 실행 valid (hold 0 · invalid 0) · 통과 · 생존 수가 v3 집계와 같음 · on/gap 의 채널 11 NaN 193 개는 모두 낙상 뒤라 valid · 지금 q_post 로 다시 만든 episodes · cells 가 저장본과 바이트 같음 · full 의 discrete_obstacles/fwd05 는 on 이 없어 incomplete |

lead 재실행 (23:31): `test_uncr_v4.py` 46/46 PASS · 재검사 보고의 묶음 해시 e55975172405901a0178a8e2bd3541ce7e13b118d0a9ab723fb6028d69ef2b58 를 파일에서 직접 읽어 확인.

## 3. 물음

1. 17c §2.4 의 P1 셋 (post 단독 거짓 완료 · 궤적 · 지문 내용 미검사 · 오래된 full 관문) 과 §5 출처 문제가 이 판에서 실제로 막히나. 사본에서 반례를 다시 걸어 보아 주십시오.
2. 재검사 보고 (21 실행 valid) 를 「학습 시드 1042 의 부모 · off · on 조건부 회귀 진단 7 칸 확정」 근거로 써도 되나. 쓸 수 있는 문장 범위.
3. **GPU 1 에서 full (나머지 25 칸 × 3 모델) 을 지금 띄워도 되나.** v4 는 실행 관문 v2 (`isaac_slot.py`) 와 격리기 v2 (`usd_isolate_run.py`) 를 그대로 부릅니다. 17c 가 짚은 v2 관문 결함 (경로별 판정 · 94 가 자식 종료 뒤 · registry 경합) 은 v3 로 고치는 중이며 아직 검사 전입니다. 이 Go2 URDF 경로에서는 loader 격리가 실제 23 실행에서 확인됐습니다. v2 로 full 을 띄워도 되는지, 아니면 v3 검사 (17f 예정) 뒤로 미뤄야 하는지 판정해 주십시오. 띄운다면 붙일 조건.
4. lead 가 놓친 것.

## 결과

- `inbox/jay/20261012-arch-discussion/VERIFY-astra-17e.md` 한 파일. 첫 줄은 한 문장 판정 (full 기동 가능 · 고쳐서 기동 · 기동 불가).
- 표기: 확인됨 · 추정 · 미확인.

## 지킬 것

- 코드 · 파일을 고치지 말고, GPU · Isaac 실행을 하지 마십시오. 돌고 있는 GPU 0 학습 · `out_uncr` · `out_branch` · STOP · 잠금 · registry 를 건드리지 마십시오 (읽기는 됩니다).
- CPU 시험은 임시 폴더에서만 하고 끝나면 지워 주십시오. 커밋 · push 를 하지 마십시오. em dash 를 쓰지 마십시오.
