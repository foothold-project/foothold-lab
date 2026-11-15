> 분류: 리서치
> 작성: ASTRA10 WASM 독립 조사 세션 · 2026-10-13
> 근거: runtime-web 실제 배포 JS와 보관 manifest의 SHA-256 대조 · 변경 없는 worker와 추출 WASM의 Node 합성 입력 실행 · main 지도 렌더러 원문
> 요지: 누적 점과 direct 점은 실제 지도 렌더러에 함께 전달되며, clear의 배열 끝 인자 오류로 일부 중복 키가 남는 동작을 재현했다.
> 상태: worker 실행 8건 확인됨 · main 호출과 렌더 버퍼 연결은 정적 확인됨 · 실기 센서 입력과 실제 화면 효과는 미확인

# 실제 배포 worker와 WASM의 연결

**앞선 WASM 분석에서 남겨 둔 공식 앱 호출부 미확인을 일부 해소했다.** 배포된 `three.worker-VAdOurOh.js`는 7,410 bytes WASM을 실제로 호출하고, `main-LIOZh9o1.js`는 누적 `output`과 현재 입력의 `directOutput`을 각각 다른 점 렌더 버퍼에 넣는다. z만 다른 두 점 중 하나가 누적 출력에서 사라지는 현상은 이 worker의 `newMap` 메시지 경로에서도 재현됐다.

또한 실제 `clear`는 WASM 카운터를 초기화하지만 JS의 `TypedArray.fill` 끝 인자가 잘못되어 dictionary 일부와 index 배열이 지워지지 않는다. 합성점 `[51, 0, 0]`을 넣고 `clear`한 뒤 다시 넣으면 direct에는 한 점, 누적에는 0점이 나온다. 이는 확인한 배포 코드의 특정 입력에 대한 결과다. 실제 로봇이 이 좌표와 bounds를 보내는 빈도, 사용자 화면에서의 발생 빈도는 미확인이다.

이 문서는 [REPORT-WASM.md](REPORT-WASM.md)의 후속 증거다. 그 문서의 조사 당시 호출부 미확인 표기를 소급해서 바꾸지 않았다. 외부 문서나 공개 wrapper를 공식 앱 실행의 대용으로 삼지 않고, 새로 보관된 배포 JS를 직접 읽고 실행했다.

## 원문과 재현 범위

| 파일 | bytes | SHA-256 |
|---|---:|---|
| [three.worker-VAdOurOh.js](../runtime-web/assets/three.worker-VAdOurOh.js) | 6,083 | `fb87c81e68b0958cfce39065cbf7764d298eb875769cfd65d4ea16a022967143` |
| [three.worker-BhnsyeGz.js](../runtime-web/assets/three.worker-BhnsyeGz.js) | 6,568 | `2a2a87c04b03c51a02be39da4d282d585054cead6881e452a0cba3c9bcb23e96` |
| [slam.worker-B9-NnJ09.js](../runtime-web/assets/slam.worker-B9-NnJ09.js) | 4,274 | `7be29eece06e43d4edbab276911f02e50c1134aa37d07dce4ec9731ead9066ef` |
| [main-LIOZh9o1.js](../runtime-web/assets/main-LIOZh9o1.js) | 11,785,671 | `cebfc3e7e2d7838cf8adf650d0a32edbf7fbd32df8ede486d7521f96afb6ab15` |

네 파일의 크기와 hash는 [runtime-web-manifest.json](../evidence/runtime-web-manifest.json)과 직접 대조했다. manifest가 기록한 획득 출처는 에뮬레이터의 localhost HTTP 서버다. 이 하위 조사에서는 서버 획득 과정을 다시 수행하지 않고, 보관본의 동일성과 알고리즘을 확인했다. manifest의 `apk_same: false`는 암호화된 APK asset과 평문 JS가 같은 바이트가 아니라는 기록이다.

[fixtures-wrappers.cjs](fixtures-wrappers.cjs)는 worker 원문을 수정 없이 Node `vm`에 넣는다. `fetch`는 지정한 로컬 WASM 하나의 바이트만 반환하며 다른 URL은 assertion으로 거부한다. 실제 `WebAssembly.instantiate`와 실제 wrapper의 imports를 사용하고 export의 allocator, generate, reset 호출을 관찰한다. 기록용 함수가 인자와 반환을 그대로 전달하며 메모리를 바꾸지 않는다. `instantiateStreaming`을 제공하지 않아 원문에 있는 ArrayBuffer 로딩 경로를 사용한다.

