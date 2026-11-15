> 분류: A/평가 · Codex Worker 1043 CPU 후보 보고
> 작성: Codex Worker · 2026-10-14 10:55
> 근거: TASK-codex-worker-1043-eval-build.md · VERIFY-astra-17q.md · codexE 후보·시험 로그·SHA256SUMS.txt
> 요지: 1043 평가 manifest·비교기·A 전용 드라이버·후처리기를 이식하고 CPU 합성·복사본 시험을 마쳤다
> 상태: CPU 후보 제작·자체 시험 완료 · 독립 검토 미실시 · 실제 GPU·Isaac 기동 불가

# 1043 평가 새 판 제작 보고

## 결과와 범위

`cand/manifest_s1043.json` 계약 해시는 `1cbfb526b7453b1196cadb11087b110d7a604137ddac29426d552974f62172a6`이다. 학습 seed 1043, 부모 E1 20,000, off/on 22,000·24,000의 등록 경로와 해시, A 45회, base 555회, B 잔여 510회, 선별 96칸과 최대 추가 768회를 기록했다. 첫 배포 코드는 **A 45회만 허용**하며 B·remeasure 호출은 rc 8로 거절한다. GPU index·UUID, 마감, 위험 한도, 승인, 공통 lease 참가, 변환 잠금 공유, torch·Isaac 런타임 등은 `UNDECIDED`다. 현재 manifest로 실제 기동을 시도한 CPU 시험은 rc 4로 차단됐다.

후보는 `cand/`의 `s1043_manifest.py`, `cmdr_bundle_compare_s1043.py`, `cmdr_eval_driver_s1043.py`, `frozen_exec_s1043.py`, `cmdr_post_s1043.py`다. 원본 v37·post v10·비교기는 `_eval`에서 읽기만 했고 SHA256은 각각 `c351fde3…`, `dea9ca7b…`, `bb827f3c…`로 재확인했다. 전체 변경은 `cand/diff-driver.patch`, `cand/diff-post.patch`, 설명은 `CHANGES-driver.md`, `CHANGES-post.md`에 있다. 원본의 1042 로그·hold·legacy stamp·승인 경로는 새 post에 연결하지 않았다.

| 갈래 | 구현한 내용 | CPU 확인 |
|---|---|---|
| ① manifest·경로 | 입력·설정·두 군 종료 증거·출력 경로를 등록하고 쓰기 경로를 codexE 아래로 제한. q에 `--outdir` 명시 | 격리·A 45·B 510, 출력 루트 회귀 거절 |
| ② 기동 관문 | slot v3 전용 registry·변환 잠금, 별도 전체 실행 lease, 물리 GPU UUID·여유 검사, slot 대기 뒤 frozen 자식 입력 재검사 | v2 registry·분리 잠금·대기 뒤 입력 변경 거절. 실제 slot·GPU 동작은 미확인 |
| ③ 출처·단계 | 양 군 결과·stamp·bundle·종료 로그 검증, 부모 포함 A 45개, 새 attempt·stamp·해시와 고유 tag만 수용 | 복사본 전체 입력 정상 0오류, bundle·stamp·result 변조 거절, 1042 출처·부모 누락·중복 거절 |
| ④ 판정·표시 | post v10 통계 함수를 유지하고 A 완전성 관문, seed 1043 범위 문구, 결과 파일별 원자 교체 추가 | 정상 합성 A 45개 집계와 v10 주요 집계 10항목 일치, 경계값 3개 확인 |

## 시험 결과

모든 시험은 `C:/Users/AI-WS01/anaconda3/envs/isaac311-moects/python.exe -B`, `CUDA_VISIBLE_DEVICES=-1`로 실행했다. 진입점과 후보는 해석기·`__file__`·SHA256을 출력했고 경로를 검사했다. 합성·복사 입력과 출력은 모두 `codexE/` 아래다. 원본 post v10은 읽기 전용 실행했고 환경 변수로 입력과 출력만 codexE에 지정했다.

| 증거 | 결과 | 핵심 관측 |
|---|---:|---|
| `fixture_synth/integrated_2/test_results.json` | 33/33 | 정상 CLI 먼저, v10 논리 10항목 일치, 반례·경계값·기동 거절, 변이 6개 `CAUGHT` |
| `fixture_real/complete/full3/test_results.json` | 9/9 | 모든 등록 입력과 양 군 stamp 목록 9개씩의 복사본 정상 0오류, bundle·stamp·result 변조, 1042 승인 거절 |
| `cand/reports/stage1_results_final2.json` | 5/5 | 실제 1043 bundle 복사본 정상 두 번 `SAME` rc 0, seed 1042·부모 해시·한 군 NPZ 변조 `DIFFERENT` rc 1 |
| `cand/reports/driver_cpu_final2.json` | 5/5 | A 45 고유 태그, B 510, B·remeasure rc 8, 자기 해시 오류 rc 3, q 경로·모델 역할 |
| `cand/test_manifest.py` | 통과 | 계획 수·격리·계약 해시 변조·미정 기동 거절 |

