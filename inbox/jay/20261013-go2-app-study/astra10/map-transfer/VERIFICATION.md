> 분류: 검증 기록
> 작성: ASTRA10 map-transfer 조사 세션 · 2026-10-13
> 근거: 현재 조사 세션의 Python 실행 결과 · 공개 GitHub HTTPS 응답 · MAP-TRANSFER.md 재읽기
> 요지: 회전 원점·행 반전·화살표·FOV 산술을 합성 입력으로 확인했고, 인용한 공식 소스 20개의 branch와 고정 commit 내용이 일치했다.
> 상태: 계산·파일 대조 확인됨 · 브라우저·ROS 런타임·Go2 실기 검증 미실행

# 지도 전용 조사 검증 기록

검증 대상은 [MAP-TRANSFER.md](MAP-TRANSFER.md)의 수식과 출처다. 제품 구현 테스트 또는 로봇 안전성 시험이 아니다. 직접 조회한 branch HEAD는 해당 보고서 표에 있다. 원점 회전 미지원 등 소스 읽기 결과를 ROS 노드에서 재현하지는 않았다.

## 답을 아는 입력 계산

아래 계산을 Python에서 실행해 assertion이 모두 통과했다. 부동소수점 왕복은 오차 1e-10 아래인지 확인했다.

```python
import math
r, w, h = .05, 3, 2
ox, oy, yaw = 10, 20, math.pi/2
for j in range(h):
    for i in range(w):
        gx, gy = (i+.5)*r, (j+.5)*r
        x = ox + math.cos(yaw)*gx - math.sin(yaw)*gy
        y = oy + math.sin(yaw)*gx + math.cos(yaw)*gy
        u = (math.cos(yaw)*(x-ox)+math.sin(yaw)*(y-oy))/r
        v = (-math.sin(yaw)*(x-ox)+math.cos(yaw)*(y-oy))/r
        assert math.floor(u) == i and math.floor(v) == j
        assert abs(u-i-.5) < 1e-10 and abs(v-j-.5) < 1e-10
data = [0, 100, -1, 50, 0, 100]
canvas = [data[i+w*j] for j in reversed(range(h)) for i in range(w)]
assert canvas == [50, 0, 100, 0, 100, -1]
assert math.isclose(math.degrees(2*math.atan(640/(2*320))), 90)
assert (round(math.cos(math.pi-yaw)), round(-math.sin(math.pi-yaw))) == (0,-1)
assert round(46/.05)*round(27/.05) == 496800
```

실행 결과: cell(2,1)=(9.925,20.125), 왕복 6칸 일치, 행 반전 일치, 화살표 (0,-1), 대칭 FOV 산술 90°, 지도 크기 산술 496,800칸. 카메라 실제 시야는 미측정이다.

## 공식 소스 재다운로드

본문 GitHub 고정 commit 링크 20개를 추출했다. 각 파일에 대해 `raw.githubusercontent.com/<repo>/<commit>/<path>`와 같은 파일의 branch URL을 인증 없이 읽고 byte 배열을 비교했다. **20/20 일치, 조회 오류 0개.** byte 동일성 검증은 검색 캐시 대신 실제 HTTP 응답으로 했다.

아래는 핵심 구현 파일의 고정 commit 응답 SHA-256이다. 모두 보고서의 Nav2 Jazzy commit `645abd95f2be02a13ca539b29c2ddc065db34f89`에 속한다.

| 파일 | SHA-256 |
|---|---|
| nav2_map_server/src/map_io.cpp | `ab627952ff7a2647365ff4a820089a571fb7b1abf77ceff7d2be1110c18002b1` |
| nav2_costmap_2d/plugins/static_layer.cpp | `81606bf320d682901f661fa83223da42d5c631add5eb98e0055aee29cd1ac4ac` |
| nav2_amcl/src/amcl_node.cpp | `8f458800deca6db48f53a9f6441fe010163aa3925ab40c6326b2762d7748aea8` |
| nav2_costmap_2d/src/costmap_2d.cpp | `ce221510cc609a43c1c984f0b0ef93fe5ff4bed006f5622bb314c19c5ad85e83` |
| nav2_costmap_2d/plugins/denoise_layer.cpp | `8a4b35a2ea7902160998fdd9ee83a955de57508586cc1b5180780889a400272b` |
| nav2_costmap_2d/plugins/obstacle_layer.cpp | `e2e6e56b04d6ade1ded6f17b08667dba220f453b6000c122ece638cee1839caf` |
| nav2_costmap_2d/plugins/costmap_filters/keepout_filter.cpp | `4bb7da72285b3ff592197935d5ce716885fd32d87f44346d5bf98ec0032e008e` |
| nav2_costmap_2d/plugins/costmap_filters/speed_filter.cpp | `1cffec0ff691f044d06fbfd1d7833938bcfba578b9fe5d357d96ddcf684b9e02` |

## 산출물 확인 범위

- 새 보고서의 첫 다섯 줄 메타데이터와 APP-PLAN-facts.md 상대 링크가 실제 파일로 연결되는지 검사했다.
- em dash는 0개다. 원본 보고서·기획 요약은 수정하지 않았다.
- Git 작업 디렉터리에 남의 변경이 다수 있어 pull·merge·rebase·commit·push를 실행하지 않았다. 할당된 `astra10/map-transfer/` 아래 신규 Markdown 두 개만 작성했다.
- 공개 문서 HTTP 조회와 로컬 계산만 했다. 기기 접속, ROS 노드 실행, 프로세스 종료, 인증 정보 조회, 외부 발송, 유료 호출은 하지 않았다.
