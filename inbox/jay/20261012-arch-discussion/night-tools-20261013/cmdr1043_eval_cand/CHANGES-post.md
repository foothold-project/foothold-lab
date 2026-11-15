> 분류: A/평가
> 작성: Codex · 2026-10-14
> 근거: `_eval/cmdr_post_v10.py` 읽기 전용 원본 · `VERIFY-astra-17q.md` · `TASK-codex-worker-1043-eval-build.md`
> 요지: 1043 A 45회 전용 후처리기 이식 변경과 제외 경로
> 상태: CPU 합성 정상 실행 확인 · GPU 자료 미확인

# 1043 후처리기 변경

원본 SHA256 `dea9ca7bfe01b92b634aa85048ff0cb4128b4eaa3b7943030a9a9b5660332dc2`. 전체 차이는 `cand/diff-post.patch`에 있다.

## ① manifest · 경로

`load_manifest`, `check_inputs`, `inside`를 호출한다. 실험, 계획, seed, A 로그, 입력·출력 루트를 등록 계약에서 받는다. `--manifest`, `--expect_self_sha`를 요구하며 해석기·후보 경로·후보 SHA를 출력한다. 결과 JSON과 Markdown은 등록된 `reports` 아래에 임시 파일을 쓴 뒤 각각 원자 교체한다. 1042용 환경 변수 출력·hold 우회는 거절한다.

## ② 출처 · 수집 검증

기존 두 로그 병합을 `s1043A_base` 한 로그로 제한했다. 실험·계약·판·A 단계, 완결 상태, 부모 포함 45개의 고유 태그와 유효 기록, sidecar attempt, 코드·설정 pin, 체크포인트, 새 stamp·collection attempt·네 출력 해시를 대조한다. `load`는 episode ID 0..99 및 같은 cell을 요구한다. meta의 모델 경로·해시, 1043 명령·noise·seed·outdir, 장치 index·UUID, 짝 지문을 확인한다. `read_run`의 읽기 전후 stat과 발행 직전 로그·attempt·파일 재확인은 유지한다.

## ③ 판정 · 표현

`paired`, `pooled`, `compare`, `mae_status`, `joint_verdict`, `regression_tag` 등 v10 통계 함수는 보존했다. A만 있으면 24,000 목표 세 칸의 500쌍 결합 판정을 낸다. 부모 대비는 별도 표기한다. 출력 schema·표 제목을 1043 A1로 바꾸고 seed 1043, 3/99칸 측정, 96칸 및 22,000 미평가 문구를 계약에서 강제한다. 학습 seed를 일반 효과나 독립 episode 1,000개로 표현하지 않는다.

## ④ 가져오지 않은 기능 · 시험 한계

v3.2 legacy stamp, 1042 hold·release·승인 JSON, 두 번째 remeasure 로그, B와 선택 재측정 결과의 발행을 가져오지 않았다. `--cpu_fixture`는 합성 입력의 파일 존재 확인만 완화하며 A 로그·stamp·집계 관문은 그대로 거친다. 이 플래그로 낸 결과는 실측이 아니다. 정상 합성 45개의 새 CLI 결과와 원본 v10의 목표·시작·칸·Holm·완료·회귀·기본 계약 등 10개 집계 항목이 같았다. 반례와 변이는 다음 단계에서 실행한다.
