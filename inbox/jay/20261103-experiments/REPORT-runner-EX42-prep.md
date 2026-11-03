> 분류: A/정책학습 · 준비 보고
> 작성: 오흥재 (runner 문서 반영) · 2026-11-03
> 근거: CURRICULUM-GATES v0.14 · DESIGN-EX42-TERRAIN v0.4.6 · D113/D114/D146/D151/D158/D159/D160/D163 · RULES-HUB R6/R25 · FAILURE-LOG M02/M08/M14/M24/M29/M76/M77
> 요지: EX-42 사전 표·승인 차단·W72 경계 계약을 추가하고, 실행 준비와 미결 설계를 분리했다.
> 상태: CPU 준비 확인 · Kit 미실행 · 환경 설정 import 미확인 · 본 실행 금지

# EX-42 준비 작업 보고

## 근거 대조

정본은 `origin/feature/fable-25a-jay` HEAD `0b1bf8d3704709d34af4dbca0d842044a5bb2039`, EX-42 절 v0.14 단위 커밋 `a7407329`다. 초안은 `DESIGN-EX42-TERRAIN-draft.md` v0.4.6, 단위 기록은 `D:/mai-tmp/planner/COMMENT-555-EX42v014.md`, analyst 확인은 `D:/mai-tmp/analyst/REVIEW-EX42-v013-1103.md`다. `ex42_canon_check.py`를 읽기 전용 스냅샷에 실행한 결과 `어긋남 0`이었다.

정본의 10단계는 E0 · E1 · E1F · E2 · E3 · E4 · E5 · M · E6a · E6b다. 계획 파일에는 각 단계 최소/최대 회차와 연장, 가능한 단일 경계 축, 환경 3,072개, 종류별 승급 창, 26개 판정 칸과 13개 기록 칸을 옮겼다. terrain manifest 계약은 5개 family에 대해 종류별 원본/학습/평가 치수, preset ID, geometry SHA, 메모리 · 생성 시간 · ray 처리 실측을 요구한다. 평가 전용 크기는 배율을 정본이 정하지 않아 아직 수치를 채우지 않았다.

## 팀장 미결 칸

아래 값은 승인된 기준으로 사용하지 않는다. 현재 표에서 모두 `approved: false`로 두었고 런타임 통합이 준비되지 않아 시작을 막는다.

- 최소 유효 env 48, 추종 오차 증가 0.03 m/s 및 0.05 rad/s 등 유지표의 E.5 가정값 승인
- 기록 전용 지표를 판정 지표로 올릴지 여부
- 조건부 명령 몫의 분모와 기본 배분
- 듬성 지형 후진 · 옆 명령의 완료 정의, 옆 · 고난도 종류의 완료 정의
- W48 계단 치수, Q4 두 창의 반복 폭과 결과 전 고정값
- 평가 지형의 실제 크기 배율과 family D preset

별도 단계: D113 JEPLO preset 구현은 정본에서 analyst 책임이다. 요청 기준 runner HEAD에는 `jeplo_preset_v1`, `start_go2_v1`, `ame2_go2_mix_v1`의 구현을 찾지 못했다. 이 세 preset의 실제 geometry를 만들어 냈다고 보고하지 않는다.

## 변경 내용

- `foothold_s2/curriculum/ex42-prep.yaml`: 정본의 EX-42 10단계 회차 틀, Go2 학습 preset 자리, 평가 전용 대형 지형 자리, 39칸 평가 계약, 미결 승인값을 `preparation_only` 표로 기록.
- `foothold_s2/curriculum/ex42-boundary.yaml` 및 `ex42-approvals.yaml`: W72와 같은 커밋 스냅샷 계약용 기본 문서. 승인 · 생산 기동 · 자동 기동 모두 닫힘.
- `foothold_s2/curriculum/ex42_prep.py`: 계획 파서, 지형 manifest 검증, 동일 clean HEAD의 boundary/approval 읽기, 승인된 단일 축 변경 검사, 26+13 점수 값 보존 계약.
- `foothold_s2/curriculum/continuous.py`: EX-42 형식을 EX-40/41 계획으로 오인하지 않고 준비 전용 계획으로 읽으며, 훈련 runtime 연결은 명시적으로 거절.
- `foothold_s2/scripts/ex42_preflight.py`: 실제 CLI parser와 Gym task 등록, 등록된 env cfg 클래스 AST, Kit module-scope import 금지, 준비/승인 blocker 출력.

## 확인 결과와 제한

`isaac311`에서 `test_ex42_prep_cpu.py`: 8 passed. W72 경로 CPU 시험은 임시 Git 저장소에서 두 파일이 같은 clean 커밋에 있을 때만 snapshot을 읽고, 승인된 단일 축의 변경은 통과, 미커밋 변경은 거절했다. 점수 payload 시험은 26 judge + 13 record-only 값을 보존한다. `ex42_preflight --dry-run --check-env-registration`는 실제 Gym 등록 `FootholdS2-Go2-S2-SB-v0`와 `FootholdS2SBEnvCfg` 클래스 AST를 확인했고 예상 blockers `runtime_integration_pending`, `explicit_lead_approval_missing`, `ex41_graduation_receipt_missing`, `terrain_manifest_missing`, `design_assumptions_pending`을 냈다.

기본 시스템 Python에는 `gymnasium`이 없어 같은 CPU 시험이 실패했지만, 지정 실행 환경 `C:/Users/AI-WS01/anaconda3/envs/isaac311/python.exe`에서 다시 실행해 통과했다. 실제 `s2_sb_cfg` Python import는 `ModuleNotFoundError: pxr`로 실패했다. 설치 `isaacsim` import는 EULA/bootstrap 프롬프트를 표시해 Kit 없이 진행할 수 없었으므로 재시도하지 않았다. 새 Kit/GPU 실행은 없었다. 따라서 실제 env cfg import, terrain 생성 · 치수, runtime의 stage consumer, 점수 파일 생산자 연결, Kit smoke는 미확인이다. 준비용 경로는 본 학습을 시작할 수 있는 완성 launcher가 아니다.

## 시험

```text
8 passed in 3.69s (isaac311)
system Python: 1 failed because gymnasium is not installed; rerun with isaac311 passed
ex42_canon_check.py: 어긋남 0
CLI: state=blocked, env registration 확인, import_boundary.kit_imports_at_module_scope=0
git diff --check: 통과
```

작업 가지 `feature/ex42-prep-runner`, 기준 `2ee5dc0023dd6d6b5f9c0b90a9344acfd39f11bf`. Kit, GPU, 학습, EX-41 고정 사본, 실행 중 프로세스는 건드리지 않았다.
