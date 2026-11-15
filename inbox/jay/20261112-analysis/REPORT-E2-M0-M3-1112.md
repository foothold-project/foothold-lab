# E2 고정 메시 M0~M3 영수증

> 분류: A/평가 · 일반화 벤치마크 · 지표
> 작성: 오흥재(analyst-lx) · 2026-11-12 01:52
> 근거: CG v0.17 §E.3:400 · lead 11/12 M1 해석 채택 · 실제 E2 flags v2 NPZ
> 요지: M0·M1 CPU 측정 완료, M2·M3은 lead Kit 측정 뒤에만 완결
> 상태: 확인됨(CPU) · Kit 미측정 · E2 입구 HOLD

**현재 전체 HOLD**. `checks.M0/M1.status=PASS`, `checks.M2/M3.status=HOLD`, `blockers=[M2_M3_missing]`. 아래 SHA는 미완료 CPU 영수증이므로 E2 승인 칸에 넣지 않는다.

## 확인된 원자료

| 항목 | 값 · 근거 등급 |
|---|---|
| 메시 폴더 | `/mnt/win-d/mai/data/foothold/s2_lab/ex42_mesh_1111/seed42_E0_c333_flags_E2_1111_v2` |
| geometry SHA | `88197b3adfdde327edc633c025c6ad9aa690ea59aa7df5d51d548f7f56c12a95` · 실측 |
| NPZ 파일 SHA | `59b0bf3e3023f40da828b86eebff4513222e13452c70fc49b8951d7e8d42d771` · 실측 |
| terrain_manifest SHA | `7e9dab9420c3c6694df9e2e5d5d9155ff4a5448d1ac7a9936a96c07d2a7a6740` · 실측 |
| CPU 영수증 | `/home/jay/mai/tmp/analyst-lx/e2-m0m3-1112/m0-m3-pending.json` |
| CPU 영수증 SHA | `69d0ab098439277eb80bb5a19cb06ebb5cb4be06c103fe651bde1002b32bc0b6` · 실측 |
| M0 | 46 선언 행, 실제 39종, 76열, L0/L5/L9 228행 · 실측 |
| 최초 프로세스 읽기 | 0.242376 s, 현재 RSS 76.602 → 142.469 MiB · 실측 |
| 반복 읽기 | 0.234997 s, 현재 RSS 77.176 → 142.059 MiB · 실측 |
| 원래 생성 | 9.176870385 s · 기존 실측 영수증 상속 |
| 깃발 추가 | 5.443580511 s · 기존 CPU 실측 영수증 |

M0는 실제 정점·면·원점·열 순서를 E0와 바이트로 대조하고 깃발이 추가된 것을 확인했다. 각 열의 0/5/9 레벨에서 삼각형 수·실제 XYZ 범위·시작점·깃발을 읽었다. 원래 높이장 배열은 NPZ에 저장되지 않았으므로 삼각 메시에서 읽은 높이 범위와 높이장 원본을 혼동하지 않는다. continuous 7행은 A의 같은 지형을 가리키는 별칭이다.

M1의 cold-first는 **이 프로세스 첫 읽기**다. 운영체제 파일 캐시를 비우지 않았으므로 디스크 cold-cache 실측이라고 부르지 않는다. 현재 RSS와 프로세스 최대 RSS를 모두 남겼다. E2 실제 경로는 고정 NPZ 읽기이며 원형 생성기 `use_cache=True/False`는 사용하지 않는다. 이 범위는 lead가 CG:400 우선으로 채택했다. 옛 DESIGN §8:321의 생성기 캐시 비교를 완료했다고 적지 않는다.

## Kit 측정 명령과 기대값

lead가 학습 종료 뒤 빈 GPU 슬롯에서만 실행한다. 아래는 실행 준비 명령이며 **아직 실행하지 않았다**. 먼저 이 PR HEAD를 고정한 사본을 준비하고 그 루트에서 실행한다. 현 작성 사본은 `/home/jay/mai/wt/foothold-lab/analyst-lx-terrain-d`다. `cuda:1`은 이번 전달 명령의 장치이며 lead 배정이 다르면 `cuda:0`으로 명시한다.

```bash
env PYTHONDONTWRITEBYTECODE=1 FOOTHOLD_MACHINE_PROFILE=machines/AI-WS01-linux.yaml /home/jay/miniforge3/envs/isaac311/bin/python -m foothold_s2.scripts.ex42_m0_m3_probe --mesh-dir /mnt/win-d/mai/data/foothold/s2_lab/ex42_mesh_1111/seed42_E0_c333_flags_E2_1111_v2 --device cuda:1 --expected-npz-sha256 59b0bf3e3023f40da828b86eebff4513222e13452c70fc49b8951d7e8d42d771 --out /home/jay/mai/tmp/analyst-lx/e2-m0m3-1112/kit-probe.json
```

