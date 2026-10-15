> 분류: A/정책학습 · Codex Worker 작업서 (sol) · S2 B 번들 실기동 경로 (학습 진입 + 기동기 동등성)
> 작성: 오흥재 (lead 세션 · Claude 작성) · 2026-10-15 14:33
> 근거: sol 의 `REPORT-s2-step4.md` (B CPU 단위 19/19) · `VERIFY-astra-17v.md` · 오늘 GPU 첫 두 시도의 실패 원인 (아래) · `VERIFY-astra-17aa.md`
> 요지: 팀장이 「지형 지도를 주고 돌려 보기」 가 하루 반 동안 한 번도 안 돈 것에 크게 화가 났다. sol 은 한도가 100 % 로 돌아왔다. **B 번들의 실기동 경로**(Isaac 안에서 도는 학습 진입)를 지금 병렬로 완성해 0 단계가 끝나자마자 smoke 가 뜨게 한다. GPU 는 건드리지 않는다
> 상태: 작업 지시 (GPU · Isaac 기동 금지 · 승인 json 은 ASTRA 가 낸다)

# sol 작업서: S2 B 실기동 경로

## 0. 지킬 것

- GPU · Isaac · 실제 `_eval` 슬롯을 **띄우지 않는다.** CUDA_VISIBLE_DEVICES=-1, 해석기 `C:/Users/AI-WS01/anaconda3/envs/isaac311-moects/python.exe -B`. 새 작업 사본은 `codexE/s2_step5/` (기존 `s2_step4/` · `s2_step4a2_frozen/` · 저장소 `s2_step4a3/` 는 고치지 않는다). 비판적이고 냉정한 전문가로, 정상 시험을 먼저 통과시킨 뒤 변이가 지정 첫 FAIL 라벨과 같을 때만 CAUGHT. em dash 금지. 저장소 공유 체크아웃 쓰기 금지(보고서와 사본은 codexE 에).
- 팀장 지시 요지: 실험이 안 도는 시간이 가장 큰 손해다. 완벽한 설계보다 **0 단계 직후에 smoke 가 실제로 뜨는 것**이 먼저다. 단, 검증을 빼지는 않는다.

## 1. 오늘 GPU 첫 기동 두 번이 가르쳐 준 것 (이 세 줄은 반드시 B 에 반영)

1. **환경 변수:** Kit 는 `OMNI_KIT_ACCEPT_EULA` 가 없으면 stdin 으로 EULA 를 물어 자식이 죽는다. 동작하던 기동기(`_eval/unseen_driver_cmdr_v6.py:105`, `_eval/run_e2.sh:18`)는 `OMNI_KIT_ACCEPT_EULA=YES` · `PYTHONUNBUFFERED=1` · `CUDA_DEVICE_ORDER=PCI_BUS_ID` · `CUDA_VISIBLE_DEVICES` 를 준다.
2. **Kit 앞 선적재:** `h5py` · `torch` · `tensordict` 를 `isaaclab.app` **앞**에서 불러와야 한다(Kit 뒤에 `tensordict._C` 를 불러오면 접근 위반). 선례 `_eval/q_eval.py:24-25` · `ce12/dump_native_v2.py:32-33` · `branch/branch_run.py:45-46`.
3. **「기동기 동등성 표」 를 CPU 로 먼저 만든다.** 1043 쌍 학습을 실제로 돌린 `_eval/branch/branch_run.py` 와 `isaac_slot_v3.py` 경로가 자식에게 주는 **환경 변수 · 선적재 · argv · 작업 폴더 · stdin 처리 · AppLauncher 인자**를 한 줄씩 적고, B 의 학습 진입이 주는 것과 나란히 놓아 빠진 줄이 0 임을 시험으로 보인다. (오늘 두 번 죽은 것이 모두 이 표의 빈칸이었다.)

## 2. 만들 것 (우선순위 순)

1. **동등성 표 + 시험** (위 3). 빠진 줄을 시험이 잡는 변이도 만든다.
2. **학습 진입 실기동 경로** `s2_train_entry` 의 live 경로를 HOLD 에서 풀되 승인 json 이 없으면 시작 안 함: 선적재 → AppLauncher(headless, `--device cuda:0`) → 설정된 8,192 가 아닌 **N=1,024 환경** 구성(`s2_env_config_17v.py` 재사용, 희소 지형 gap 15 % · stones 15 %) → E1 부모 `model_20000.pt` 로드(SHA `c8951b79…`) → A(지도 입력 상수) / B(이상적 지도) 중 `--arm` 한 개 → PPO 업데이트 → 체크포인트 0 / 200 / 2,000 / +500 경계 → `chain receipt`. **한 프로세스는 한 GPU, 한 arm**(DDP 아님).
3. **기동 래퍼:** 위 진입을 `night-tools-20261013/s2_step4a4_unattended/` 의 A4 r2(gate + watchdog v2 + launcher, 단 17z 보류 중이라 **참석 모드**로도 쓸 수 있게)로 띄우는 연결. 감독기는 증분마다 heartbeat 를 쓰고 STOP 을 읽는다. A4 의 잘못(신원 불명 종료 · 거짓 가족 영수증)은 r2 에서 고쳤으므로 그 규칙을 따른다.
4. **smoke 시험안(CPU 에서 알려진 답으로):** 200 update 에서 두 arm 의 loss/KL/엔트로피가 유한하고 부모 정책의 행동이 arm A 의 상수 지도에서 부모와 같음(제로 초기화된 actor 열)을 CPU 대역으로 보인다. 실제 Isaac 에서 볼 것은 「미확인」 으로 남긴다.
5. **보고:** `REPORT-s2-step5.md` 와 #550 댓글 초안(미게시), 해시 목록. 정상 PASS 라벨 수와 변이 CAUGHT/전체를 숫자로, 처음 실패도 함께.

## 3. 끝나면

lead 가 재실행해 확인하고 ASTRA 에 넘긴다. 0 단계 두 번째 점검(ray 시작/방향 결박 · Warp mesh · 충돌체 · 센서 시각)은 lead 가 따로 한다 — 이 작업서의 범위 밖. 막히면 추측하지 말고 막힌 줄과 필요한 값을 적어 보고한다.
