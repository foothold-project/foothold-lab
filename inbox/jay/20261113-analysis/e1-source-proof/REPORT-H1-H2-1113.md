# E1 졸업 출처 대조와 R5 접촉 근거 검증

> 분류: A/평가
> 작성: 오흥재(analyst-lx) · 2026-11-13 22:40
> 근거: #555 · verifier VERIFY-CRITERIA-CODE-1113 H1/H2 · lead 22:20 의뢰 · v24 a19cd6a2
> 요지: 다른 저장본·시드·계획 영수증과 접촉 측정이 아닌 파일이 판정 근거로 통과하는 두 경로를 막는다.
> 상태: CPU 172개 통과 · 새 돌연변이 12/12 검출 · reviewer 검토 대기 · 운영 사본 미변경

## 바뀐 동작

| 지적 | 소비 경로와 고침 | 확인 |
|---|---|---|
| H1 원자료 출처 | `foothold_s2/ex42_e1_v2.py`의 `_identity`·`_map_cell`. JSON 생성 영수증과 map NPZ의 체크포인트 SHA·시드 대조, 지형 배치 SHA와 지도·명령 파일명 대조. 캐시된 셀도 원자료와 다시 대조 | 실제 m250의 SHA만 변경, seed만 999로 변경, JSON 내부 생성 영수증만 변경한 경우 모두 거절 |
| H1 처방 영수증 | `ex42_e1_v2.py`의 `treatment`. 시작 영수증의 계획 SHA를 점수 실행 계획과 대조하고 b 영수증 3개 모두 그 SHA·스키마·경계·stage를 요구. 두 rank의 실제 보상이 명령 영수증의 요청 보상과 같아야 함 | 세 영수증의 계획 SHA를 함께 바꿔도 거절. v24의 m250=초기 계획, m500=b1, m750=b2 계약 보존 |
| H1 HOLD | `judge_e1_v2`가 출처·파일 오류를 명시적인 HOLD로 반환. 이미 계산된 PASS로 우회 불가 | 캐시 PASS에 다른 출처를 결합한 반례 HOLD. 하위 reader 오류도 기존 eval_once의 HOLD 경로로 감 |
| H2 접촉 검증 | `e1-boundary-rules/boundary_read.py:328`와 새 `r5_contact.py`. 스키마·발 순서·생성 체크포인트·시드·모드·dt·창·힘/높이/속력/생존 배열을 검사. 접촉을 원시 힘의 크기 >1 N으로 다시 계산 | 해시가 올바른 텍스트, Fz 전용 정의, 다른 체크포인트, 바뀐 발 순서, 잘린 배열, NaN, 거짓 요약 모두 거절 |
| H2 발별 집계 | 1≤t<6 s에서 완전 공중 구간·기여 env·단일 표본 구간·높이·끌림·0.5 s 미만 비율 재계산. 신고한 발별 수치와 비교 | 답을 아는 힘 입력: 발마다 31구간×64env=1,984구간, 높이 0.04 m, 접지 끌림 126/250. Fx=2 N·Fz=0인 입력으로 norm과 Fz 차이를 검출 |

졸업 수치 문턱, R2~R6 발동 조건, 보상 가중, 실행 계획은 바꾸지 않았다. R5 원자료 계약은 [판독기 README](../e1-boundary-rules/README.md)에 적었다.

## 실제 자료와 한계

확인됨: m250 `763a1eae…`를 v24 위의 수정 코드로 `ex42_score.measure`에서 다시 계산했다. 기존 FAIL과 같고 `e1_v2_cells` 전체가 동일하다. [실제 재생 결과](actual-p1-replay.json). 당시 m500 최종 점수는 없어 대신 만들지 않았다.

확인됨: runner의 `/home/jay/data/foothold/s2_lab/gait_contact_m250_20261113_191959/gait_raw_fwd0.2.csv`에는 힘과 접촉이 있지만 발 높이·속력은 없다. 따라서 이 CSV만으로 R5의 모든 근거가 갖춰졌다고 판정하지 않는다. 새 원자료 계약에 맞는 생산자 출력과 실측은 아직 필요하다. 단순히 형식 이름을 바꾸거나 미측정을 0으로 채워 통과시키지 않는다. R5 준비 부족은 학습 중단 명령이 아니다.

