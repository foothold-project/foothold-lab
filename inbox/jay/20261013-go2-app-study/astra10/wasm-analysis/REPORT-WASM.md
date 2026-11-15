> 분류: 리서치
> 작성: ASTRA10 WASM 독립 조사 세션 · 2026-10-13
> 근거: 지정된 APK 추출 WASM 두 개의 SHA-256·바이너리 section·WAT·Node 실행 · 보관된 공개 Git tree와 wrapper
> 요지: 9,520바이트 모듈은 LZ4 점유 비트맵을 노출 표면 메시로 바꾸고, 7,410바이트 모듈은 6바이트 점 복원과 중복 억제·고정 용량 누적을 수행한다. 고립 점 제거는 확인되지 않았다.
> 상태: 실제 추출 WASM에 합성 입력 28건 실행 확인됨 · 공식 앱 JS 호출·실기 입력·화면 효과는 미확인

# 두 libvoxel WASM의 실제 동작

**확인한 두 모듈은 지도를 안전하게 정제하는 알고리즘의 증거가 아니다.** 9,520바이트 모듈은 인접 voxel 사이 내부 면을 빼고 표면 mesh를 만든다. 고립 voxel 한 개도 그대로 남았다. 7,410바이트 모듈은 양자화 좌표를 복원하고 중복 키의 점을 누적 화면에서 줄인다. 통계적 이상치 제거, 이웃 밀도 판정, 군집 분할을 수행한다는 증거는 두 모듈의 분석한 함수에 없다.

특히 작은 모듈에서 **x/y가 같고 z만 4 m 다른 두 점이 direct 출력에는 모두 남지만 누적 출력에는 하나만 남는 동작**을 재현했다. 이 모듈을 일반적인 올바른 3D voxel downsampler로 소개해서는 안 된다.

## 식별과 조사 경계

| 대상 | 실제 SHA-256 | 확인한 역할 |
|---|---|---|
| [libvoxel-Bqa6xB-f.wasm](../extracted/assets/dist/assets/libvoxel-Bqa6xB-f.wasm), 7,410 bytes | `df28d833bc3045e58e110926dd87c312538a2e5b60a964a4fc5e99ff06d39b9c` | 6바이트 점 복원·중복 억제·ring 누적 |
| [libvoxel-doIu-r8s.wasm](../extracted/assets/dist/assets/libvoxel-doIu-r8s.wasm), 9,520 bytes | `1ba27f065199954dc562b233aa38ea775ac687118cce77b5c71bc14e17e05542` | LZ4 복원·점유 비트맵 순회·노출면 메시 생성 |

기존 [libvoxel-live.wat](../evidence/libvoxel-live.wat)는 7,410바이트 점 누적 모듈의 인자·export와 일치한다. [libvoxel-slam.wat](../evidence/libvoxel-slam.wat)는 9,520바이트 메시 모듈과 일치한다. **기존 WAT 파일명의 live/slam을 기능 판정에 사용하면 역할이 뒤집힌다.** 기존 파일은 이름 변경·수정하지 않았다.

상위 조사에서 지정한 APK 추출 파일을 읽었으며 배포 URL에서 APK를 독립적으로 다시 취득하지 않았다. 공식 앱 JavaScript 호출부는 이 하위 조사에서 읽지 못했다. 따라서 아래는 **지정된 실제 WASM을 직접 호출한 결과**이며 공식 앱에서 해당 기능이 언제 켜지고 어느 토픽을 받는지, 어떤 출력을 화면이나 주행 지도로 쓰는지까지 확인한 결과는 아니다. `SLAM worker`라는 공개 wrapper 이름도 이 WASM 자체가 SLAM 정합·loop closure를 수행함을 뜻하지 않는다.

REA 스킬의 증거 구분 절차를 적용했다. 현재 도구 목록에는 REA MCP가 없고 PATH에 `rea` CLI도 없어, 제공된 WAT·직접 만든 WASM section reader·Node WebAssembly를 사용했다. 아래 산출물은 로컬 shell/Node 증거이며 REA Evidence ID로 가장하지 않는다. 설치·설정 변경은 하지 않았다.

## 바이너리 함수와 메모리

[inventory.json](inventory.json)은 원 파일을 직접 파싱한 section, type, export, 코드 범위를 보관한다. 아래 offset은 **원 WASM 파일의 0 기반 byte offset**이고 종료 위치는 포함하지 않는다.

