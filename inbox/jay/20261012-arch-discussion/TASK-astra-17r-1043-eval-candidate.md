> 분류: A/평가 · ASTRA 의뢰 17r · 1043 쌍 평가 새 판 후보 검증 (CPU 후보 · 승인 전 운영 반영 없음)
> 작성: 오흥재 (lead 세션 · Claude 작성) · 2026-10-14 11:5x
> 근거: VERIFY-astra-17q.md · 작업자 E 의 후보와 보고 (`night-tools-20261013/cmdr1043_eval_cand/` · 원자료 `C:/Users/AI-WS01/.claude/jobs/09bbf294/tmp/codexE/` · #550 댓글 6158817384 · 6159198847) · lead 재실행 (`cmdr1043_eval_cand/lead_rerun/`)
> 요지: 17q 가 요구한 수정 (비교기 seed · A/B 자료 소유권 · reset 명세 · Isaac 직렬 실행 계약) 을 담은 1043 평가 새 판 (등록 manifest · 새 비교기 · A 45 회 전용 드라이버 · 새 후처리 · 시험 · 변이) 을 작업자 E 가 CPU 로 만들었다. 이 후보가 17q 의 요구를 실제로 채우는지, 숨은 1042 결박이나 약한 시험이 남았는지, 운영에 반영하고 GPU 0 에서 첫 알려진 답 · 대표 run 단계로 가기 위해 무엇이 더 필요한지 판정해 달라
> 상태: 의뢰 (GPU 는 둘 다 비어 있음 · 이 의뢰는 GPU 기동 허용을 구하지 않는다)

# ASTRA 17r

## 답하는 자세 (팀장 지시 · 모든 사항에 적용)

비판적이면서도 냉정하고, 현실적이면서도 아주 전문성이 높은, 이 분야를 평생 탐구한 전문가로서 답해 주십시오. **lead 는 Sonnet 5.5** 입니다. 작업자 E 의 보고와 lead 의 요약을 평소보다 더 신중하게 원자료 (후보 코드 · diff · 시험 코드 · 로그) 로 독립 대조해 주십시오. 17j · 17n · 17o · 17p · 17q 의 기준 (장치 전체 값 vs 몫 · 변이는 정상 소스의 같은 시험 통과와 의도한 실패 위치 · 문서와 코드의 차이 · 시험이 실제 실행 흐름을 타는지 · 「X 없음」 은 기록으로) 을 적용해 주십시오.

**분량:** `VERIFY-astra-17r.md` 한 파일. 첫 줄 한 문장 판정, 질문마다 「판정 · 근거 · 남길 미확인」. 코드 수정 · GPU · Isaac · 커밋은 하지 마십시오. `_eval/out/` 은 읽기만 · `slot/` · `handover_*` · `handover-1635` 에는 쓰지 마십시오. em dash 금지.

## 1. 대상 (바이트 고정 · `night-tools-20261013/cmdr1043_eval_cand/SHA256SUMS.txt`)

작업자 E (Codex Worker · gpt-6-sol · 검증자 아님) 의 후보. 보고 `REPORT.md` · 변경 설명 `CHANGES-driver.md` · `CHANGES-post.md` · 전체 diff `diff-driver.patch` · `diff-post.patch` · GPU 에서만 할 일 `GPU-PLAN.md` · 인계 `HANDOFF.md`.

| 파일 | SHA256 (앞 12 자) | 기준 원본 |
|---|---|---|
| `manifest_s1043.json` (계약 해시 `1cbfb526b745…`) | `4ed474bbe2ef` | (새 파일) |
| `s1043_manifest.py` (검증 함수) | `4fdf8b3e8b9f` | (새 파일) |
| `cmdr_bundle_compare_s1043.py` | `548aae46e529` | `cmdr_bundle_compare.py` `bb827f3c…` |
| `cmdr_eval_driver_s1043.py` | `4181368c9984` | `cmdr_eval_driver_v37.py` `c351fde3…` |
| `frozen_exec_s1043.py` (slot 뒤 첫 자식 · 입력 재검사) | `bf7d16d2373f` | `frozen_exec.py` (v6 의 것) 참조 |
| `cmdr_post_s1043.py` | `9c66e4cb7875` | `cmdr_post_v10.py` `dea9ca7b…` |

후보는 **운영 `_eval` 에 반영되지 않았다** (작업자는 `_eval` 안에 파일 0 개 · 수정 0 개라고 보고). 시험 · 변이 파일은 후보 폴더 `codexE/cand/` (`test_manifest.py` · `test_stage1.py` · `test_driver_cpu.py` · `test_full_inputs_copy.py` · `test_integration_s1043.py` · `make_synth_a.py` · `make_v10_reference.py` · `mutant_integrated_*.py` 12 개) 에 있다.

## 2. 작업자 보고와 lead 재실행

- 작업자: 첫 배포는 **A 45 회 (부모 · off24 · on24 x 목표 3 칸 x seed 1000~1004) 만 허용**, B · remeasure 는 rc 8 로 거절. manifest 에 계약 (전 단계 · 해시 한 개) 과 실행 기록을 분리, 부모 · off/on 22,000/24,000 · result · bundle · stamp · 설정 소스 해시 등록, base 555 · A 45 · B 잔여 510 · 선별 96 칸 · 최대 추가 768 run 등록. 미정 값 (GPU index · UUID · 마감 · 위험 한도 · 승인 · 공통 lease 참가 · 변환 잠금 공유 · torch · Isaac 런타임) 은 `UNDECIDED` 로 두어 `launch_errors()` 가 기동을 거절 (CPU 시험에서 rc 4).
- 변경 4 갈래: ① manifest · 경로 (q 에 `--outdir` 명시 · 모델 역할을 등록한 부모 경로로) ② 기동 관문 (v37 의 자체 변환 lock 제거 · 별도 전체 실행 lease · slot v3 + v3 registry + attempt 별 USD 루트 + `--expect_conversions 1` · 기동 직전 물리 UUID · 여유 · slot 뒤 frozen 자식이 입력 재검사) ③ 출처 · 단계 (양 군 결과 · stamp · bundle · 종료 로그 · 부모 포함 A 45 · 새 attempt · stamp · 해시만 수용 · 태그 접두는 밑줄 없는 `cq`) ④ 판정 · 표시 (post v10 통계 함수 보존 · A 완전성 관문 · 17q 문구 강제 · 결과 파일 원자 교체 · 표 제목 v8 수정). 가져오지 않은 것: 옛 인계 · legacy v3.2 stamp · 1042 hold / release / 승인 JSON · 두 번째 remeasure 로그 · B 결과 발행 · v37 의 `gate_c1` 시작 시험 · 구형 pin.
- 작업자 시험 (격리 · `CUDA_VISIBLE_DEVICES=-1` · isaac311-moects): 통합 33/33 (정상 CLI 먼저 · v10 논리 10 항목 일치 · 반례 · 경계값 · 기동 거절 · 변이 6 개 CAUGHT) · 등록 입력 복사본 전체 9/9 · 비교기 5/5 · 드라이버 5/5 · manifest 구조. 합성 알려진 답: 평균 정확히 +10.0 %p 와 세 하한 > 0 은 `개선`, +9.9333 %p 와 하한 0 은 `개선 아님`. 처음 실패 (비교기 경로 표기 · cp949 · `changed` NameError · `saves.json` 복사 누락) 는 분모에 안 섞음.
- **lead 재실행 (11:02 · 새 run-id `lead1` · 같은 해석기 · CPU):** `test_manifest` PASS (계획 555/45/510/96/768 · 기동 거절 이유 15 개 · 경로 · 계약 변조 거절) · `test_stage1` 5/5 · `test_driver_cpu` 5/5 · `test_full_inputs_copy` 9/9 · `test_integration_s1043` 33/33 (변이 6 개 각각 `got CAUGHT want CAUGHT`) · 모두 종료 0 · 로그 `lead_rerun/`. **lead 가 하지 않은 것:** 후보 코드의 줄 단위 검토 (diff 는 37 KB · 30 KB), 변이가 실제로 의도한 검사를 끈 것인지 코드 대조 (작업자 보고 · 로그만), `frozen_exec_s1043.py` 의 v6 `frozen_exec.py` 와의 관계 검토, 실제 slot v3 · guard · isolate 연쇄 (GPU 단계).
- **작업자가 정직하게 적은 한계 (그대로 인용):** 새 드라이버가 쓰는 변환 잠금이 운영의 공통 변환 잠금과 동일하다는 근거가 없음 · 모든 GPU 0/1 기동 경로가 lease 에 참가한다는 근거가 없음 (다른 도구는 이 lease 를 안 씀) · GPU 알려진 답 · PhysX 버퍼 대조 · reset 과 관측 history 의 GPU 알려진 답 · 대표 run 시간 · peak 는 미확인.

## 3. 물음

1. **17q 의 필수 수정 4 건이 후보에서 실제로 닫혔는가 (코드 · diff 로).** (a) 비교기: 기대 seed · 부모 · 규약이 manifest 에서 오고 1042 · 1043 동시 허용이나 seed 검사 삭제가 없는가 (원본 `cmdr_bundle_compare.py:18~20,36~44,93`) (b) A/B 자료 소유권 · 태그 문법: 같은 base 로그의 다음 attempt 에서 A 를 재검하고 555 로 확장하는 최소안이 구조적으로 가능한가 · 접두 `cq` 로 `접두_모델_나머지` 파싱이 바뀌지 않는가 · B / remeasure 를 호출하면 진짜 거절되는가 (rc 8) · `main_remeasure` 함수 본문이 소스에 남아 있는 것이 위험한가 (c) reset 명세: manifest 에 XY ±0.5 m · Z +0~0.2 m · 고정 yaw · 기본 관절 · 속도 0 이 실제 `q_eval_cmdr.py:142~154,242~247,332~386` 와 같게 적혔고 드라이버가 이 값을 대조 · 전달하는가 (d) Isaac 직렬: 별도 실행 lease 가 기동부터 자식 트리 종료까지 보유되는가 · 획득 순서 · 변환 잠금과 분리 · 같은 잠금을 바깥에서 잡고 slot 에 다시 주는 방식이 아닌가. lease 가 다른 기동 경로에 강제되지 않는 한계는 어떻게 닫아야 하나 (예: 기동 직전 foreign python/Kit 프로세스 검사로 보류).
2. **숨은 1042 결박 · 조용한 오류.** 후보에 남은 `out/` 기본 경로 · 1042 seed · 옛 모델 이름 · 옛 로그 이름 · 옛 인계 · legacy 경로가 있는지 (diff 의 변경하지 않은 줄을 포함해 전수 확인). 새 파일 이름 · 새 PARTICIPANT · 작성자 탐지 (v37 341~357) 가 새 root 에서 동작하는가 · `training_done()` 이 off / on 양 군을 보는가 · post 의 `out/` 환경 변수 우회가 막혔는가. 특히 **후보가 평가기 (q_eval_cmdr.py) 를 실제 호출할 때 인자 전체 (`--checkpoint` `--train_yaml` `--families` `--cells` `--episodes` `--eval_seed` `--obs_noise` `--physx_small_buffers` `--tag` `--outdir`) 가 1042 평가와 같은 의미로 전달되는가** (결과가 달라질 수 있는 기본값 포함).
3. **시험의 신뢰 범위.** 통합 33 / 33 · 전체 입력 9 / 9 · 드라이버 5 / 5 가 실제 새 CLI 경로를 타는가 (AST 문자열 시험이 아닌가) · 합성 fixture 가 v10 과 논리 10 항목 일치를 보이는 것이 원본 post 를 같은 합성 입력에 실제로 돌린 것인가 · 변이 6 개가 의도한 검사 한 곳만 끄고 지정한 반례가 잘못 통과해야만 CAUGHT 로 세는 규칙이 17j · 17n 규칙 (정상 소스의 같은 시험 통과 + 의도한 실패 위치) 에 맞는가 · 변이가 6 개뿐인데 17q 가 요구한 반례 전체 목록 (1042 주입 · on 만 완료 · 부모 해시 · 번들 · stamp 변경 · 출력 `out/` 회귀 · UUID 불일치 · v2 registry · 별도 lock · slot 이후 입력 변경 · 중복 태그 · 누락 / 중복 episode · 짝 지문 불일치 · 장치 불일치) 이 모두 실제 CLI 로 걸렸는가. 시험이 못 보는 것 (GPU 의 실제 slot · guard · isolate · Kit 연쇄 · 알려진 답 · 물리 버퍼 · peak) 을 구분.
4. **UNDECIDED 와 결정 권한.** manifest 의 `UNDECIDED` (GPU index · UUID · 마감 · 위험 한도 · 승인 · lease 참가 · 변환 잠금 공유 · torch · Isaac 런타임 판) 중 (i) 코드 · 현재 환경에서 lead 가 **측정해서 채울 수 있는 것** (GPU UUID · 런타임 판 · lease 경로) (ii) **팀장 결정이 있어야 채울 수 있는 것** (마감 · GPU 배정 · 위험 한도 · 「CMD-R 규약 교정」 의 의미) (iii) ASTRA 승인 json 이 필요한 것을 나눠 달라. 채우는 순서와 각 값을 정하는 시점 (결과를 보기 전) 을 명시.
5. **다음 단계와 GPU 첫 걸음.** 이 후보를 운영 `_eval` 에 반영하는 순서 (새 파일만 추가 · 보관 · 해시 고정 · 기존 v37 · post v10 동결 유지) 가 맞는가. 반영 뒤 **GPU 0 에서 첫 걸음으로 `GPU-PLAN.md` 의 알려진 답 · 대표 run (부모 평지 stop03 한 run 의 q 원본 대조 · 작은 버퍼 대조) 한 번** 을 별도 허용 대상으로 둘 수 있는가 (45 회 A 본 수집과 구분) · 그 허용에 필요한 기동 전 조건 · 중단 조건 · 보고 문구. A 45 회 본 수집 허용 전에 필요한 것 (팀장 결정 · UNDECIDED 해소 · 이 후보의 변경 · 새 승인 json).
6. **견적 갱신.** 작업자는 약 10:15 ~ 10:55 (40 분) 에 이 후보를 만들었다 (17q 견적 8.5 ~ 16 시간 중 작성 · 시험 부분). 남은 것 (ASTRA 검토 · 지적 반영 · 운영 반영 · GPU 알려진 답 · A 45 회 약 56 분 + 시작 시험 · 대기 · 재시도) 의 현실적인 남은 시간을 17q 7 절 기준으로 다시 적어 달라.

## 결과

- `inbox/jay/20261012-arch-discussion/VERIFY-astra-17r.md` 한 파일. 첫 줄은 한 문장 판정. 표기: 확인됨 · 추정 · 미확인.
