> 분류: A/정책학습 · ASTRA 의뢰 17aa · S2 첫 수집 두 번째 시도 허용 여부 (환경 변수 한 줄 수정)
> 작성: 오흥재 (lead 세션 · Claude 작성) · 2026-10-15 14:05
> 근거: 17y 참석 단회 조건 · 첫 시도 증거 `night-tools-20261013/s2_stage0_first_collection/attempt1_20261015_1403/` · Kit 소스 `isaacsim/kit/kit_app.py:15~40`
> 요지: 14:03 에 17y 조건대로 GPU 0 참석 단회를 한 번 띄웠으나 자식이 0.2 초 만에 죽었다 (Kit EULA 프롬프트가 stdin 이 없어 실패). 원인은 환경 변수 `OMNI_KIT_ACCEPT_EULA` 를 안 준 것 하나다. 같은 조건에서 환경 변수 두 개만 더해 한 번 더 띄워도 되는지 매우 좁게 판정해 달라
> 상태: 의뢰 (팀장이 지금 채팅에 있음 · GPU 둘 다 계산 0 · 승인 json 없음)

# ASTRA 17aa

비판적이면서도 냉정하고 현실적인 전문가로서 답해 주십시오. 한도(주간 4 %)가 낮으니 이 한 가지만 보십시오. 분량 `VERIFY-astra-17aa.md` 한 파일, 첫 줄 한 문장 판정. 코드 수정 · GPU · Isaac · 커밋 금지, em dash 금지.

## 사실 (직접 읽을 것)

- **첫 시도(attempt one) 결과: 시작 실패 · 원시 행 0 · 정상 완료 걸음 0.** 14:03:14 기동 도구 → prelaunch GO(0.7 초) → 감독기 pid 169356 → 자식 종료 코드 42 → 영수증 `HOLD_INFORMATION_ONLY` 사유 `artifact_missing · exit_code · step_count`, `family_active_count=0`. 총 2 초. GPU 0 메모리는 15 MiB 에서 한 번도 안 올라감. 출력: `out/failure.json` · `out/launch.json` · `logs/child.log` · 감독기 영수증 · `launcher_summary.json`.
- **직접 원인(child.log):** `isaacsim/kit/kit_app.py:34 check_eula()` 의 `input("Do you accept the EULA? (Yes/No): ")` 가 `RuntimeError: input(): lost sys.stdin` 으로 죽고 `SystemExit: Unable to bootstrap inner kit kernel`. `kit_app.py:19` 는 `OMNI_KIT_ACCEPT_EULA` 가 `y/yes/1` 이면 프롬프트 없이 통과시킨다. 이 저장소의 동작하던 Isaac 기동기는 모두 이 변수를 준다 (`_eval/unseen_driver_cmdr_v6.py:105`, `_eval/run_e2.sh:18` 등, `PYTHONUNBUFFERED=1` 도 같이).
- **A3 감독기는 자식 환경을 `os.environ.copy()` 에 `CUDA_VISIBLE_DEVICES` · `CUDA_DEVICE_ORDER` · `FOOTHOLD_USD_ROOT` · `FOOTHOLD_EXPECT_CONVERSIONS` 만 더해 만든다.** 이 변수는 감독기 프로세스의 환경을 통해서만 들어갈 수 있다.
- **lead 의 수정(A3 바이트는 그대로, 47/47):** 기동 도구 `s2_attended_launch_a3.py` 가 감독기를 띄울 때 `env={**os.environ, "OMNI_KIT_ACCEPT_EULA": "YES", "PYTHONUNBUFFERED": "1"}` 를 준다. 이 두 줄 외 모든 입력(GPU 0 UUID/bus · 8 환경 · 256 step · 변환 0 · 서로 다른 세 출력 폴더 · 해시 · 마감 · 참석 조건)은 17y 그대로. 새 chain/attempt id 와 새 run 폴더가 시각으로 만들어지며 첫 시도의 claim 은 지우지 않았다.

## 물음 (둘)

1. **17y 의 참석 단회 조건으로, 위 환경 변수 두 개만 더한 두 번째 시도를 허용하는가.** 17y 는 retry 0 이었으므로 새 승인 범위가 필요한지, 허용한다면 조건(참석 확인 방식 · 중단 조건)에 바꿀 것이 있는지.
2. **자식 환경에서 더 확인할 차이가 있는가.** 동작하던 기동기와 이 감독기의 자식 환경 · stdin 처리(`JobOwner` 가 stdin 을 닫음) 차이 중 Kit 시작 전에 또 막을 만한 것이 보이면 한 줄씩. 못 본 것은 「미확인」 으로.

## 결과
- `inbox/jay/20261012-arch-discussion/VERIFY-astra-17aa.md` 한 파일. 표기: 확인됨 · 추정 · 미확인.
