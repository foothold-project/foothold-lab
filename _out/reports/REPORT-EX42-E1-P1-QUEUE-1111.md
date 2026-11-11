# EX-42 E1 P1 경계 평가 큐 준비

> 분류: 운영
> 작성: runner-lx · 2026-11-11 15:06
> 근거: lead-lx 15:07 지시 · E1 P1 계약 #623 · D44 #664
> 요지: E1 종료 후 m250·500·750·1000 평가를 고정 checkout에서 등록할 수 있게 명령 생성기와 선행 완료 게이트를 준비했다.
> 상태: CPU 확인됨 · Kit 미실행

## 준비한 실행 순서

새 `foothold_s2.scripts.ex42_e1_boundary_queue` 명령은 E1 종료 뒤 잠긴 고정 checkout에서만 계획을 만든다. `--e1-ended`를 요구하고, manifest 진행값이 1000 이상인지, `model_250.pt`부터 `model_1000.pt`까지 각 파일 SHA가 manifest와 맞는지, 네 출력 위치와 완료 표식이 새 위치인지 확인한다. 실행 소스가 깨끗하고 읽기 전용으로 잠겼는지도 검사한다.

| 저장본 | 장치 | 큐 우선순위 | 선행 조건 |
|---|---:|---:|---|
| m250 | cuda:0 | P1 | 없음 |
| m500 | cuda:1 | P1 | m250 성공 표식 |
| m750 | cuda:0 | P1 | m500 성공 표식 |
| m1000 | cuda:1 | P1 | m750 성공 표식 |

각 항목은 `foothold_s2.ex42_eval_once --p1-stage-id E1 --sha-from-manifest --execute`를 부른다. E1 P1 판정에는 기존 26칸 평가와 D44 착지 평가가 들어간다. D44 계약의 6개 judge case와 3개 record-only case를 확인했다. 각 자식 평가의 성공 영수증을 검사한 뒤에만 wrapper가 고유한 완료 표식을 쓴다. 후속 큐 항목은 dispatcher의 `wait_present`로 그 표식을 기다린다. 비정상 종료나 영수증 누락이면 표식이 생기지 않아 뒤 경계가 먼저 출발하지 않는다.

일반 map64용 E0 통합 메시와 D44 착지 타일은 서로 다른 자료다. 생성기는 전자를 `terrain_manifest_measurements`의 상대 경로와 SHA에서 읽고, 후자는 D44 계약의 `source_mesh_dir`와 SHA로 별도 검증한다. 실제 디스크의 CPU 검사 결과는 E0 메시 `88197b3a…12a95`, D44 타일 `baa59af3…febb82`로 각각 계약과 일치했다.

## 실행 방법

E1 종료 뒤 lead가 새 고정 checkout을 만들고 잠근 다음, 그 checkout에서 아래 명령으로 큐 등록 payload를 생성한다. 이 명령은 실제 큐를 변경하지 않고 JSON에 네 개의 `queue_add_shell`을 기록한다.

```bash
set -a; source ~/mai/foothold-linux.env; set +a
export FOOTHOLD_OPS_MACHINE_PROFILE="$HOME/mai/tmp/lead/ops/AI-WS01-linux-ops.json"
cd "$FIXED_REPO"
"$ISAAC311_PYTHON" -m foothold_s2.scripts.ex42_e1_boundary_queue \
  --repo "$PWD" --e1-run "$E1_RUN" --e1-ended \
  --out-json "$MAI_TMP_ROOT/runner/ex42-e1-boundary-queue.json"
```

실제 등록은 생성 결과를 검토한 뒤 lead가 수행한다. 읽기 전용 큐 확인에서 옛 코드 항목 `id=4` m250과 `id=5` m500이 대기 중인 것을 확인해 취소 대상으로 기록한다. 두 항목은 직접 취소하지 않았다. 지금 확인한 큐에는 m750/m1000 옛 코드 항목이 없었다. 이후 같은 옛 사슬로 추가되면 해당 항목도 lead가 취소 대상으로 처리한다.

이전에 요청한 W09 baseline, W08 반복, W14/W19 측정과 단계 예행은 scripter flag 판정과 sonnet #670이 올 때까지 이 payload에서 제외했다. 실제 E1 run 경로가 아직 전달되지 않았으므로 실행별 payload 생성과 queue 등록은 미실행이다. GPU와 Kit도 사용하지 않았다.

## 검증

- E1 큐 builder/wrapper, post-E1 chain, E1 judge, D44 CPU 검사 및 dispatcher 전체 시험: 141 passed, 5 skipped.
- 새 Python 파일 `py_compile` 및 `pyflakes`: 통과.
- E0 통합 메시 및 D44 착지 타일의 실제 파일을 CPU preflight/source-tile로 읽어 SHA 확인: 통과.
- 등록 payload 4개를 임시 복사 큐에 추가하고 `wait_present` 직렬화 확인: 통과. 실제 `queue.json`은 읽거나 변경하지 않았다.
