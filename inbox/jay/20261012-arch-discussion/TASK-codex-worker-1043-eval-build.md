> 분류: A/평가 · Codex Worker 작업서 · 1043 쌍 평가 새 판 제작 (CPU 전용 후보 · 승인 전 운영 반영 없음)
> 작성: 오흥재 (lead 세션 · Claude 작성) · 2026-10-14 10:2x
> 근거: VERIFY-astra-17q.md 전문 (설계 검증 · 필수 수정) · night-tools-20261013/cmdr1043_eval_design/MEMO-codexD.md · VERIFY-astra-17p.md 5 절 · VERIFY-astra-17.md 3.2 ~ 4 절 · `_eval/cmdr_eval_driver_v37.py` · `cmdr_post_v10.py` · `cmdr_bundle_compare.py`
> 요지: ASTRA 17q 가 (가) 안 (v37 동결 + 새 판) 을 택하고, 비교기 seed · A/B 자료 소유권 · reset 명세 · Isaac 직렬 실행 계약을 먼저 고치라고 했다. 새 폴더에서 CPU 전용 후보 (manifest · 비교기 · 드라이버 · post · 시험 · 변이) 를 만든다. GPU 기동 허용이 아니다
> 상태: 의뢰 (2 단계 · 코드 쓰기 · CPU 전용 · `_eval` 은 읽기만)

# Codex Worker 작업서 · 1043 평가 새 판 제작

## 0. 규칙 (먼저 읽을 것)

- 너는 **Codex Worker (gpt-6-sol)** 이고 검증자가 아니다. **만들고 「검증됐다」 라고 쓰지 마라.** ASTRA 가 따로 검증한다. 규칙은 `TASK-codex-worker-17g-fix.md` 1 절 · `TASK-codex-worker-17i-fix.md` 0 · 0.1 절 (격리 단언) 을 그대로 따른다. YOLO 세션 · 커밋 금지 · 삭제 금지 · GPU · Isaac 실행 금지 · 시험은 `CUDA_VISIBLE_DEVICES=-1` · 키 · 토큰 안 다룸 · em dash 금지 · 실패한 것도 정직하게 보고.
- **전부 새 작업 폴더 `C:/Users/AI-WS01/.claude/jobs/09bbf294/tmp/codexE/` 안에서 만든다.** `C:/isaac/ext/go2_rl_robotlab/_eval/` 안에는 어떤 파일도 만들거나 고치지 않는다 (원본 v37 · post v10 · 비교기 · q 도구 · slot · isolate · guard 는 **읽기만** · 동결). 후보를 운영에 반영하는 것은 ASTRA 판정 뒤 lead 가 한다. `_eval/out*` · `slot` · `branch` · `s2` · `handover*` · `rand_scenes` · `ce12` 쓰기 금지. `_eval/out/` 은 다른 일의 자리라 **읽기는 1042 평가 기록 (`cmdr_eval_driver.json` 같은 것) 에 한한다.**
- **격리 단언 (첫 번째 일):** 첫 쓰기 전에 시험 · 후보가 쓰는 모든 경로 변수 (출력 · 보고 · 작업 · attempt · registry · lock · slot 기록 · STOP · 로그) 가 `codexE/` 아래인지 코드로 확인하고 출력한다. 시험은 실제 `out/` · `out_branch/` · `slot/` 으로 향한 경로가 **한 개라도 있으면 시작하지 않게** 한다. 시험이 읽는 실제 자료는 `codexE/fixture_real/` 로 복사해서 복사본으로만 쓴다.
- 해석기: `C:/Users/AI-WS01/anaconda3/envs/isaac311-moects/python.exe` (시험 · 비교기). 시작에서 `sys.executable` · 적재한 후보 파일의 `__file__` 과 SHA256 을 출력하고 기대와 다르면 「환경 불일치」 로 끝낸다.
- **ASTRA 17q 를 먼저 끝까지 읽고 그 지적을 그대로 따른다.** 아래는 요약이지 대체가 아니다. 모르는 것은 추측하지 말고 보고서의 「미확인」 으로 남긴다. 시간에 맞추려고 관문을 삭제하지 않는다 (17q 7 절).

