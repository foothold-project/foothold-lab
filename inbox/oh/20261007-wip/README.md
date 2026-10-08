# 20261007 진행 보고 첨부: 판정 요약 파일 사본

> 분류: 운영
> 작성: 오현민 · 2026-10-08 14:50
> 근거: 실측
> 요지: 진행 보고서(`../20261007-wip.md`)가 근거로 인용하지만 팀이 열 수 없던 작은 판정 요약 파일의 사본과 원래 위치, 가린 내용, 제외한 것.
> 상태: 초안

보고서 §5·§9에서 「첨부」로 링크한 파일이 여기 있다. 원본 전체가 아니라 **판정 요약 파일만** 골랐다. 원래 위치는 작성자 로컬 작업공간 기준 상대 경로다.

## rl/: 목표형·속도형 교사 결과 Markdown (8개)

원래 위치: `Isaac-CV/24-perceptive-first-env-20261007/` 아래 같은 상대 경로.

| 파일 | 내용 |
|---|---|
| `goal1-20261007/FROZEN-CONFIG-goal1r3-20261007.md` | r3 동결 설정·사전 검증 기록 |
| `goal1s-20261007/RESULT-goal1s-20261007.md` | S 결과(r3 대비 개선/회귀) |
| `goal1u-20261008/RESULT-goal1u-20261008.md` | A·B 결과 |
| `goal1u-20261008/COMPARE-AB-20261008.md` | A·B 비교표 |
| `goal1u-20261008/trace5/trace5_summary.md` | trace 요약 |
| `goal1u-20261008/resume-audit/AUDIT-resume-20261008.md` | 이어학습 복원 CPU 검수 |
| `goal1u-20261008/resume-audit/train_windows.md` | 학습 구간별 요약 |
| `logs/pod/lla-20261007-s1-ft3/four_way.md` | 기존 속도형 ft3 네 갈래 비교 원표 |

## app/: 조종 앱 시험 판정 파일 (12개)

원래 위치: `control-app/test/results/` 아래 같은 상대 경로.

| 파일 | 보고서 §5 칸 |
|---|---|
| `gz-20261007/locgate-r7/loc.json` · `slam-r6/loc.json` · `slamreload-r1/loc.json` | Gazebo 이동·영상·지도 |
| `gz-20261007/fault-suite-r3/fault.jsonl` | 장애 시 차량 정지 |
| `auth-20261007/fin-auth-183445/result.json` | 인증·영상 서버 차단 최종 회귀 |
| `auth-20261007/fin-mission-183734/result.json` | 임무·결과 기록 |
| `auth-20261007/fin-kill-184248/result.json` | 임무 서버 장애·재시작 |
| `auth-20261007/phone-182645/result.json` | 휴대폰 화면 에뮬레이션 |
| `auth-20261007/go2mock-174129/result.json` | Go2 어댑터 오프라인 검증 |
| `docs-mobile-20261008/run-012850/result.json` · `run-014323/result.json` · `auth-20261008/phone-land-013711/result.json` | 휴대폰 문서·가로 화면 |

## 사본에서 바꾼 것 (원본은 그대로)

`확인됨`(2026-10-08 사본 대조): 내용과 수치는 그대로이고 아래만 바꿨다. 그래서 사본의 파일 해시는 원본과 다르다.

- 긴 대시 문자를 `-` 로 바꿈(팀 저장소 표기 규칙).
- 로컬 절대경로 앞부분을 `<workspace>/` 로 바꿈: `docs-mobile-*/result.json`, `slam-r6/loc.json`, `slamreload-r1/loc.json`.
- 로컬 프로세스 번호를 `"<masked>"` 로 바꿈: `locgate-r7/loc.json`, `fault.jsonl`, `phone-182645/result.json`, `phone-land-013711/result.json`.
- `FROZEN-CONFIG-goal1r3-20261007.md`: 3행 원격 작업 폴더 경로를 `<pod-work>/` 로, 162행 프로세스 번호 2개를 `<가림>` 으로 바꿈.
- `RESULT-goal1u-20261008.md`: 56행 게재 금지 항목 목록의 계정명·경로 실값을 일반 명칭으로 바꿈.
- `RESULT-goal1s-20261007.md`: SHA-256 전체값 11개를 앞 16자로 줄임.

## 넣지 않은 것

| 제외 | 이유 |
|---|---|
| checkpoint(`.pt`)·영상·화면 캡처 | 용량. 결과 판단은 위 요약 파일로 확인 가능 |
| 원시 로그(`metrics.jsonl`·`run.log`·`stack.log`·`vmode-gz-r4.log` 등) | 요약이 아닌 원시 기록이고 로컬 경로·프로세스 정보가 섞여 있음 |
| manifest 원본·실행 코드·DB | 보고서 §6에 「향후 제공 예정」으로 둔 자료. 이번 제출 범위 아님 |
| 인증서·계정 파일, 실기 시험 메모(`live-20261008/`) | 보안·계정 정보 |