Node v24.13.0, JS heap 128 MiB 제한, WASM 최대 1,536 pages 제한, 각 VM 실행 2초 제한으로 실행했다. 실제 WASM 메모리는 점 worker 100,663,296 bytes, mesh worker 65,536,000 bytes였다. 모든 프로세스가 정상 종료했다. 브라우저, main 전체, 실제 로봇, 통신 서버는 실행하지 않았다. 이 fixture는 worker 메시지와 결과 버퍼까지의 재현이며 최종 화면의 재현은 아니다.

## mapping 점 경로: 실제 누적 출력이 사용된다

정적으로 확인한 경로는 다음과 같다. 줄 번호는 위 hash의 main 보관본 기준이다.

| 단계 | 직접 확인한 코드 |
|---|---|
| 입력 | main 18988~18990: `LIDAR_MAPPING_CLOUD_POINT`를 받으면 `type: "newMap", data: e.data`로 worker에 전달 |
| worker 선택 | main 18651: `/assets/three.worker-VAdOurOh.js`를 `window.lidarMappingWorker`에 할당 |
| WASM 선택 | worker 문자 offset 1765: `/assets/libvoxel-Bqa6xB-f.wasm` |
| 처리 | worker offset 4679: bounds 여섯 값, 입력 점 개수, capacity와 각 buffer pointer로 `_generate` 호출 |
| 결과 | worker offset 5464: `newMap` 결과에 `output`, `directOutput`, 두 count와 `addedCount` 모두 포함 |
| main 수신 | main 18646~18648: `newMap`이고 페이지 상태가 `new`이면 `w.updatePointCloud(O.output, O.directOutput)` |
| 렌더 버퍼 | main 17954~17955: `output.buffer`는 `filteredBufferGeometry`, `directOutput.buffer`는 `laserBufferGeometry`의 position attribute |
| scene | main 17935~17944: 두 Points를 모두 scene에 추가. 누적 재질 size `0.05`, direct 재질 size `0.1` |

따라서 누적 배열이 계산만 되고 버려진다는 해석은 맞지 않는다. 다만 이 정적 연결만으로 어떤 실제 시점의 화면에서 어느 점이 보였는지는 확정할 수 없다. direct 점도 함께 그리므로 누적에서 사라진 점이 화면 전체에서 반드시 사라진다고 표현해서도 안 된다.

worker의 핵심 의미를 변수명만 풀어 쓰면 다음과 같다.

```js
const capacity = 1_000_000;
const directCount = packedBytes.length / 6;
HEAPU8.set(packedBytes, inputPtr);
generate(xmin, xmax, ymin, ymax, zmin, zmax,
         directCount, inputPtr, capacity,
         dictionaryPtr, storedKeyPtr, directPtr, accumulatedPtr,
         addedCountPtr, outputCountPtr);
const outputCount = readI32(outputCountPtr);
const addedCount = readI32(addedCountPtr);
return {
  directCount,
  directOutput: copyFloat32(directPtr, directCount * 3),
  outputCount,
  output: copyFloat32(accumulatedPtr, outputCount * 3),
  addedCount
};
```

`directOutput`은 해당 입력 메시지를 복원한 점들이고, `output`은 이전 호출의 상태를 보존하는 ring 누적 결과다. 반환 시 두 배열 모두 heap에서 복사한다. `output` 길이는 `addedCount`가 아니라 전체 `outputCount`에 맞추므로 이번 호출에 추가한 점만 반환하는 방식이 아니다. `lastCount`에는 count를 저장하지만 읽어서 분기하거나 샘플링하는 코드는 이 worker에서 발견되지 않았다.

WASM 내부의 좌표 복원은 앞선 15건 점 fixture에서 확인한 `minimum + uint16 * 0.001`이다. 여섯 bounds를 wrapper가 모두 전달해도 WASM의 최대값 세 개가 clipping에 쓰이는 것은 아니다. 복원과 key 계산의 상세 함수·offset 및 max bounds 변경 시험은 [REPORT-WASM.md](REPORT-WASM.md)와 [fixtures-points.json](fixtures-points.json)에 있다. 현재 wrapper는 별도 높이 범위 필터나 bounds 검사로 이를 보완하지 않는다.

