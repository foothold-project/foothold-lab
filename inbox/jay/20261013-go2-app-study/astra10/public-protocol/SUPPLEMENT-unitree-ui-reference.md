> 분류: 리서치 · ASTRA10 추가 공개 구현
> 작성: 오흥재 조사 보조 · 2026-10-13
> 근거: legion1581/unitree_ui 고정 main 및 feat/3d_lidar_mapping branch 소스
> 요지: 공개 브라우저 재구현에서 높이색 · 누적 worker · pose 보간 · 경로 · 목표 전송 연결을 확인했다. APK와 같다는 주석은 독립 확인되지 않았다.
> 상태: 공개 소스 정적 확인됨 · 공식 APK 동등성 미확인 · 실기 미측정

# 공개 unitree_ui 추가 참조

기존 4개 저장소 조사 뒤, 부모 조사자가 이전 APK 자산의 공개 참조를 요청해 범위를 추가했다. `legion1581/unitree_go2_ui`는 현재 `legion1581/unitree_ui`로 redirect된다. 이것은 공개 브라우저 재구현이다. 조사한 tree에서는 공식 APK 전체 JS archive를 찾지 못했다. 아래 주석은 **저장소 작성자가 APK를 참조했다고 주장하는 단서**이며 우리가 공식 APK와 대조해 확인한 사실이 아니다.