## 1. 만들 것 (후보 · `codexE/cand/`)

1. **등록 manifest** `manifest_s1043.json` + 검증 함수 (`s1043_manifest.py`): 과학적 계약 (전 단계 동결 · 해시 한 개) 과 실행별 기록 (attempt · 마감 · 승인 · 이 계약 해시 참조) 을 나눈다. 필수 항목은 17q 4 절 전부 + 메모 6 묶음: 실험 `cmdr_s1043_pair_eval` · seed 1043 · 부모 (E1 20,000 같은 바이트 `c8951b79…`) 경로와 해시 · off/on 24,000 (22,000 은 B 목록용) 경로 · 해시 · `result.json` · `bundle.json` · `bundle.npz` · `validate_stamp.json` 해시 · 부모 `env.yaml` · `agent.yaml` · 실제 설정 소스 해시 (env.yaml 은 현재 설정과 비교용이라 설정 전체를 복원하지 않는다는 17q 4 절 문구 그대로) · 평가 계약: difficulty 0.5 · terrain_set train · heading_hold 0 · student · 한 run 한 칸 100 환경 · 평가 seed 1000 ~ 1004 · 목표 noise on · flat 대조 noise off · 실제 관측 corruption/history 설정 · 명령 벡터 · 전환 시각 · 길이 · policy/physics dt · episode ID 배치 · 지표 `span_q2/span_q1a/span_q1` 와 결측/비유한 값 처리 · MAE 부모값 0 절대선 · 선별 −5 %p 경계 · 장치: 물리 GPU index 와 UUID · 최소 여유 4096 MiB · `CUDA_DEVICE_ORDER=PCI_BUS_ID` · 같은 `CUDA_VISIBLE_DEVICES` · 새 데이터 · 보고 · 작업 루트 · 태그 namespace · STOP · 마감 · 코드 / 입력 해시 목록 · 해석기와 주요 라이브러리 판 · 새 승인과의 연결. **미결정 값 (GPU 배정 · 마감 · 위험 허용선 등) 은 임의 기본값으로 채우지 말고 `UNDECIDED` 로 두어 그 상태에서 기동이 거절되게 한다.**
   - **reset 명세는 실제 `q_eval_cmdr.py:142~154,242~247,332~386` 를 읽어 적는다:** 지형 원점 주변 XY ±0.5 m · Z +0~0.2 m · 관절 기본 자세 · 몸체 속도 0 · 명령별 고정 yaw. `spawn_offset=""` 은 별도 전진 오프셋 없음. 「무작위화 없는 중앙 시작」 으로 구현하지 않는다 (다른 시험이 된다).
