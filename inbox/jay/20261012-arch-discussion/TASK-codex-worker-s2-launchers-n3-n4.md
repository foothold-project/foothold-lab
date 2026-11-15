> 분류: A/정책학습 · Codex Worker 작업서 (sol) · 네 노드 중 3 · 4 (평가기 update 0 연결, 발 광선 확인)의 참석 기동 도구 (step17)
> 작성: 오흥재 (lead 세션 · Claude 작성) · 2026-10-16 22:19
> 근거: `VERIFY-astra-17ai.md` 3절(한 번의 직접 동의로 A3.4 → 배관 → 평가기 → 발 광선 네 노드까지, 노드마다 독립 manifest · 코드 폐쇄 해시 · 입력 SHA · claim · 출력 경로, 노드 사이 lead 확인) · step16 (`s2_eval_scope.py` · `s2_eval_supervisor.py` · `s2_foot_kit_scope.py` · `s2_foot_kit_supervisor.py` · `s2_foot_kit_driver.py`) · lead 의 기존 도구 `night-tools-20261013/s2_step4a3_launch/s2_attended_launch_a34.py` · `s2_attended_launch_b12.py` · `s2_family_observer.py`
> 요지: 노드 1 · 2 (A3.4 수집, 배관 재시도)는 lead 도구가 있고 리허설도 GO 다. 노드 3 · 4 는 감독기와 계약은 있는데 이를 실제로 봉인해 띄울 참석 기동 도구가 없다. 같은 구조로 만들어 lead 가 리허설할 수 있게 한다. 이 작업은 GPU 를 쓰지 않는다
> 상태: 작업 지시 (CPU 만 · GPU · Isaac 기동 금지 · 승인 json 은 만들지 않는다)

# sol 작업서: 노드 3 · 4 참석 기동 도구 (step17)

## 0. 지킬 것

step16 과 같다. 새 사본 `codexE/s2_step17/`: `launch/` 폴더에 도구를, 필요한 번들 파일 변경은 `s2_step16` 사본을 복사한 `bundle/` 에(변경 없이 쓸 수 있으면 변경하지 않는다). `CUDA_VISIBLE_DEVICES=-1`, `C:/Users/AI-WS01/anaconda3/envs/isaac311-moects/python.exe -I -B`. 정상 먼저, 변이는 지정 첫 FAIL. 정상 PASS 와 변이 단계 선행 PASS 를 합쳐 쓰지 않는다. 해시 목록 CR 없이, 번들 안에서 닫히게. 인도 때 B 전체 회귀와 새 도구 시험을 같이 낸다. 도구는 번들 **밖**(`launch/`)에 두고 번들 바이트를 바꾸지 않는다. 승인 JSON 은 만들지 않는다(도구가 lead 의 직접 동의 파일을 받아 매 실행마다 봉인).

## 1. 만들 것

기존 `s2_attended_launch_b12.py` / `s2_attended_launch_a34.py` 의 구조를 따른다: `--rehearse`(봉인 + 검증 + 실제 GPU 0 identity / free VRAM / lease / USD 잠금 prelaunch 까지만, 감독기 미기동), `--live --attendee NAME --confirm LAUNCH-ATTENDED --consent-file ...`(독립 `s2_family_observer.py` 기록 → prelaunch → 감독기 foreground → 관찰자 검증, 상태줄 10초 간격, Ctrl+C STOP, 자동 재시도 없음). 동의 파일은 `by` · `eula_accepted` · `attending_until_end` · `go_for_this_one_run` 이 yes 이고 원문 `quote` · 해당 노드의 `scope` 문자열이 일치해야 한다(scope 이름은 step16 의 감독기 / 범위 파일이 요구하는 값을 읽어서 쓴다).

1. **노드 3: `s2_attended_launch_eval0.py`**
   - 학습 0 의 update 0 체크포인트 A / B 를 E1 부모(`model_20000.pt`, SHA `c8951b79…`)에서 S2 형식으로 만든다(`s2_eval_cpu.py` / step13 의 CPU 저장 경로 재사용). 각 실행의 `in/` 에 저장하고 SHA 를 job 에 핀(plan · encoder_mode `full_freeze` · parent · arm · `completed_updates == 0` · `next_update_index == 0` · optimizer step 0). 기존 파일을 재사용하지 않는다.
   - smoke case JSON 은 gap 2 + stones 2(평지 · stairs_up 0), 평가 seed 는 학습 seed 집합 {11, 7, 42, 1043 및 B 요청의 모든 seed} 와 서로소인 값 네 개를 **도구 안 상수로 고정**해 case 목록을 봉인(`s2_eval_cases.py` 사용), 명령 `fwd10`, 결정적 추론.
   - 새 빈 시도 루트, `expect_conversions=any` · 상한 8, 자산 폐쇄 해시(URDF `f130b1d2…`)와 새 `usd_isolate_run_v3.py` SHA, 900초 이하 마감, `min_free_vram` · 잠금 · lease · claim · STOP 경로를 manifest 에 봉인. 코드 폐쇄 해시는 번들 목록에서 계산.
2. **노드 4: `s2_attended_launch_foot.py`**
   - 요청 `scope=s2_foot_kit_check_once`, 분석적 8장면, N 최대 2, `steps_per_scene` 2~37, 총 300 step 이하, 학습 · optimizer 0, `max_wall_s` 900 이하. lead 결정값(허용치 hit XY / Z 0.001 m 이하, collision 중심 거리 0.001 m 이하, 경계군 0.005 m · ±0.002 m · ±0.05 N)을 요청에 그대로 봉인.
   - 새 빈 시도 루트, 절대 마감, 자원 하한, claim, STOP, 독립 관찰자.
3. **공통:** 두 도구 모두 `--rehearse` 가 감독기를 띄우지 않는다는 것, `--live` 가 동의 파일 없이 / scope 불일치 / prelaunch GO 가 45초보다 오래됨 / 관찰자 기준선 실패에서 시작하지 않는다는 것을 CPU 시험(가짜 prelaunch · 가짜 감독기)으로 닫는다. 변이: 동의 scope 불일치 허용, GO 나이 검사 제거, 관찰자 실패 무시, 자동 재시도 추가, 기존 체크포인트 재사용, 평가 seed 가 학습 seed 와 겹침 허용.
4. **노드 연결 문서** `S2-GPU-CHAIN.md`: 네 노드(A3.4 → 배관 → 평가기 update 0 → 발 광선)의 순서, 노드 사이 lead 가 확인할 원자료 목록, ASTRA 17ai 3절 표(앞 결과별 뒤 노드 처리)를 그대로 옮긴 분기, 각 노드의 최대 시간, 합쳐서 화면 앞에서 보셔야 할 시간 추정(미측정 구간은 미측정으로).

## 2. 끝나면

`REPORT-s2-step17.md` (파일 · 시험 수 · 변이 CAUGHT/전체 · 첫 실패 · 미확인), `S2-STEP17-SHA256SUMS.txt`, #550 댓글 초안(미게시). lead 가 재실행하고 두 도구를 `--rehearse` 로 돌린다. 막히면 추측하지 말고 막힌 줄과 필요한 값을 적는다.
