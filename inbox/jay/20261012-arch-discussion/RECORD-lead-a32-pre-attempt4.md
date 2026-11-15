> 분류: A/정책학습 · lead 검증 기록 (ASTRA 17ac 7절 조건) · S2 0단계 A3.2 · 4차 참석 정보 수집 전
> 작성: 오흥재 (lead 세션 · Claude 작성) · 2026-10-15 16:49
> 근거: `VERIFY-astra-17ac.md` · 3차 증거 `attempt3_20261015_1506/` · 스위트 `A32_suite_summary.json` `A32_suite_stdout.txt` · 기동 예행 GO
> 요지: A3.1 위에 바뀐 파일 8개, 원인과 수정, 정상 대조와 변이, 아직 못 채운 조건을 적는다. 4차는 이 기록과 팀장의 새 동의로만 판단한다
> 상태: CPU 확인됨 · GPU/Isaac 4차 미실행 · PhysX 질의의 실제 동작 · 무중력의 고정 효과 · 질의 속도는 미확인

# A3.2 lead 검증 기록

## 1. 동결 바이트

- 코드 목록 `s2_step4a3/SHA256SUMS.txt` 49줄, SHA256 `98bd193683ba48d8ad2ff4787309db0c8d572e4f0768044e866cda62758ff7f1`. 진단 `s2_connect_diag_17v.py` `065b832c46523977c80430e0abc5bd63a83da30bb86df3c40e6f741ffc549bfc`. 기동 도구 `s2_step4a3_launch/s2_attended_launch_a3.py` `575bcb23373df4d15dd9d459aed18286b1654ab5342413d7c2e7f71b5e5d68c3`.
- A3.1 대비 바뀐 파일(나머지 41개는 A3.1 바이트 그대로):

| 파일 | SHA256 |
|---|---|
| `s2_env_config_17v.py` | `9e9793cbac89fcf18396e85b81896f5d562f0ed24379a36f76a0fcdf43699a04` |
| `s2_connect_check_17v.py` | `c0bc62e407da907fcf493fe1f571fc4889a83764bc69f493d4b3c46534c7d6bd` |
| `s2_connect_diag_17v.py` | `065b832c46523977c80430e0abc5bd63a83da30bb86df3c40e6f741ffc549bfc` |
| `s2_mesh_probe_a2.py` | `d6b3a95aa824053b14190628ddc315401705326d37f25ba7d46ab3e5e0d76daa` |
| `test_s2_connect_a2.py` | `2e90d45f2b88924ccf66269b68d1184f07d2a7f4ad43789324801596987f6bfe` |
| `test_s2_a32.py` | `c76e96c3f6313fc125ea3bb5f90d8b906bafecff2cdd36e2ebca04bef0af3ccf` |
| `test_s2_a32_mutants.py` | `065957800cbeee36d53b0dcec554bc9a19e0a1817de6788eada2c0b91a36383a` |
| `run_all_s2_step4a3.py` | `30ed763e4ef52d4ee4d20502b928434f3a6fdec257ab081fbd5ab972756bfd8c` |

- 해석기 `C:/Users/AI-WS01/anaconda3/envs/isaac311-moects/python.exe` -B, `CUDA_VISIBLE_DEVICES=-1`. 저장소와 `s2_lab` 사본의 49개 해시가 일치(0 bad).

## 2. 원인, 수정, 정상 대조, 반례 기대값