합성 정상 결과는 24,000 목표 세 칸의 동등 가중 결합 차이 **정확히 +10.0 %p**와 세 칸 Tango 구간 하한 > 0에서 `개선`이었다. +9.9333 %p는 `개선 아님`, 한 칸 하한 0도 `개선 아님`으로 나왔다. 이는 합성 알려진 답이며 **실제 1043 성능 결과가 아니다**. A 시점의 회귀 범위는 3/99칸 측정, 96칸과 22,000은 미평가다. 부모 대비는 별도 표시한다. 학습 seed 하나를 일반 효과로, 짝지은 판을 독립 1,000개로 주장하지 않는다.

반례는 1042 모델·로그·stamp·승인·hold 주입, on만 완료, 부모 해시 오류, bundle·stamp 변경, `_eval/out`으로 출력 경로 회귀, GPU index 0과 틀린 UUID, v2 registry·분리 변환 잠금, slot 대기 뒤 입력 변경, 중복 tag, 누락·중복 episode, 짝 지문·pin·출력 바이트 불일치, manifest 미정 값, B·remeasure 호출을 포함한다. post 반례는 비정상 종료 후 새 보고 파일이 없음을 확인했다. 변이 6개는 각각 정상 입력이 원본 코드에서 먼저 통과한 뒤 장치·짝·episode·경로·출력 해시·pin 검사 한 곳을 껐을 때 지정 반례가 잘못 통과해야만 `CAUGHT`로 셌다. `SKIP`·`HOLD`로 통과 분모를 채운 항목은 없다. GPU 실행의 skip·hold·중단 코드는 실제로 재지 않았다.

처음 실패는 별도로 남긴다. 비교기 초기 정상 입력의 Windows 경로 표기 차이, driver 시험의 cp949 디코딩 오류, post 첫 합성 실행의 남은 `changed` 변수 `NameError`, 전체 입력 첫 복사의 `saves.json` 누락이었다. 각각 수정 후 새 실행 ID로 정상·반례를 다시 확인했고 앞선 실패는 위 통과 분모에 포함하지 않았다. 1042 승인 검사 보강 후 통합 33/33과 전체 입력 9/9를 다시 실행했다.

## 미확인 · 다음 관문

실제 GPU·Isaac·slot v3 자식 연쇄, 공통 lease에 다른 기동 경로가 모두 참여하는지, 공통 변환 잠금의 운영 경로, 물리 버퍼 동등성, reset과 관측 history의 GPU 알려진 답, 대표 run 시간·peak, 1043 정책 성능은 **미확인**이다. `GPU-PLAN.md`에 시작 전 대조와 중단 순서를 적었다. 독립 검토 및 운영 반영은 lead의 별도 판단이다. 미정 값을 임의로 채우거나 관문을 삭제하지 않았다.

이번 작업은 약 10:15~10:55 KST, 약 40분의 CPU 후보 제작·자체 시험이다. 작업서의 8.5~16시간은 전체 구현·검토 사전 견적이며 GPU 검증 시간이 포함된 실측값으로 읽지 않는다. 이번 명령으로 `_eval` 안에 만든 파일 0개, 수정한 파일 0개다. Git 저장소에도 쓰지 않았고 커밋·pull·push를 하지 않았다.

## 재실행

```powershell
$env:CUDA_VISIBLE_DEVICES='-1'
$p='C:/Users/AI-WS01/anaconda3/envs/isaac311-moects/python.exe'
$c='C:/Users/AI-WS01/.claude/jobs/09bbf294/tmp/codexE/cand'
& $p -B "$c/test_manifest.py"
& $p -B "$c/test_stage1.py" --run-id review_unique_1
& $p -B "$c/test_driver_cpu.py" --run-id review_unique_1
& $p -B "$c/test_full_inputs_copy.py" --run-id review_unique_1
& $p -B "$c/test_integration_s1043.py" --run-id review_unique_1
```

각 `--run-id`는 기존 증거를 덮지 않도록 새 값을 쓴다. 해시 목록은 `SHA256SUMS.txt`에 있다. #550 요약 댓글은 [6159198847](https://github.com/foothold-project/foothold-lab/issues/550#issuecomment-6159198847)이며 GitHub API 되읽기에서 `ISSUE_550 True`, `BODY_MATCH True`를 확인했다.