| 대상·기능 | export / 함수 index | body byte 범위 | 인자 |
|---|---|---|---|
| 7,410B 점 처리 | `e` / func 5 | `0x1A8A <= offset < 0x1CD4` | f32 6개 + i32 9개, i32 반환 |
| 7,410B reset | `d` / func 6 | `0x1CD5 <= offset < 0x1CE7` | 인자 없음 |
| 9,520B 압축 복원·메시 | `e` / func 6 | `0x1AC3 <= offset < 0x2457` | i32 11개, i32 반환 |

7,410B 모듈은 `a.a(i32)->i32` 하나를 import한다. `b`는 memory, `c`는 빈 초기화 함수, `d`는 reset, `e`는 점 처리, `f/g`는 allocator/free, `h`는 table이다. 메모리는 min=max=1,536 pages, **96 MiB**다. 9,520B 모듈은 위 함수와 `a.b(i32,i32,i32)`를 import한다. `c`는 memory, `d`는 초기화, `e`는 메시 처리, `f/g`는 allocator/free, `h`는 table이다. min=max=1,000 pages, **62.5 MiB**다. 두 모듈 모두 start section이 없다. [원 section 확인](inventory.json)

실행은 Node v24.13.0의 WebAssembly 안에서 했다. WASI·파일·네트워크·프로세스 API를 import하지 않았고 `a.a`는 확장 실패 0, `a.b`는 범위를 확인하는 메모리 copy만 제공했다. 원 WASM memory 선언은 고정 크기다. 프로세스는 `--max-old-space-size=128 --wasm-max-mem-pages=1536`으로 띄우고 각 WASM 함수 호출은 VM timeout 2,000 ms 안에서 실행했다. 이는 **WASM memory 한도와 JS old-space 한도**이며 프로세스 전체 RSS가 128 MiB 이하였다는 측정 주장은 아니다. 두 프로세스 모두 자연 종료 code 0이었다.

## 9,520B · LZ4에서 voxel 표면으로

인자 이름은 공개 [voxel-worker.ts](../public-protocol/legion1581__unitree_ui/source/src/workers/voxel-worker.ts)의 wrapper에서 취하고 동작은 원 WASM으로 검증했다.

```text
generate(input, compressedSize, decodeCapacity, decoded, decodedSizeOut,
         positionsOut, uvsOut, indicesOut, faceCountOut, pointCountOut, zNormalized)
```

`e` 앞부분은 LZ4 raw block 형식의 token·literal length·16-bit match offset·match length를 해석한다. 뒤쪽은 복원한 바이트의 비트를 검사한다. WAT의 func 6 시작은 3433행, 비트 순회는 4388행 부근, 이웃 점유 검사는 4420~4470행, 정점·인덱스·UV 출력은 4475행 이후다. 데이터 메모리 1024에는 `80 40 20 10 08 04 02 01` 마스크가 있다. [WAT](../evidence/libvoxel-slam.wat)

실험에서 사용한 점유 배열은 128 × 128 × 30 bits = **61,440 bytes**다. 위치 `(x,y,z)`의 인덱스는 다음과 같다.

```text
bitIndex = x + 128*y + 16384*z
byteIndex = bitIndex >> 3
bitMask = 0x80 >> (bitIndex & 7)
```

고립 `(0,0,0)`과 `(7,0,0)`을 함께 넣으면 첫 바이트가 0x81이다. 실행 결과 x=0과 x=7에 각각 unit voxel이 생겼다. `(127,127,29)` 한 점의 정점 최대 좌표는 `(128,128,30)`이었다. 이것은 이 모듈의 격자 좌표이며 ROS `OccupancyGrid`의 unknown/free 의미는 포함하지 않는다.

LZ4 복원은 두 종류의 답을 아는 입력으로 시험했다.

- **literal-only block:** raw 61,440 bytes를 전부 literal로 넣었다. token `F0`, 길이 확장 바이트, 원 비트맵을 이어 만들었으며 길이 61,682 bytes다. 복원 배열은 원 입력과 byte 단위로 일치했다.
- **실제 back-reference block:** 0 한 바이트를 literal로 시작하고 offset=1의 match로 61,434개를 복원한 뒤 0 다섯 개의 마지막 literal을 붙였다. 총 원 길이는 1+61,434+5=61,440이다. 복원 배열이 전부 0인 것을 byte 비교했다. 생성 코드는 `fixtures.cjs`의 `zeroMatch()`에 남겼다.

따라서 token 모양이 비슷하다는 정적 추측만으로 LZ4라고 부른 것이 아니다. literal와 match 경로 모두 원 WASM에서 실행했다. LZ4 전체 적합성·손상 입력 처리·실제 패킷 캡처 검증까지 수행한 것은 아니다.