- 128 → 512 → 3072 순차로 지형 원점과 광선 버퍼를 늘린다. 크기를 올리기 전과 광선마다 장치 여유를 확인한다. 2 GiB 미만이면 더 늘리지 않고 미완료 종료한다. 프로세스 전체 제한 600초. 둘은 CG 가정·승인값이다.
- 접촉용 USD/PhysX 메시를 올리고 `sim.reset()`한 뒤 Warp 메시를 올린다. allocated/reserved/최대/관측 최소 free GiB를 남긴다. **로봇 관절체·rollout·PPO 메모리는 제외**하므로 학습 전체가 3072에서 들어간다는 근거는 아니다.
- M3는 승인된 대리 하향 격자: 높이 스캔 187, depth 크기 3600, 합계 3787 광선/env. 각 크기·패턴마다 첫 호출 + warmup 20 + 100회, CUDA event·동기화 벽시계·평균·p50·p95·최대.
- reset 포함은 광선 시작점 버퍼를 복원하는 **proxy reset**이다. 로봇 리셋·센서 정확도·전방 카메라 광학 경로가 아니다. 실제 센서 512 GT·발 100은 이 승인된 3787 proxy 묶음에 들어 있지 않는다.
- 기대값: rc 0, status `measured`, 세 크기·각 여섯 패턴/reset 조합, 2 GiB 이상, 600초 이내. 실패는 rc 2·불완전 영수증, 시간 초과는 rc 124·`.timeout.json`. 이전 파일을 덮지 않는다.

Kit rc 0 뒤 CPU 조립:

```bash
env CUDA_VISIBLE_DEVICES='' PYTHONDONTWRITEBYTECODE=1 FOOTHOLD_MACHINE_PROFILE=machines/AI-WS01-linux.yaml /home/jay/miniforge3/envs/isaac311/bin/python -m foothold_s2.tools.ex42_m0_m3 --mesh-dir /mnt/win-d/mai/data/foothold/s2_lab/ex42_mesh_1111/seed42_E0_c333_flags_E2_1111_v2 --table /home/jay/mai/tmp/analyst-lx/e2-m0m3-1112/plan-b30baea309f8caaed84b5019a197bc4f19333a0eec6fe8702a7ac081d508befe.yaml --probe /home/jay/mai/tmp/analyst-lx/e2-m0m3-1112/kit-probe.json --out /home/jay/mai/tmp/analyst-lx/e2-m0m3-1112/m0-m3-final.json
```

기대값은 전체 PASS·blockers=[]·네 checks PASS. 최종 파일의 SHA를 그때 계산해 verifier에게 준다. 미측정·다른 NPZ·크기 누락·낡은 증거는 HOLD 또는 오류다. 이 도구는 승인 파일·학습 설정·원 메시를 수정하지 않는다.

## verifier 소비 계약

`foothold_s2.tools.ex42_m0_m3.verify_receipt(path, expected_sha256, mesh_dir=...)`가 JSON·참조 파일 SHA, 현재 메시 identity, CPU M0 재계산, 원 생성시간, 원시 100회 재집계, 순차 크기·여유·시간 제한을 검사한다. HOLD는 ValueError로 거절한다. 구조:

```text
format: foothold-ex42-m0-m3/1
stage_id: E2
status: PASS | HOLD
mesh.geometry_sha256
mesh.files[terrain_mesh.npz | mesh_manifest.json | terrain_manifest.json]: path, sha256
checks[M0 | M1 | M2 | M3]: status=PASS|HOLD, evidence=[path,sha256]
cpu_ref: 실제 .cpu.json
probe_ref: Kit 원시 JSON 또는 null
```

원래 메시 SHA만 같고 flags·원점이 다른 파일을 받지 않도록 파일 SHA도 함께 대조한다. raw JSON의 이름만 등록해서 PASS를 만들지 않는다.

## 검증과 한계

CPU 시험 **10 passed in 9.09s**(실측). 시험 파일은 `foothold_s2/tests/test_ex42_m0_m3_cpu.py`. 알려진 시간열 [1,2,3], NaN·누락 크기·낮은 여유·통계 변조·메시 SHA 오류·미측정 PASS 변조·Kit 전 잘못된 NPZ 거절·실제 E2 원자료·고정 plan 상대 YAML 동반 복사를 시험한다. 최종 시험 원출력은 `/home/jay/mai/tmp/analyst-lx/e2-m0m3-1112/cpu-test.log`.

Kit 코드의 실제 실행 성공은 미확인이다. 설치된 Isaac Lab `terrain_importer.py:72~99,291~305`의 constructor/원점 API와 기존 `ex42_mesh_build.py`의 Warp API를 대조했다. 프로브의 VRAM 여유는 측정 지점 값이며 드라이버 전역 순간 최저를 연속 계측한 값은 아니다. GPU 학습을 켜거나 운영 프로세스를 바꾸지 않았다.