새 실제 worker fixture 결과:

| 입력 | direct 결과 | 누적 결과 |
|---|---|---|
| packed uint16 두 점 `[1000,2000,0]`, `[1000,2000,4000]`, minima 모두 0 | count 2, `[1,2,0, 1,2,4]` | count 1, `[1,2,0]`, added 1 |

이는 x/y가 같고 z만 다른 점을 같은 key로 취급하는 앞선 WASM 결과와 일치한다. 이 코드에 이름만 보고 정상적인 3D voxel downsampling, 군집화, 밀도 기반 잡음 제거라는 설명을 붙일 수 없다. 여기서 확인한 것은 복원, 중복 key 억제, 고정 용량 누적이다.

### 개수와 해상도의 구분

`capacity = 1_000_000`은 누적 최대 점 수다. `size: 0.05`는 main의 Points material 인자다. `newMap` worker의 WASM 호출에는 resolution 인자가 없다. 따라서 이 코드가 0.05 m 점유 지도나 0.05 m voxel grid를 만든다는 주장은 근거가 없다. 앞선 WASM key 수식에는 200 단위 나눗셈이 있으나, rawZ 대신 rawX를 다시 사용하는 동작 때문에 이를 정상적인 0.2 m 3축 grid라고 소개하는 것도 부정확하다.

wrapper는 입력 점을 무작위로 고르거나 일정 간격으로 생략하지 않는다. 점 감소는 WASM의 key 억제와 누적 capacity에서 발생한다. 입력 길이의 `/6`에는 정수·배수 검사도 없다. allocator 요청은 packed input 200,000 bytes, direct output 300,000 bytes이므로 direct XYZ float32 저장 용량은 25,000점이다. 이는 **정적 배열 용량**이며, 실기 메시지가 이를 넘는지 또는 실제로 메모리 손상이 발생하는지는 시험하지 않았다.

## clear: 문자열은 맞고 배열 끝값이 틀린다

main 18727~18729의 `cleanPage`는 `postMessage("clear")`를 보낸다. 실제 worker는 `if(h.data === "clear") P.clear()`로 받는다. 따라서 문자열과 객체 사이의 메시지 형식 불일치는 없다. 새 fixture도 같은 문자열을 보냈다.

문제는 worker offset 4543의 다음 코드다.

```js
HEAPU8.fill(0, this._outputDict, 67108864);
HEAPU8.fill(0, this._outputIndices, 1_000_000 * 4);
this._module._reset();
```

`fill(value, start, end)`의 end는 배열 시작부터의 절대 index다. 할당 시작 pointer에 길이를 더해야 해당 버퍼 전체가 지워진다. 실제 wrapper allocator를 거친 이번 실행의 위치와 결과는 다음과 같다.

| 버퍼 | 시작 pointer | 필요한 끝 index | 코드가 전달한 끝 index | 직접 확인한 결과 |
|---|---:|---:|---:|---|
| dictionary | 567,128 | 67,675,992 | 67,108,864 | 끝 567,128 bytes가 clear 범위 밖 |
| stored keys | 67,676,000 | 71,676,000 | 4,000,000 | end가 start보다 앞이어서 아무것도 지우지 않음 |

WASM `_reset`은 메모리 1028과 1032의 두 카운터만 0으로 만든다. dictionary 자체를 지우지 않는다는 앞선 WAT·실행 결과를 이번 실제 wrapper 메모리에서도 확인했다.

| 시험 | clear 전 | clear 후 | 같은 점 재입력 |
|---|---|---|---|
| 보통 key `274213381` | dict byte `34843800`의 bit 32 | bit 0, 카운터 `[0,0]`, stored key는 남음 | 이 경우 dictionary bit는 정상적으로 지워짐 |
| 큰 key `536347391` | dict byte `67610551`의 bit 128 | bit 128 유지, 카운터 `[0,0]`, stored key 유지 | directCount 1, outputCount 0, addedCount 0 |

두 번째 시험의 packed 입력은 `[51000,0,0]`, bounds는 `[0,64,0,64,0,64]`이며 복원 좌표는 `[51,0,0]`이다. clear 이후 direct에는 이 점이 남고 누적 배열은 비었다. 모든 좌표에서 clear가 실패한다고 일반화하지 않는다. 이 재현은 지워지지 않는 dictionary tail에 key가 들어가는 경우를 특정한다.