| 합성 점유 입력 | pointCount | faceCount | 관찰 |
|---|---:|---:|---|
| 빈 배열 | 0 | 0 | 빈 출력 |
| 고립 `(3,4,5)` 한 개 | 1 | 6 | 고립점 제거 없음 |
| x·y·z 방향 각각 인접 두 개 | 2 | 각 10 | 공유하는 두 내부 면만 제거 |
| 한 칸 떨어진 두 개 | 2 | 12 | 별도 군집 제거 없음 |
| 꽉 찬 2 × 2 × 2 | 8 | 24 | 바깥 면 6 × 2² |
| 꽉 찬 3 × 3 × 3 | 27 | 54 | 내부 voxel도 pointCount에는 남고 표면만 생성 |
| 이후 빈 프레임 | 0 | 0 | 이전 점유를 자동 누적하지 않음 |

`positions`는 정점당 **uint8 3개**, 면당 4정점으로 **12 bytes/face**다. `indices`는 uint32로 면당 6개, 두 삼각형이다. `uvs`는 uint8 8개/face다. 고립 `(3,4,5)`의 첫 면은 다음과 같이 나왔다. 전체 배열은 [fixtures-mesh.json](fixtures-mesh.json)에 있다.

```text
positions = [3,5,5, 3,4,5, 3,5,6, 3,4,6]
indices   = [0,1,2, 2,1,3]
uvs(zNormalized=0)  = [96,0,96,255,90,0,90,255]
uvs(zNormalized=10) = [156,0,156,255,150,0,150,255]
```

zNormalized를 0에서 10으로 바꿔도 정점과 면 개수는 같았고 UV만 달라졌다. 따라서 이 인자는 검증한 범위에서 **기하 필터보다 높이에 따른 표시용 UV**에 영향을 준다. 공개 [voxel-map.ts](../public-protocol/legion1581__unitree_ui/source/src/ui/scene/voxel-map.ts)는 이 byte UV를 normalize하고 색 texture를 사용하며, mesh에 resolution scale과 origin 위치를 적용한다. 이 공개 renderer의 동작이 현재 공식 앱 호출부와 같다는 사실까지 입증하지는 않았다.

단순화한 실제 동작은 다음과 같다.

```text
bits = decode_lz4_block(input)
for each occupied voxel:
    pointCount += 1
    for each of the 6 axis-aligned neighbors:
        if neighbor is outside the fixed volume or not occupied:
            emit 4 corner vertices, 2 triangles and height UV
```

이는 **군집화나 잡음 제거가 아닌 노출면 생성**이다. 점군 화면이 덜 복잡해 보일 가능성은 있지만 센서의 가짜 점을 판별한 것이 아니다.

## 7,410B · 6바이트 점과 누적

인자 배열은 공개 [slam-worker.ts](../public-protocol/legion1581__unitree_ui/source-3d-branch/src/workers/slam-worker.ts)와 일치한다. 공개 주석은 과거 APK 파일명을 적고 있으므로 현재 호출부 확인 근거로 쓰지 않았다.

```text
generate(xmin,xmax,ymin,ymax,zmin,zmax,
         count,input,maxPoints,dict,storedKeys,directOut,accumulatedOut,
         addedCountOut,outputCountOut)
```

각 점은 little-endian **uint16 x, uint16 y, uint16 z**, 합계 6 bytes다. 함수는 아래 복원을 모든 입력에 먼저 적용해 directOut에 float32 XYZ를 쓴다. uint16 단위 1이 0.001로 복원된다는 사실은 **저장 표현의 간격**이며 센서 정확도 1 mm를 뜻하지 않는다.

```text
direct.xyz = [xmin,ymin,zmin] + 0.001 * [rawX,rawY,rawZ]
```

입력 bytes `E8 03 D0 07 B8 0B`는 `[1000,2000,3000]`이다. minima `[10,20,30]`에서 실제 출력은 `[11,22,33]`이었다. xmax/ymax/zmax만 극단적으로 바꾼 두 fixture는 direct 출력과 저장 key가 모두 같았다. WAT의 점 복원 구간은 `libvoxel-live.wat` 3490~3555행이다.

누적 출력은 bit dictionary에 key가 없을 때만 점을 쓴다. 이미 있는 key는 이번 directOut에는 남고 accumulatedOut에는 새로 쓰지 않는다. 최대 점 수를 넘으면 ring slot을 덮고, 그 slot의 이전 key에 해당하는 bit를 지운다. 이는 최근 입력 중 공간 키별 대표점을 유지하는 구조다. 평균값·이웃 수·군집 크기를 계산하는 구조가 아니다.