| 3차에서 나온 것 | 수정 | 정상 기대 | 반례 기대(첫 FAIL이 의도한 줄) |
|---|---|---|---|
| 로봇이 16걸음에 0.23 m 움직이고 base_contact로 자동 리셋 5번, gap_90 추락(173행부터 광선 시작점이 지면 아래) | 진단 cfg에서 `disable_gravity=True`와 `terminations.base_contact=None`. 고정을 주장하지 않고 첫 16행을 실측(`fixed_pose_evidence`) | cfg 갱신 · 원본 cfg 불변 · 없는 경로는 ValueError | 중력 켬 → `gravity off`, 종료 유지 → `base_contact removed` |
| 센서 시각이 리셋 때 되감김(음의 차 13곳)을 검사기가 모름 | 예정된 128행에서만 되감김 허용, 그 외 행은 한 제어 step(0.02 s ± 1 ms), 128행 시각은 약 0.02 s, 에피소드는 128행에서 정확히 +1, `termination` `timeout` `reset_mask` 별도 HOLD | 3차의 같은 구조 fixture PASS | 되감김 · 정지 · 두 step 점프 · 리셋 후 이전 버퍼 · 가짜 에피소드 증가 · 예정 밖 종료 · 마커 없음 각각 지정 사유 |
| 광선 자체가 유효한지 안 봄 | `ray_start_xy` `ray_direction` `ray_start_height`(출발 높이 ≥ 표면 +1 m) | fixture PASS | XY 1 cm 어긋남 · 기울어진 방향 · 지면 아래 출발 |
| 경계 1개 차이(float32 대 float64) | 경계 마스크는 검사기와 같은 함수로 재계산하되 **원본 마스크를 `edge_excluded_recorded`로 보존**하고 차이 위치 20개를 meta에 기록 | 5 mm 안팎 알려진 입력: 4.9 mm와 5.1 mm 거리를 oracle이 정확히 읽고 5 mm 컷이 갈라놓음 | 한 칸 차이는 `boundary_mask` |
| meta의 버전 · 출처 · 증거 파일 누락 | 버전(isaac · kit · torch · NVML 드라이버), 자산 다이제스트(URL이면 omni.client로 읽고 실패하면 빈 값, 지어내지 않음), `root_sensor_offset_b`는 센서 view의 `_offset`(cfg의 +20 m 아님, 환경 일치 · 회전 단위 · drift 0일 때만), 경계 증거 파일 | 진단이 만든 meta + 실제 검사기 = PASS | 항목 하나씩 빼면 `provenance_missing` |
| 충돌 증거가 없음 | USD 메시 대 Warp 메시 수치 대조, 그리고 **PhysX scene query를 캡처 도중 같은 step에 같은 광선으로** 쏨(69개 step), 원시 응답 전부 `physx_queries.npz`로 보존, 환경 x 표면(구멍 · 깊은 바닥 · 단 위 · 평지) 16개 갈래를 결과 전에 코드로 고정 | 갈래마다 계획 20개 이상, 비교 가능이 절반 이상, 오류 0, hit/miss 불일치 0, oracle 불일치 0, 높이차 0.002 m 이하 | 구멍 광선 전부 차폐(ASTRA 반례) · 구멍에서 지면이 잡힘 · 단 위 5 cm 차이 · 질의 오류 · 한 번도 안 본 갈래 · 경계 광선을 비교에 넣음 · 로봇 hit를 지면으로 셈 |

`collision_sha256`은 **질의 응답의 지문**이며 충돌 메시 바이트 해시가 아니다(`collision_sha256_kind`에 명시). 증거의 `scope`는 `sampled_collision_response`이고 검사기가 scope와 `branches_ok`를 요구한다. PhysX가 쿠킹한 메시 전체의 동일성은 주장하지 않는다.

## 3. 시험 결과 (실행 대비)

- 스위트 `run_all_s2_step4a3.py` 복사본 실행, 종료 0, `complete=true`. 정상 시험 파일 16개 전부 종료 0, PASS 줄 203(skip · hold · 미실행 0). 변이: 기존 5/5 · 6/6 · 7/7 · 감시자 4/4 유지, **A3.2 변이 28/28 CAUGHT**(각 변이는 정상 소스의 같은 시험 통과 뒤, 첫 FAIL이 지정 라벨과 같을 때만). 깨끗한 폴더 import 22개, 해시 49줄 일치.
- 변이 설계에서 잡히지 않은 6개를 처음 돌릴 때 보았다. 3개는 시험 장면이 변이를 가리고 있어 시험을 고쳤고(되감김 구간을 분리, 구멍이 없는 장면을 따로 만듦), 3개는 두 경로가 같은 것을 막는 중복 보호(`satisfied` 와 `any_failure`, 되감김 필수와 리셋 후 시각 검사)라 한쪽만 깨면 관측되지 않아 변이에서 뺐다. 중복을 숨긴 것이 아니라 여기에 적는다.
- 3차 원자료에 대한 새 검사기의 기대: 로봇이 떨어진 원자료는 새 검사기에서 `ray_start_height` `unscheduled_termination` 등으로 여전히 HOLD다(기존 데이터를 통과시키려고 oracle을 완화하지 않음).
- 기동 예행(`--rehearse`): prelaunch GO 1.0초, GPU 0 UUID 일치, 경쟁 프로세스 0, 목록 49개 일치.

## 4. 17ac 조건에 대한 상태

| 조건 | 상태 |
|---|---|
| 새 chain · manifest · approval · 출력 · 단회 claim | 기동 도구가 시각으로 만든다 (시도 번호 4, 앞선 세 chain 기록) |
| 사람이 끝까지 보는 참석, 고정 시간(900 s) · 자원 · 시도 수 1, 실패 뒤 가족 정리 | 유지 |
| 팀장의 새 동의 | **아직 없음.** 받은 뒤 원문 그대로 동의 파일에 적는다 |
| tolerance나 제외 범위를 넓히지 않음 | 기존 값 그대로(xy 0.002 · z 0.002 · 경계 0.005). 새 규칙은 모두 더 엄격하거나 새 검사 |
| 무인 · 자동 재시도 · 후속 학습 · B 기동 | 포함하지 않음. 17z 무인 보류 유지 |