의도가 버퍼 전체 초기화라면 끝 인자는 각각 `dictPtr + 67108864`, `keysPtr + 1_000_000 * 4`여야 한다. 이는 원문 동작에 대한 진단이다. 배포 파일은 수정하지 않았다. worker 자체를 새로 만드는 경우와 실제 지도 세션 전환의 전체 수명 주기는 이 fixture 범위 밖이다.

## 전방 voxel 경로와 정적 지도 경로는 같은 worker가 아니다

`three.worker-BhnsyeGz.js`는 9,520 bytes [libvoxel-doIu-r8s.wasm](../extracted/assets/dist/assets/libvoxel-doIu-r8s.wasm)을 로드한다. 11개 정수 인자로 압축 바이트, 해제 buffer, geometry 출력 pointer, count pointer, z 기준값을 넘긴다. 반환된 `face_count`에 맞춰 positions는 `faces * 12` bytes, UV는 `faces * 8` bytes, indices는 `faces * 24` bytes를 복사한다. 이 동작은 앞선 LZ4 복원과 노출면 생성 fixture의 모듈과 연결된다.

| 구분 | 입력과 main 연결 | worker 결과 |
|---|---|---|
| operation의 실시간 voxel | main 10907에서 BhnsyeGz worker 생성, 10913에서 `ULIDAR_ARRAY` 전달 | mesh geometry, resolution, origin |
| mapping 중 점 누적 | main 18988~18990에서 `LIDAR_MAPPING_CLOUD_POINT`를 VAdOurOh `newMap`에 전달 | 누적 점과 direct 점 |
| 저장된 PCD 표시 | main 17967~17973의 `loadPCD`가 loader 결과를 `pointsLoaded`로 scene에 추가 | 이 함수에는 위 두 worker를 거치는 코드 없음 |

front mesh를 갱신하는 main 10086~10092는 worker의 geometry를 읽고 `mesh.scale.set(resolution, resolution, resolution)` 및 `mesh.position.set(origin[0], origin[1], origin[2])`를 적용한다. 좌표 표시의 의미는 `world = origin + resolution * voxelVertex`다. worker 내부 geometry는 정수 voxel 꼭짓점이고, worker가 그 값을 미터 좌표로 곱해 반환하는 방식이 아니다.

worker offset 6416에서는 `Number(message.resolution) || 0.1`을 사용한다. width는 읽어 객체에 넣지만 이후 generate 호출에 전달하지 않는다. offset 6243에서는 `floor(origin[2] / resolution)`을 WASM의 마지막 인자로 전달한다. 앞선 fixture에서 이 인자는 UV 색상 계산에 영향을 주며 geometry를 재샘플링하는 인자가 아니었다.

새 worker fixture는 한 voxel만 든 252 bytes LZ4 입력으로 다음을 확인했다.

| message 입력 | 실제 결과 |
|---|---|
| resolution `".05"`, origin `[1,2,0.17]`, width 128 | 반환 resolution 0.05, 마지막 WASM 인자 3, 1 voxel · 6 faces |
| resolution 0, 같은 origin, width 999 | 반환 resolution 0.1, 마지막 WASM 인자 1, 같은 geometry의 1 voxel · 6 faces |

실제 센서 resolution이 무엇인지는 이 합성 시험으로 확정할 수 없다. 확인한 것은 제공된 resolution의 변환과 기본값, geometry scale 연결이다. 또한 폭을 999로 바꿔도 동일 bit 입력의 geometry는 같았다. 임의 width의 점유 volume을 지원한다고 보아서는 안 된다. 이 WASM의 실제 순회 grid는 앞선 분석에서 확인한 128 × 128 × 30이다.

worker 자체에는 점별 무작위 sampling이나 잡음 분류가 없다. main은 10913에서 `q == 0`일 때만 새 `ULIDAR_ARRAY`를 보내며 10864에서 전송 후 q를 1로 설정하고 10894에서 응답 시 0으로 되돌린다. 화면 상태 `show == 0`에서는 `qE(callback, 150)`으로 감싼 전송 함수를 쓰지만, 이 문서에서는 그 helper 구현까지 추적하지 않았으므로 150의 정확한 스케줄링 의미를 확정하지 않는다. 메시지 전송 제어와 공간 해상도는 별개다.