### z 입력을 사용하지 않는 누적 key

정상적인 유한값·정수 overflow 없는 구간에서 WAT key 식을 풀면 다음과 같다. Bx/By/Bz를 만들 때 실제 WASM은 f32 연산 뒤 unsigned 변환을 하므로 경계점에서는 실수 수식의 floor와 차이가 날 수 있다.

```text
Bx = trunc_u32(f32(f32(xmin + f32(102.4)) * 1000))
By = trunc_u32(f32(f32(ymin + f32(102.4)) * 1000))
Bz = trunc_u32(f32(f32(zmin + f32(51.2)) * 1000)) + 2
ix = floor((rawX + Bx) / 200)
iy = floor((rawY + By) / 200)
iz_from_x = floor((rawX + Bz) / 200)
key = ix + (iy << 10) + (iz_from_x << 20)
```

**rawZ가 아니라 rawX가 세 번째 항에 다시 들어간다.** WAT 3557행과 3563행은 둘 다 `local.get 19`를 사용한다. local 19에는 앞서 읽은 rawX가 들어 있다. 이 구간은 func 5 body `0x1A8A~0x1CD4` 안에 있다. 이는 번역한 C++ 소스의 추측이 아니라 명령 흐름을 읽은 결과다. [WAT](../evidence/libvoxel-live.wat), [함수 offset](inventory.json)

실행으로도 교차 확인했다. minima 모두 0에서 `[1000,2000,0]`, `[1000,2000,4000]`을 순서대로 넣었다.

```text
direct = [1,2,0, 1,2,4]
accumulated = [1,2,0]
addedCount = 1
outputCount = 1
stored key = 274213381
```

따라서 z가 다른 두 점이 이 누적 경로에서 충돌하는 것은 확인됐다. 버그인지, 원 개발자가 의도한 제한인지, 공식 앱이 directOut을 대신 사용하는지, 입력 전처리로 이 경우를 피하는지는 **미확인**이다. 일반적인 0.2 m 3D voxel dedup으로 미화하지 않는다. 여기의 `/200`도 0.05 m ROS 지도 해상도와 관련 있다는 근거가 없다.

### 누적과 reset 실제 결과

| fixture | addedCount / outputCount | 의미 |
|---|---|---|
| 동일 점을 같은 프레임에 두 번 | 1 / 1 | 같은 key 억제 |
| 다음 프레임에 같은 점 | 0 / 1 | dictionary가 프레임 사이 유지됨 |
| x 또는 y를 200 raw 단위 떨어뜨림 | 2 / 2 | 해당 입력에서 다른 key |
| 가까운 세 점 | 1 / 1 | 평균을 내지 않고 먼저 들어온 대표점 유지 |
| 고립점 한 개 | 1 / 1 | 고립점 제거 없음 |
| reset export만 호출 뒤 같은 점 | 0 / 0 | counter만 초기화하고 dict는 남음 |
| reset + dict/keys clear 뒤 같은 점 | 1 / 1 | 공개 wrapper의 clear 작업 필요성 확인 |
| capacity=4에 5개 새 key | 5 / 4 | 첫 slot을 다섯 번째 점으로 덮음 |
| 퇴출된 첫 key 재입력 | 1 / 4 | 옛 key bit가 지워져 다시 들어옴 |

reset func 6은 메모리 주소 **1032와 1028의 i32 counter 두 개만 0**으로 쓴다. dictionary나 출력 버퍼를 지우지 않는다. 공개 wrapper가 dictionary와 storedKeys를 따로 clear하는 이유와 부합한다. frame당 addedCount는 누적 개수와 다르고, capacity보다 클 수 있다.

capacity=4, x=[0,200,400,600,800], y=z=0 입력의 누적 slot 순서는 `[0.8,0.2,0.4,0.6]` m였다. 시간 순으로 재정렬한 배열이 아니다. 렌더러가 점 순서에 의미를 부여하거나 경로로 연결하면 틀린 결과가 된다. 전체 input과 float32 결과는 [fixtures-points.json](fixtures-points.json)에 있다.

## 공개 decoder와의 hash 대조

공개 WASM을 새로 내려받지는 않았다. 기존 조사에 보관된 `metadata.json`과 `branch-3d-tree.json`의 **Git blob SHA-1**을 원 APK member에서 직접 계산한 값과 비교했다. Git blob hash는 평범한 파일 SHA-1이 아니라 `SHA1("blob " + byteLength + NUL + bytes)`다.

