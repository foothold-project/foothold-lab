# S2 step17 · 평가 update 0 및 발 광선 참석 기동 도구 보고
> 분류: A/정책학습
> 작성: sol · 2026-10-16
> 근거: TASK-codex-worker-s2-launchers-n3-n4.md · VERIFY-astra-17ai.md 3절 · step16 번들 · CPU 시험 로그
> 요지: 노드 3·4의 참석 기동 도구를 만들고, 캐시 폐쇄 및 실제 디스크 점검을 고쳤다.
> 상태: CPU 확인됨 · GPU/Isaac 미기동 · lead 리허설 및 직접 동의 대기

## 산출물과 경계

- `bundle/`은 `s2_step16`의 1586개 파일을 바이트 그대로 복사했다. 자체 해시 목록 `S2-STEP16-SHA256SUMS.txt`의 SHA `b3fb34d066a6f916d5a4aec93d2dd6b844b3a7ea55f637a8cf5f12f5f2ef6312`를 그대로 핀한다. 목록 1585행 중 Python 원본·데이터 1572행의 존재와 SHA를 검사하고, `__pycache__/` 아래 또는 `.pyc`인 13행은 캐시로 취급해 존재와 SHA를 요구하지 않는다. 번들 파일은 고치지 않았다.
- `launch/s2_attended_launch_eval0.py`는 E1 `model_20000.pt` SHA `c8951b79…`에서 새 시도마다 A/B S2 update 0 파일을 `in/`에 만든다. 두 파일의 completed/next update 0, optimizer slot 및 step 0, `full_freeze`, plan/env/parent 핀과 학습 정책 대 로더의 고정 action/value 완전 일치를 CPU에서 검사한다. 기존 체크포인트 경로는 거절한다. step16 로더가 요구하는 `plumbing_meta` 컨테이너를 사용하며, 그 `manifest_sha256`에는 각 arm의 고정 short 요청 SHA를 기록했다. 실행 manifest의 순환 SHA로 해석해서는 안 된다.
- 평가 case는 gap 2, stepping_stones 2, flat/stairs_up 0, 명령 `fwd10`, 결정적 추론이다. 평가 seed 3101·3109·3119·3121은 학습 seed 11·7·42·1043 및 B 요청의 모든 seed와 교집합이 없음을 봉인 시 재검사한다. URDF SHA `f130b1d2…`, terrain source SHA `0009e1e1…`, 새 USD wrapper SHA, 코드 폐쇄 해시, `expect_conversions=any`, 상한 8을 함께 봉인한다.
- `launch/s2_attended_launch_foot.py`는 `s2_foot_kit_check_once`, 분석적 8장면, N=2, 각 장면 2~37 step, 총 300 이하, 학습·optimizer 0을 봉인한다. 요청에는 팀장 지정 hit XY/Z 및 충돌 중심 0.001 m, 경계군 0.005 m·0.002 m·0.05 N을 적는다. 현재 step16 발 드라이버의 검사 기준과 같은 값이지만 요청 필드 자체를 드라이버가 따로 읽지는 않는다.
- 두 도구는 새 빈 시도 루트, 고유 claim, 상태·STOP, 900초 이하 wall 및 절대 마감, GPU 0 UUID/bus, 자원 하한, GPU lease, 기존 USD lock, 독립 watchdog 등록, `s2_family_observer.py` 기준선·사후 검사를 사용한다. `--rehearse`는 봉인·검증·실제 자원 prelaunch에서 끝나며 감독기/Kit을 띄우지 않는다. `--live`는 attendee, 확인 문자열, 일치하는 scope의 직접 동의 파일과 45초 이내 GO를 요구한다. supervisor와 watchdog은 각 1회만 시작한다. Ctrl+C는 STOP을 써서 소유 가족 정리를 기다린다. 자동 재시도는 없다. 승인 JSON은 납품하지 않았고 live 시도 안에서만 직접 동의 파일로 만든다.
- `S2-GPU-CHAIN.md`에 네 노드와 노드 사이 lead의 원자료 확인, 17ai 3절 실패 분기, 최대 wall 900+600+900+900=3300초 및 미측정 준비·확인 시간을 적었다.

## CPU 시험

`CUDA_VISIBLE_DEVICES=-1`, `C:/Users/AI-WS01/anaconda3/envs/isaac311-moects/python.exe -I -B`로 실행했다. 실제 GPU probe, Isaac, Kit, 감독기를 시작하지 않았다. 정적 검증과 부모 체크포인트의 CPU 로드·저장, GPU 샘플 주입, 실제 디스크 조회·GPU lease·기존 USD 잠금의 획득과 해제, 가짜 감독기/watchdog를 실행했다.

