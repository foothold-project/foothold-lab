# D 묶음 시작 지지면 CPU 사전 점검

> 분류: 실험
> 작성: 오흥재 · 2026-11-11
> 근거: lead 02:09 의뢰 · hipan_posture 6a9719bf · ABCDE v2 합성 메시와 장착 JSON
> 요지: 현재 D 3종의 시작 지지면 누락은 CPU에서 발견되지 않았으며 전체 Kit 실패의 원인은 아직 귀속할 수 없다
> 상태: 확인됨(CPU 기하) · 전 열 Kit 결과 대기
> 판: v1.0

작성 보조: analyst-lx. 생성기·reset 범위·학습 설정은 고치지 않았다. GPU·Kit 실행 없음.

## 결과

`확인됨`: **현재 8×8 m 판에서 지지면이 없는 D 종류는 0개다.** high_ledge · wall · crawl 모두 앞쪽 `(1,4,0)`에서 시작한다. 기본 XY ±0.5 m와 yaw ±3.14 rad를 유지해도 아래 범위는 지지 바닥 안이다. RESET_RANGES 추가가 필요하다는 근거는 현재 없다.

| 종류 | 저장 행 / 물리 레벨 수 | 기본 자세 지지 높이 | XY·yaw 전체 범위 지지 높이 | 그 범위 끝에서 장애물 시작까지 |
|---|---|---|---|---|
| high_ledge | 10 / 3 | 0.000000~0.000000 m | 0.000000~0.000000 m | 2.069884 m |
| wall | 10 / 1 | 0.000000~0.000000 m | 0.000000~0.000000 m | 2.019884 m |
| crawl | 10 / 10 | 0.000000~0.000000 m | 0.000000~0.000000 m | 0.069884 m |

실제 합성 메시에서 **30 저장 칸 × 2 조건 × 121점 = 7,260점**, 미검출 0 · 지지 높이 모두 0 m. high_ledge의 상한 반복 행과 wall 반복 행은 새 난도나 독립 표본으로 세지 않는다.

## 전체 범위를 확인한 방법

- 기준 발 주변 직사각형은 0.70×0.50 m다. 중심에서 꼭짓점까지 거리는 `sqrt(0.35²+0.25²)`다.
- 어떤 yaw에서도 이 직사각형은 반지름 **0.430116263 m** 원 안에 있다. 여기에 XY 표본 범위 0.5 m를 더하면 각 축 반폭 **0.930116263 m**인 사각형이 모든 경우를 덮는다.
- 이 사각형은 지역 좌표 x=[0.069884,1.930116], y=[3.069884,4.930116]이다. 코드의 전체 바닥 x/y=[0,8] 안이며, 턱 시작 x=4 · 벽 시작 x=3.95 · 천장 시작 x=2와 겹치지 않는다. 무작위 몇 개만 뽑은 판단이 아니라 바닥·장애물 경계를 이용한 연속 범위 계산이다.
- 추가로 원자료 NPZ의 실제 삼각형을 골라 두 범위에서 수직선 교차를 독립 계산했다. 알려진 삼각형의 높이 0.8 m, 메시 밖 미검출, 바닥 밖/천장과 겹치는 범위의 실패를 먼저 확인했다.
- 이 반폭은 로봇 동작 중 모든 관절 자세의 발 궤적을 뜻하지 않는다. 현재 초기 자세와 지정한 발 주변 크기에 관한 점검이다. 초기 관절·roll/pitch·몸 크기·carrier 크기를 바꾸면 다시 재야 한다.

근거 코드: [hipan_posture.py](https://github.com/foothold-project/foothold-lab/blob/6a9719bfb7bf18f5e794f614112620680a1946d3/foothold_s2/terrains/hipan_posture.py#L76) :76~100의 바닥·장애물·origin, `:194~214`의 저장 행 대응. 재현 도구: `tools/audit_hipan_spawn_cpu.py`. [숫자 원자료](evidence/hipan-d-spawn-cpu.json).

## 전체 장착 실패와 구별할 것

- mount v2의 전체 판정은 여전히 `failed_criteria`다. 이 CPU 점검으로 그 판정을 바꾸지 않는다.
- 같은 JSON에서 C 전용 칸은 28줄 중 28줄이 통과한 것을 직접 확인했다. 이는 이전 C 수정의 장착 확인이며 D 동적 접촉의 증거는 아니다.
- 현재 일반 reset의 최악 발 높이는 env·열·종별 식별자가 없으므로 D 또는 다른 묶음으로 귀속할 수 없다. `worst_root_above_mesh`의 A random_rough를 최악 발 높이의 주인으로 해석하지 않는다.
- 64 env에 76열 전체가 들어가지 않았다. v2의 일반 reset 사용 열 목록에는 D 69열(high_ledge)이 없고 70·71열만 있다. 따라서 시작점 높이 0 m 한 점 검사와 일반 reset 집계로 D 전 종류의 동적 장착 PASS를 주장할 수 없다.
- crawl의 지지 범위 끝과 천장 시작 사이 최솟값은 약 7 cm다. 현재 범위는 겹치지 않지만 여유가 크다고 부르지 않는다. 다음 전 열 검사에서 발 네 개·몸 자세·clearance를 함께 확인한다.

## 입력 핀과 재현

| 입력 | 식별자 |
|---|---|
| mount/manifest 내용 해시 | `eafbada6c431fdc37b2a0e20094a404f0caad96d58cb2bcaca761629acf0b01d` |
| NPZ 파일 SHA256 | `f1697a4bc0ad2e8f352d003a9bd41f9077bea808a605f8e1f911062b874d09c2` |
| 장착 JSON 파일 SHA256 | `15a39b5f2c3b794006317cb712426e1faff0fd57165228820f84076a114f2064` |
| 생성기 파일 SHA256 | `37e6550d53931df9de01b32b1d12e08c136af3b60601bb3c68eea211ebe55509` |

```bash
CUDA_VISIBLE_DEVICES='' PYTHONDONTWRITEBYTECODE=1 python tools/audit_hipan_spawn_cpu.py \
  --mesh /mnt/win-d/mai/data/foothold/s2_lab/ex42_mesh_1111/seed42_ABCDE_v2/terrain_mesh.npz \
  --manifest /mnt/win-d/mai/data/foothold/s2_lab/ex42_mesh_1111/seed42_ABCDE_v2/mesh_manifest.json \
  --mount /mnt/win-d/mai/data/foothold/s2_lab/ex42_mesh_1111/mount_check_ABCDE_v2_cuda0.json \
  --output /home/jay/mai/tmp/analyst-lx/terrain-d-spawn-1111/recheck.json
```

| 판 | 내용 |
|---|---|
| v1.0 | D 기본·전체 reset 범위 지지면 점검, 실제 메시 7,260점 확인, 전체 실패 귀속은 미확인 |