2. **새 번들 비교기** `cmdr_bundle_compare_s1043.py`: 기대 seed · 부모 · 규약을 manifest 에서 읽는다 (원본 `cmdr_bundle_compare.py:18~20,36~44,93` 의 seed 1042 고정이 1043 을 거절하는 도구 계약 불일치. seed 검사를 지우거나 1042/1043 동시 허용으로 풀지 않는다). `--out` 으로 `codexE/` 아래를 명시하고 `out/branch` 기본 출력은 쓰지 않는다. 정상 (실제 1043 입력 복사본 → `SAME`) · 오입력 (seed 틀림 · 부모 해시 틀림 · 한 군 바이트 변경 → `DIFFERENT`) 시험. 원본 비교기의 1042 동작을 건드리지 않는다.
3. **새 드라이버** `cmdr_eval_driver_s1043.py` (v37 복사본 · v37 원본 해시 `c351fde3…` 를 기준으로 두고 변경을 아래 4 갈래로 나눠 `CHANGES-driver.md` 에 diff · 함수 목록으로 제출):
   - ① manifest / 경로: `OUT` · `B` · `MODELS` · `EXPERIMENT` · 로그 · attempt · `NIGHT_OUT` · 시작 시험 (989~1043) 을 manifest 에서. 평가기 호출에 **`--outdir` 를 넘긴다** (v37 821~830 의 `q()` 가 안 넘김).
   - ② 기동 관문: slot v3 + `usd_isolate_run_v3` + `gpu_guard` + **v3 전용 registry** (구형은 읽기만) + attempt 별 USD 루트 + 공통 변환 lock (v37 의 자체 `out/isaac_convert.lock` 방식 785~794 은 가져오지 않는다 · 같은 lock 중첩 금지) + `--expect_conversions` + 기동 직전 장치 UUID · 여유 · 상대 프로세스 확인. **Isaac 직렬 실행:** slot v3 는 장면 생성 뒤 잠금을 풀기 때문에 (`isaac_slot_v3.py:483~505`) 변환 직렬화일 뿐이다. 17q 5 절대로 별도 **실행 lease (기동부터 자식 트리 종료까지 보유 · 변환 잠금과 역할 · 획득 순서 분리 · 같은 잠금을 바깥에서 잡고 slot 에 다시 주는 방식 금지)** 를 설계하거나, 참가하지 않는 Isaac 이 있으면 시작하지 않는 검사를 넣는다. 어느 쪽이든 안 되는 부분 (다른 도구가 이 lease 를 안 씀) 은 보고서에 그대로 적는다.
   - ③ 출처 / 단계 전환: A (목표 전용 45 run: 부모 · off24 · on24 x 목표 3 칸 x seed 1000~1004 x 100 episode) 와 B (나머지 base 510 + 선별 추가) 의 **자료 소유권 · 태그 문법 · 로그 namespace**. post 는 같은 태그가 두 로그에 있으면 거절하고 태그를 `접두_모델_나머지` 로 파싱한다 (`post:212~215,391~421` · `v37:1134~1135`): 접두에 밑줄을 넣으면 모델 해석이 바뀐다. 최소안: 같은 base 로그의 다음 attempt 에서 A 를 재검하고 555 개로 확장하며 A 시점 보고는 불변 사본으로 보존. **첫 배포에서는 A 45 회만 기동 가능하고 B / remeasure 는 명시적으로 비활성화 (호출하면 거절)** 하되 B 의 555 개 목록 · 선별 규칙 · 단계 순서 · 예산 · 중단 시 부분 보고 방식은 manifest 에 처음부터 동결한다. 옛 인계 (87~88 · 295~321) · legacy v3.2 재사용 · 옛 pin 은 가져오지 않고 이유를 `CHANGES-driver.md` 에 적는다. 새 파일 이름이므로 `PARTICIPANT` · `SELF_PATH` (500~547) 와 작성자 탐지 (341~357) 를 새 이름 · 새 경로 기준으로 고친다 (모델 역할은 `startswith(E1)` 대신 등록한 경로 · 역할). `training_done()` 은 **off/on 양 군** 완료를 요구 (296~325 는 on 만 봄).
   - ④ 판정 / 표시: 목표 결합 판정 (세 구간 하한 모두 > 0 · 세 칸 동일 가중 평균 ≥ +10 %p) 은 기존 post 규칙 그대로. **A 완료 = 부모 포함 45 회 모두 유효** 를 별도로 검사 (기존 post 결합 식은 부모 결측만으로는 안 막힘). 결과 문구는 코드가 강제: 「학습 seed 1043 의 평지 목표 세 칸, 24,000 on−off 결합 판정. 부모 대비 별도 표시. 회귀 범위 3/99 칸 측정, 나머지 96 칸 및 22,000 미평가」 (「퇴행 99 칸 미평가」 는 틀림: 목표 3 칸도 99 칸에 포함. `post:594~607`). 두 학습 seed 를 합쳐 일반 효과 · 독립 episode 1,000 개라고 쓰는 문구 거절.