axis-v2의 옛 NPZ에는 자체 `run_identity`가 없다. 그 경로는 생성 JSON의 체크포인트·시드를 대조한 뒤 JSON이 고정한 원시 NPZ SHA를 검증한다. 파일 안에 없는 정체 정보를 검증했다고 주장하지 않는다.

## CPU 시험

| 범위 | 결과 | 증거 |
|---|---:|---|
| 수정 전 H1/H2 반례 | 출처 반례 7개와 임의 텍스트 반례가 기존 코드의 거절 실패를 재현 | `/home/jay/mai/tmp/analyst/h1h2-red-1113.log` |
| v24 + H1 | 54 PASS | `/home/jay/mai/tmp/analyst/e1-h1h2-1113/h1-final.log` |
| H2와 기존 R2~R6 도구 | 118 PASS | `/home/jay/mai/tmp/analyst/e1-h1h2-1113/h2-final.log` |
| 출처·접촉 검사 제거/변형 | 12/12 검출, 정상 대조 2개 통과 | [mutations.json](mutations.json) |
| 기존 문턱·GT/PRED·R5 검사 변형 | 12/12 검출, 정상 대조 통과 | [legacy_mutations.json](legacy_mutations.json) |

돌연변이 사망은 해당 반례의 assertion 또는 DID NOT RAISE 실패로 확인했다. import 오류나 수집 오류를 검출로 세지 않았다. 최초 실제 자료 동등성 시험에서 `/home/jay/data`와 `/mnt/win-d`의 경로 별칭이 달라 실패해, 원 점수에 기록된 평가 경로로 재생했다. 수치를 느슨하게 비교한 것이 아니다.

시험은 두 프로세스로 분리한다. 통합 가지의 옛 4항 parser와 v24의 10항 parser를 한 pytest 프로세스에 함께 import하면 기존 도구 시험 3개가 모듈 캐시 때문에 실패한다. H1은 a19cd6a2 실행 코드 위에 변경분을 얹어 확인했고, H2는 #784 도구 자체의 기존 실행 코드 경로를 유지했다. GPU·Kit·학습은 실행하지 않았다.

```bash
# 저장소 뿌리에서. 출력은 운영 폴더 밖 지정.
set -a
source /home/jay/mai/foothold-linux.env
set +a
CUDA_VISIBLE_DEVICES='' PYTHONDONTWRITEBYTECODE=1 OMP_NUM_THREADS=2 /home/jay/miniforge3/envs/isaac311/bin/python -B inbox/jay/20261113-analysis/e1-source-proof/check_provenance_mutations.py --out /home/jay/mai/tmp/analyst/h1h2-reproduce
```

이 명령은 a19cd6a2를 scratch에 풀고 H1 변경만 얹어 반례·돌연변이를 실행한다. 원본·운영 사본을 수정하지 않는다. 전체 H1 회귀는 생성된 `v24-overlay`에서 `test_ex42_e1_source_identity_cpu.py`, `test_ex42_e1_v2_cpu.py`, `test_ex42_e1_judge_cpu.py` 세 파일, H2 회귀는 별도 Python 프로세스에서 `e1-boundary-rules`를 pytest로 실행한다.

## 전달 범위

- 실행용 v24에 필요한 H1 코드: `foothold_s2/ex42_e1_v2.py`와 `foothold_s2/ex42_stage_judges.py`의 사전 `measure_cells` 호출 제거 한 줄. 다른 단계 adapter를 통째로 덮어쓰지 않는다.
- #784 판독기 H2: `boundary_read.py`와 **새 `r5_contact.py`를 함께** 사용. README·template·SHA256SUMS 동반.
- 새 브랜치는 통합 `5d819f8e`에서 출발하고 a19cd6a2의 두 파일 수정만 `8005e6e3`으로 먼저 옮겼다. 실행 중인 고정 사본이나 원장은 수정하지 않았다.
- reviewer 요청 범위는 H1/H2 및 위 반례·돌연변이다. 다른 감사 지적은 해당 주인 작업에 남긴다.