## 5. 아직 못 채운 것(미확인 그대로 두는 것)

- **무중력만으로 첫 16행이 2 mm 안에 고정되는지**: 실측해야 안다. 안 되면 `fixed_pose_evidence` HOLD이고 다음 수정은 명시적 root 고정.
- **PhysX `raycast_closest` 반환 키**(`hit` `position` `collision` `rigidBody`)는 설치본 데모 코드와 stub로 확인했지만 실제 지면 collider 경로 문자열은 미확인. 틀리면 갈래가 `occluded`로 몰려 HOLD(오류로 끝나지 않고 응답 샘플이 `physx_raw_samples`에 남는다).
- **질의 속도**: 69 step x 1,496광선. 150초 예산을 넘으면 남은 step을 건너뛰고 증거가 그렇게 말한다(캡처는 계속).
- **native 오류**는 Python try/except로 못 잡을 수 있다(ASTRA 17ac). 기존 hard deadline과 가족 정리가 적용된다.
- 자산 다이제스트는 URL의 주 레이어 한 파일뿐이다(참조 레이어 미포함).

## 6. 추가 (19:45): 독립 가족 정리 관찰자 (ASTRA 17ae 5절 최소 요건)

- 새 도구 `night-tools-20261013/s2_step4a3_launch/s2_family_observer.py`(+ `test_s2_family_observer.py`, 10 PASS, 실제 OS 프로세스와 실제 파일 잠금 사용, GPU 작업 없음). 기동 도구가 live 일 때 **감독기를 띄우기 전에 기준선 `record`, 감독기가 끝난 뒤 `verify`** 를 Job 밖의 별도 프로세스로 호출하고 `run/family_baseline.json` `run/family_observation.json` 에 남긴다.
- verify 가 하는 일: 감독기와 자식의 PID **및 생성 시각**을 상태 파일에서 모아 두고, 종료 뒤 4초 간격으로 두 번 관찰해 (1) 기준선에 없던 Isaac/Kit/우리 도구/실행 폴더가 argv 에 든 프로세스가 있는지, (2) 알려진 attempt PID 가 같은 생성 시각으로 살아 있는지(PID 재사용은 다른 생성 시각이라 사망 증거를 혼동하지 않음), (3) 지정 **물리 UUID** 의 NVML compute 와 `nvidia-smi` 두 시각, (4) 같은 GPU lease(실행별 `ctl/lease`)와 공통 USD 잠금을 비차단으로 잠깐 잡았다 즉시 푸는지, (5) 영수증들의 SHA 와 `family_active_count`. 읽지 못한 프로세스 목록 · NVML 미지원은 **UNKNOWN(HOLD)** 이고 PASS 가 아니다. WDDM 에서 NVML 빈 목록은 「없음」 이 아니라 「보고되지 않음」 일 수 있다고 출력에 적는다. 도구는 프로세스를 죽이지 않고 다른 소유자의 잠금을 건드리지 않으며 한 attempt 에 한 번만 쓴다.
- 한계: 다른 세션의 CPU 시험이 같은 도구 이름으로 프로세스를 띄우면 `os_residual` 로 잡힌다(사람이 읽고 판단). 기동 도구의 live 배선(기준선 → 감독기 → verify)은 실제 4차에서 처음 실행된다(예행은 감독기를 띄우지 않으므로 이 경로를 지나지 않는다). 기준선 단계가 실패하면 NO_GO 로 아무것도 시작하지 않는다.

## 7. 정정 (ASTRA 17ae 로 바로잡은 lead 의 서술)

- 「sol 보고의 271 이 틀렸다」 는 내가 틀렸다. 271 은 정상 단계, 273 은 변이 단계의 정상 선행 2개를 더한 값이다. 두 수 모두 맞고 의미가 다르다.
- 「지도 계산 모듈 6개가 A3 와 바이트 동일」 은 **5/6**: `s2_ppo_17v.py` 는 loss · 그룹별 pre-clip grad · norm 기록과 비유한 grad 거절이 추가돼 다르다.
- 「sol final2 와 lead 결과가 같다」 는 저장소 사본에 `evidence_s2_step7/final2/summary.json` 이 없어서 이 사본으로는 확인되지 않는다(lead 의 `lead_rerun_1908` 과 ASTRA 독립 실행은 따로 유효).