| 관문 | 결과 | 증거 |
|---|---:|---|
| 새 도구 정상 | 31 PASS | `evidence/normal.log` |
| 새 도구 정상 단계 반례 | 12 CAUGHT, 각 지정 첫 실패 | `evidence/normal.log` |
| 지정 소스 변이 | 6/6 CAUGHT, `first_FAIL=want` | `evidence/mutants.log` |
| 캐시 폐쇄 보정 | 정상 5 PASS, 반례·변이 3 CAUGHT, `first_FAIL=want` | `evidence/cache_closure.log` |
| 두 CLI `-I -B --help` | 각각 rc 0 | 이 보고 직전 재실행 |
| B 전체 깨끗한 복사본 | 52/52 파일, 정상 40파일 PASS 356·CAUGHT 3, 변이 12파일 PASS 2·CAUGHT 84 | `evidence/b_regression/summary.json`, 파일별 로그 52개 |
| step17 납품 SHA | 1641/1641행, CR 0 | `S2-STEP17-SHA256SUMS.txt`, `verify_step17_hashes.py` |

정상 시험은 발 8장면과 범위 검증, 실제 E1 부모를 이용한 새 A/B update 0 체크포인트의 로더 및 고정 forward, 두 도구의 가짜 `--rehearse` 감독기 0회, 가짜 live 감독기·watchdog 각 1회, watchdog PID/manifest 결합과 사후 관찰 호출을 포함한다. 반례는 동의 누락·scope 불일치, 45초 초과 GO, 관찰자 기준선/사후 실패, 기존 출력 재사용을 지정 오류에서 거절한다. 소스 변이는 scope 불일치 허용, GO 나이 검사 제거, 관찰자 실패 무시, 자동 재시도 허용, 기존 체크포인트 재사용, 평가 seed 중복 허용이다. 변이 단계의 선행 PASS와 정상 단계의 CAUGHT는 합산하지 않았다.

캐시 보정 시험은 번들 전체를 임시 사본으로 복사해 고정 목록의 pyc 13개를 전부 삭제한 뒤 통과를 확인했다. 이어 목록에 있던 pyc의 다른 바이트와 새 pyc 두 곳을 허용했고, `s2_eval_cpu.py`의 바이트 변경과 누락을 각각 `step16_bundle_changed:s2_eval_cpu.py`에서 거절했다. 고정 목록 자체를 바꾸면 `step16_hash_list_changed`에서 거절했다. 임시 사본만 수정했으며 납품 번들은 수정하지 않았다. 원본 `s2_step16`과 납품 `bundle/`의 전체 1586파일 SHA도 1586/1586 일치를 다시 확인했다. 기존 B 전체 회귀 결과는 번들 불변으로 유지했고, 이번 좁은 launcher 수정 뒤에는 새 도구 정상·변이 시험을 다시 실행했다.

실제 리허설에서 `disk_probe_failed`가 난 원인은 `new_run()`이 `log_path`의 부모 `logs/`를 만들지 않은 것이었다. `new_run()`은 이제 `in/`, `ctl/`, `logs/`만 만든다. `out/`, `ctl/claims`, `child.log`는 미리 만들지 않는다. 시험은 예전 구조의 새 폴더에서 실제 `disk_free(logs)`가 지정 첫 실패 `disk_probe_failed`를 내는 반례를 확인했다. 고친 새 시도에서는 발 광선과 평가기 각각 실제 `disk_free`가 유효한 여유 바이트를 반환하고, 실제 manifest 검증·GPU lease·기존 USD byte lock을 지나는 `prelaunch`가 `GO`를 냈다. 두 lease는 해제 뒤 재획득했고 기존 USD 잠금 파일 SHA는 전후 일치했다. 두 래퍼의 `execute(--rehearse)` 경로도 실제 번들 검사와 같은 CPU 단계로 `GO`를 기록했다. 이때 GPU 샘플만 주입했고 NVML 생성은 시험에서 금지했다. 감독기·watchdog는 시작하지 않았으며 claim·out·child.log는 남지 않았다. 실제 GPU 0 계측과 Kit 결과는 미확인이다. `evidence/normal.log`에 정상 31 PASS와 반례 12 CAUGHT가 있으며 지정 변이 6/6, 캐시 5 PASS·3 CAUGHT도 재실행했다.

## lead 인도와 미확인

lead는 두 CLI에 `--max-wall-s`, 네 자원 상한·하한을 명시하고, 발 도구에는 `--seed`, `--steps-per-scene`을 추가해야 한다. 기본 자원 결정을 넣지 않았다. 리허설의 실제 GPU 0 identity/free VRAM, 임대·USD 잠금 GO와 실제 Kit의 평가 case 짝 지문, 자연 종료, 발 광선의 USD geometry·RewardManager·reset은 **미확인**이다. CPU GO를 실제 GPU GO로 전하지 않는다. 두 도구의 live는 해당 scope의 직접 동의 파일이 없으면 시작하지 않는다.

회귀용 별도 작업 복사본 `codexE/s2_step17_regression_work/`는 증거를 `evidence/b_regression/`에 해시 대조해 복사한 뒤 남아 있다. 자동 승인 검토가 재귀 삭제와 캐시 파일 삭제를 거부해 정리를 더 진행하지 않았다. 이 폴더는 납품 `s2_step17/` 번들과 무관하다. `launch/__pycache__/`의 오래된 pyc 네 개도 남았으며 SHA 목록에서 제외했다. 실행은 `-B`로 검증했다.