| 원 APK member | 직접 계산한 Git blob SHA-1 | 보관된 공개 tree에서 일치하는 경로 |
|---|---|---|
| Bqa6xB-f | `e7694dcd11644d0c3ac3a3deaacb79f61816004a` | legion1581/unitree_ui `public/libslam.wasm` |
| doIu-r8s | `d80d9bf670ed519e644f9e2f3f2e7d8f108b2eca` | unitree_ui `public/libvoxel.wasm`; unitree_webrtc_connect·go2_ros2_sdk·tfoldi·phospho·VectorRobotics의 libvoxel.wasm |

크기와 blob 식별자가 일치한다. **이 조사의 직접 확인 범위는 로컬에 보관된 공개 tree와의 일치**다. 다른 세션이 저장한 tree의 원격 응답 자체를 다시 HTTP 조회하지는 않았다. unitree_go2_ui와 unitree_ui metadata의 중복된 alias는 독립 구현 두 개로 세지 않았다. 각 파일 경로·tree entry·일치 member를 [inventory.json](inventory.json)의 `public_tree_comparison`에 보관했다.

공개 wrapper는 입출력 의미를 읽는 유용한 근거다. 실제 동작 판정은 wrapper의 주석을 신뢰하는 대신 APK member를 직접 실행해 보완했다. 같은 blob이라는 사실은 독립적으로 같은 기법을 개발했다거나 바이너리 재배포 권리가 확인됐다는 뜻은 아니다.

## FOOTHOLD로 옮길 수 있는 부분

이 절은 **설계 제안**이다.

- 3D 표시에는 점유 voxel의 내부 면을 생략하는 원리를 참고할 수 있다. 2³ cube에서 48면 대신 24면이 되는 차이는 이번 fixture로 확인했다. 하지만 unknown/free의 증거를 생성하지 않으므로 Nav2 지도 편집과 분리한다.
- 양자화 좌표 복원과 화면용 point budget을 분리한다. direct point, 표시용 대표점, 원자료를 구분해 보존한다. 위 key 충돌 동작은 가져오지 않는다.
- 고립점 하나가 두 모듈 모두에 남으므로, 이 WASM만 근거로 기획의 잡음 지우개가 대체된다고 주장하지 않는다. 실제 잡음 제거가 필요하면 별도의 센서 근거·검증이 필요하다.
- byte voxel 좌표는 해상도·origin을 곱하기 전의 격자 좌표다. ROS map 좌표로 사용할 때 프레임·시각·단위·원점을 명시적으로 변환한다.
- 이 실험은 실제 센서 데이터나 실기 로봇을 사용하지 않았다. 공식 앱의 토픽 연결·색상 표·누적 선택·상위 전처리·주행 맵 사용 여부는 여전히 미확인이다.

## 재현 산출물

| 파일 | 내용 |
|---|---|
| [inspect_wasm.py](inspect_wasm.py) | 원 binary section·hash·공개 tree 비교. 대상 파일 읽기 전용 |
| [inventory.json](inventory.json) | 두 바이너리 export/type/memory/body offset, 공개 tree 대조 |
| [fixtures.cjs](fixtures.cjs) | 네트워크 없는 Node harness, 알려진 합성 입력 생성·assertions |
| [fixtures-mesh.json](fixtures-mesh.json) | 13건 입력 점 목록·압축 입력 hash·출력 정점/UV/index·count |
| [fixtures-points.json](fixtures-points.json) | 15건 uint16 입력·bounds·direct/누적 출력·key·counter |

저장소 루트에서 다음 세 명령으로 재현한다. WASM은 수정하지 않는다. Node harness는 자신의 폴더에 결과 JSON만 쓴다.

```powershell
python inbox/jay/20261013-go2-app-study/astra10/wasm-analysis/inspect_wasm.py
node --max-old-space-size=128 --wasm-max-mem-pages=1536 inbox/jay/20261013-go2-app-study/astra10/wasm-analysis/fixtures.cjs points
node --max-old-space-size=128 --wasm-max-mem-pages=1536 inbox/jay/20261013-go2-app-study/astra10/wasm-analysis/fixtures.cjs mesh
```

실행 결과는 28건 모두 assertion 통과다. 이는 열거한 합성 입력에 대한 성공이며 파일 전체의 보안 감사·실시간 성능·모든 입력 적합성·공식 앱 화면 검증의 완료를 뜻하지 않는다.