| 범위 | 고정 revision | 관련 원문 |
|---|---|---|
| main | `590baf6ab580d27890c7a7575c138a9080d7d516` | [voxel-map.ts](https://github.com/legion1581/unitree_ui/blob/590baf6ab580d27890c7a7575c138a9080d7d516/src/ui/scene/voxel-map.ts), [voxel-worker.ts](https://github.com/legion1581/unitree_ui/blob/590baf6ab580d27890c7a7575c138a9080d7d516/src/workers/voxel-worker.ts) |
| feat/3d_lidar_mapping | `8beafb4200965b33c64718e2717f975eff06d54e` | [slam-worker.ts](https://github.com/legion1581/unitree_ui/blob/8beafb4200965b33c64718e2717f975eff06d54e/src/workers/slam-worker.ts), [slam-scene.ts](https://github.com/legion1581/unitree_ui/blob/8beafb4200965b33c64718e2717f975eff06d54e/src/ui/scene/slam-scene.ts), [mapping-page.ts](https://github.com/legion1581/unitree_ui/blob/8beafb4200965b33c64718e2717f975eff06d54e/src/ui/components/mapping-page.ts) |

## 지도와 렌더링 두 경로

main의 `VoxelMap`은 `axisColor4.png` 텍스처, NearestFilter, MeshBasicMaterial을 쓴다. worker가 준 Uint8 UV를 정규화한 BufferAttribute로 넣고 mesh에 `resolution` scale과 `origin` translation을 적용한다. 기존 mesh는 제거·dispose한 뒤 새 mesh로 대체한다. 150 ms setTimeout 동안 pendingData를 덮어써 최신 payload를 하나 보내는 코드는 **공개 클라이언트의 제한 설정**이다. 실제 송수신 Hz가 아니다. face_count가 0이면 `applyGeometry`가 바로 반환하므로 이 함수에서는 기존 mesh가 유지된다. [voxel-map.ts L26-L38](https://github.com/legion1581/unitree_ui/blob/590baf6ab580d27890c7a7575c138a9080d7d516/src/ui/scene/voxel-map.ts#L26-L38), [L69-L128](https://github.com/legion1581/unitree_ui/blob/590baf6ab580d27890c7a7575c138a9080d7d516/src/ui/scene/voxel-map.ts#L69-L128).

`voxel-worker.ts`는 resolution이 falsy면 0.1을 쓰고, `floor(origin.z/resolution)`을 wasm generate에 넘긴다. 문서는 UV 높이색이라고 설명하지만 wasm 내부와 실제 텍스처 출력은 이번 조사에서 확인하지 않았다. 출처·함수·revision을 갖춘 후속 분석 후보다. [voxel-worker.ts L152-L169](https://github.com/legion1581/unitree_ui/blob/590baf6ab580d27890c7a7575c138a9080d7d516/src/workers/voxel-worker.ts#L152-L169), [작성자 lidar 문서](https://github.com/legion1581/unitree_ui/blob/590baf6ab580d27890c7a7575c138a9080d7d516/docs/lidar.md).

별도 3D mapping branch의 `SlamProcessor`는 입력 길이/6으로 점수를 계산하고 xyz min/max 경계와 데이터를 wasm에 전달한다. 최대 점수 상수는 1,000,000이고 dictionary·index·output buffer를 유지한다. 반환값은 누적 `output`과 현재 `directOutput` 두 Float32Array다. `clear`에서는 dictionary와 index buffer를 0으로 채우고 reset export를 호출한다. JS wrapper만으로 내부 중복 제거의 정확한 voxel 간격, outlier 규칙, 오래된 점 소거 정책을 확정하지 않았다. [slam-worker.ts L15-L94](https://github.com/legion1581/unitree_ui/blob/8beafb4200965b33c64718e2717f975eff06d54e/src/workers/slam-worker.ts#L15-L94).

이 worker 머리 주석은 예전 APK 자산명 `three.worker-4tXjtm4c.js`와 `libvoxel-amusQfn9.wasm`을 적고 있다. export 구조는 b memory, c ctor, d reset, e generate, f malloc, g free라고 적혀 있다. 이는 이번 APK 조사에서 비교할 구체적 단서지만 해당 APK 파일 자체는 이 공개 저장소에서 확보하지 못했다. [slam-worker.ts L1-L13](https://github.com/legion1581/unitree_ui/blob/8beafb4200965b33c64718e2717f975eff06d54e/src/workers/slam-worker.ts#L1-L13).

## 높이색, pose, 경로

| 기능 | 공개 branch의 실제 코드 | 해석 제한 |
|---|---|---|
| 높이색 | `createHeightMaterial` shader는 z에서 `R=abs(sin(z))`, `G=0.5*abs(cos(z))`, `B=0.3`을 계산한다. | 이 브라우저 구현은 직접 확인됨. 공식 APK 동일 shader는 미확인. 순환 함수라 색을 절대 높이의 단조 범례로 설명하면 안 된다. |
| 누적/현재 cloud 구분 | worker newMap의 output은 `updatePointCloud`, directOutput은 `updateLaserCloud`로 간다. | 겉보기 정리와 실제 이상점 삭제를 구분해야 한다. |
| pose 표시 | quaternion에서 yaw를 구해 target pose를 갱신하고 매 렌더에 position lerp와 quaternion slerp를 계수 0.15로 적용한다. | 화면 위치의 부드러움이 지도 정확도나 센서 잡음 제거를 증명하지 않는다. |
| pose 처리 제한 | `handleOdom`은 경과 50 ms 미만이면 반환한다. 위에는 200 ms와 50 ms를 말하는 상충 주석이 함께 있다. | 코드 상수만 확인됨. 실제 20 Hz라는 측정값으로 바꾸지 않는다. |
| 지나온 경로 | XY 이동 제곱이 0.01보다 클 때 z=0 trace 점을 추가하고 최근 200점을 남긴다. | 완전한 임무 기록 경로가 아니라 화면용 꼬리다. 기록용 궤적은 별도 보존해야 한다. |
| 계획 경로 | PointCloud2의 처음 세 field offset에서 little-endian float32 XYZ를 읽고 빨간 Points로 렌더한다. 새 경로가 오면 이전 경로를 제거한다. | field 순서·datatype·endianness가 다른 메시지까지 지원한다는 근거는 없다. |

근거: [slam-scene.ts L10-L34](https://github.com/legion1581/unitree_ui/blob/8beafb4200965b33c64718e2717f975eff06d54e/src/ui/scene/slam-scene.ts#L10-L34), [mapping-page.ts L342-L363](https://github.com/legion1581/unitree_ui/blob/8beafb4200965b33c64718e2717f975eff06d54e/src/ui/components/mapping-page.ts#L342-L363), [slam-scene.ts L201-L222](https://github.com/legion1581/unitree_ui/blob/8beafb4200965b33c64718e2717f975eff06d54e/src/ui/scene/slam-scene.ts#L201-L222), [L608-L614](https://github.com/legion1581/unitree_ui/blob/8beafb4200965b33c64718e2717f975eff06d54e/src/ui/scene/slam-scene.ts#L608-L614), [mapping-page.ts L2092-L2124](https://github.com/legion1581/unitree_ui/blob/8beafb4200965b33c64718e2717f975eff06d54e/src/ui/components/mapping-page.ts#L2092-L2124), [slam-scene.ts L238-L276](https://github.com/legion1581/unitree_ui/blob/8beafb4200965b33c64718e2717f975eff06d54e/src/ui/scene/slam-scene.ts#L238-L276), [slam-worker.ts L150-L169](https://github.com/legion1581/unitree_ui/blob/8beafb4200965b33c64718e2717f975eff06d54e/src/workers/slam-worker.ts#L150-L169).

## topics와 목표 UI의 기획 차이

branch `topics.ts`에는 `rt/uslam/frontend/cloud_world_ds`, `rt/uslam/frontend/odom`, `rt/uslam/cloud_map`, `rt/uslam/localization/odom`, `rt/uslam/localization/cloud_world`, `rt/uslam/navigation/global_path`가 있다. `mapping-page.ts`는 cloud·pose·path를 각 handler로 분기한다. 기존 4개 저장소의 오래된 `qt_*` 상수만 볼 때보다 구체적인 후속 분석 단서다. [topics.ts L32-L41](https://github.com/legion1581/unitree_ui/blob/8beafb4200965b33c64718e2717f975eff06d54e/src/protocol/topics.ts#L32-L41), [mapping-page.ts L1681-L1708](https://github.com/legion1581/unitree_ui/blob/8beafb4200965b33c64718e2717f975eff06d54e/src/ui/components/mapping-page.ts#L1681-L1708).

코드는 목표 포즈를 놓으면 navigation이 비활성 상태인 경우 start를 먼저 발행하고 goal pose를 전송한다. 이는 `APP-PLAN-facts.md`의 목표 선택 후 경로 검사와 확인을 거치는 정책과 다르다. 이 공개 UI의 목표 이벤트 처리를 그대로 이식해서는 기획을 충족하지 않는다. 명령은 정적 분석만 했고 로봇에 보내지 않았다. [mapping-page.ts L985-L1027](https://github.com/legion1581/unitree_ui/blob/8beafb4200965b33c64718e2717f975eff06d54e/src/ui/components/mapping-page.ts#L985-L1027).

main 루트 LICENSE는 MIT다. 소스 재사용 시 저작권·허가 고지를 보존한다. APK에서 가져왔다고 주석에 적힌 wasm·텍스처의 출처와 권리까지 MIT가 입증한다고 해석하지 않는다. 이 조사에서는 wasm·텍스처를 다운로드하지 않았다. [LICENSE](https://github.com/legion1581/unitree_ui/blob/590baf6ab580d27890c7a7575c138a9080d7d516/LICENSE).

다운로드한 TypeScript·문서는 `legion1581__unitree_ui/source/` 및 `source-3d-branch/`에 있으며 source-manifest SHA-256로 검증했다. 브라우저·worker·wasm의 실제 실행 결과는 미확인이다.