4. **새 post** `cmdr_post_s1043.py` (post v10 `dea9ca7b…` 복사본 · 변경을 같은 4 갈래로 `CHANGES-post.md`): 모델 · 로그 두 개 · `EXPERIMENT` 를 manifest 에서 · 출력은 새 루트에 **원자적 저장** · 표 제목 (post 711 행의 v8 표기) 수정 · 새 수집만 허용 (1042 hold/승인 JSON 과 legacy 재사용 금지) · 통계 함수와 검증 조건은 불필요하게 재작성하지 않는다.
5. **시험과 변이** (`codexE/cand/` 안 · 격리 단언 포함):
   - 정상 fixture: 합성 정상 대조군이 등록된 1043 부모 · off · on 을 받아 **새 경로에만** 쓴다 (실제 새 CLI 경로로. AST 문자열 시험만으로는 충분하지 않다는 17q 2 절). 기준 (v37 · post v10) 과 새 판의 **논리 결과를 같은 정상 fixture 에서 대조**.
   - 반례를 **실제 새 CLI 경로**로: 1042 모델 / 로그 / 승인 주입 · on 만 완료 · 부모 해시 / 번들 / stamp 변경 · 출력 루트가 `out/` 로 되돌아감 · GPU index 는 0 인데 UUID 가 1 · v2 registry 또는 별도 lock · slot 이후 입력 변경 · 중복 태그 · 누락 / 중복 episode · 짝 지문 불일치 · 장치 불일치 · manifest 의 `UNDECIDED` 값 · B 호출 · 비교기 seed 오입력. 정상은 통과하고 반례는 자식 0 회 또는 `미확인` 으로 닫혀야 한다.
   - 알려진 답 통계 경계: 평균 정확히 +10 %p 는 통과 · +9.9333 %p 는 실패 · 하한 하나가 0 이면 실패.
   - 변이: 각 검사를 끈 사본에서 지정한 시험이 **실제로** 실패해야 CAUGHT (실패한 시험 목록 = want, import · module · 구문 오류 · 환경 불일치는 CAUGHT 로 세지 않음. 17j · 17n 규칙). 정상 소스에서 같은 시험이 먼저 통과한 로그를 남긴다.
   - **GPU 알려진 답 / 물리 버퍼 대조는 CPU 시험이 아니다.** 이 후보에서는 「GPU 에서만 확인할 항목」 목록으로 보고서에 남기고 CPU 시험 통과로 대신하지 않는다 (17q 7 절).
6. **GPU 에서만 확인할 항목과 기동 계획서** (코드가 아니라 문서): 첫 GPU 기동 전에 필요한 알려진 답 · 대표 run · 장치 / UUID · peak 측정 · lease 동작 확인 순서와 중단 조건. GPU 0 에서 평지 시작 시험을 한 과거 기록 (`out/cq_test_*g0*` · 50.9 초 · 최소 여유 12,917 MiB · 최대 사용 3,385 MiB) 은 **제한된 과거 시험일 뿐 1043 전체 처리량의 근거가 아니다** (17q 5 절).

## 2. 순서와 보고

순서: (a) 격리 단언 · 17q · 메모 · v37 · post · 비교기 읽기 (b) manifest 스키마와 검증 함수 + 새 비교기 + 그 시험 (가장 먼저 닫히는 부분 · 끝나면 lead 가 따로 볼 수 있도록 `codexE/STAGE1-DONE.md` 한 줄) (c) 드라이버 새 판 · 변경 4 갈래 diff (d) post 새 판 (e) 통합 시험 · 변이 (f) 보고서.

보고서 `codexE/REPORT.md`: 머리 다섯 줄 (분류 · 작성 · 근거 · 요지 · 상태) 뒤에 격리 단언 출력 · 해석기와 후보 해시 · 변경 4 갈래 diff 요약 (줄 수는 우열의 증거가 아니라는 점) · 가져오지 않은 기능과 이유 · 정상 대조군 논리 결과 비교 · 시험 (예정 대비 실행 · skip · hold · 종료 코드) · 변이 (CAUGHT 의 want 일치) · 처음 실패한 것 (분모에 섞지 말 것) · 실제 작업 시간과 원래 견적 (8.5~16 시간) 의 차이 · GPU 에서만 확인할 항목 · **미확인** · `_eval` 안에 만든 파일 (0 개여야 함) · 후보 `SHA256SUMS.txt` · lead 가 다시 돌릴 명령. 끝나면 #550 에 요약 댓글 (되읽기 확인 · 🤖 꼬리말 금지). 한도나 컨텍스트가 모자라 중단하면 (b) 까지의 상태와 남은 일을 `codexE/HANDOFF.md` 에 적고 그대로 멈춘다.