이 코드에서 노출면을 만들 때 이웃 voxel 사이의 내부 면을 생략하는 것은 geometry 최적화다. 고립 voxel을 제거하는 증거가 아니다. front geometry 또는 누적 display buffer를 수정하면 저장된 PGM, 항법 costmap, robot 측 SLAM 상태도 바뀐다는 연결은 확인하지 못했다.

## preview와 navigation-path는 별도 float32 복사

VAdOurOh worker offset 5613 이후의 `preview`, `navigation-path`는 WASM을 호출하지 않는다. `width * height`개 점에 대해 각 record의 `point_step`과 앞 세 field의 offset을 읽고, `DataView.getFloat32(offset, true)`로 XYZ를 복사한다. 입력의 field 이름·datatype·endianness를 일반적으로 해석하는 parser가 아니라 이 형태를 전제한 경로다.

두 메시지 각각 width 1, height 1, point_step 16, field offset `[4,8,12]`, 값 `[1.5,2.5,3.5]`를 넣었다. 반환은 동일 XYZ였고 WASM generate 호출 수는 증가하지 않았다. main 18648은 preview를 `updateLaserPointCloud`, navigation-path를 `updateNavPathPointCloud`에 전달한다. 이를 누적 WASM의 잡음 제거 결과로 설명하면 안 된다.

## 이름이 slam인 이미지 worker의 실제 동작

`slam.worker-B9-NnJ09.js`에는 WASM 로드가 없다. offset 3960의 `$` 함수는 `image_.data_`를 base64 해제하는 `q`를 호출하지만 그 반환값을 쓰지 않는다. 이어서 `width * height * 3` 길이의 새 `Uint8ClampedArray`를 만들어 그대로 반환한다. 새 배열은 0으로 초기화된다.

fixture에서 입력 bytes `[1,2,3,4,5,6]`, width 2, height 1을 base64로 전달하자 `[0,0,0,0,0,0]`이 돌아왔다. WASM fetch와 generate는 없었다. 따라서 이 worker를 지도 이미지의 실제 정제나 SLAM 알고리즘 근거로 사용할 수 없다. 이것이 앱 전체 SLAM이 작동하지 않는다는 뜻은 아니다. main에서 실제 mapping에 연결된 worker는 위 VAdOurOh이며, 이 이름의 이미지 worker가 사용자 기능에서 호출되는지는 이번 범위에서 미확인이다.

## 재현 파일과 남은 경계

```powershell
node --max-old-space-size=128 --wasm-max-mem-pages=1536 inbox/jay/20261013-go2-app-study/astra10/wasm-analysis/fixtures-wrappers.cjs points
node --max-old-space-size=128 --wasm-max-mem-pages=1536 inbox/jay/20261013-go2-app-study/astra10/wasm-analysis/fixtures-wrappers.cjs mesh
node --max-old-space-size=128 --wasm-max-mem-pages=1536 inbox/jay/20261013-go2-app-study/astra10/wasm-analysis/fixtures-wrappers.cjs image
```

입력, 반환 배열, 실제 malloc pointer, generate 인자, reset 호출 수, 원문 문자 offset은 [점 결과 5건](fixtures-wrappers-points.json), [mesh 결과 2건](fixtures-wrappers-mesh.json), [이미지 결과 1건](fixtures-wrappers-image.json)에 있다. 세 결과 모두 `assertions_passed: true`를 직접 확인했다. 기존 WASM fixture 28건을 이 8건과 혼동해 새로 36건을 실행했다고 보고하지 않는다.

확인한 범위에서는 시각화용 key 억제와 표면 생성이 있다. 동적 장애물 판별, 시간 기반 transient 제거, 통계적 이상치 제거, 군집 크기 판정, negative obstacle 판별, 안전한 free-space 판정은 이 세 worker의 알고리즘에서 확인되지 않았다. 이런 기능이 robot 측 또는 다른 앱 모듈에 없는지까지 조사한 것은 아니다. 앱 설계에 이 결과를 옮긴다면 표시 정리와 항법 지도 변경을 별도 기능으로 두고, 실제 데이터 계약과 지도 버전 관계를 별도로 검증해야 한다는 것은 설계 제안이다.
