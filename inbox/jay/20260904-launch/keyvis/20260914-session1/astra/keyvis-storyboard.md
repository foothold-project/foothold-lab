# FOOTHOLD 런칭 A · 키비주얼 스토리보드 설계

> 분류: 계획
> 작성: 키비주얼 설계 워커 · 2026-09-14 02:19
> 근거: keyvis-brief.txt, 제작 설계 v1.2, 브랜드 브리프, 감독 시나리오, 라이브러리 목록과 직접 열람한 이미지
> 요지: 19컷의 대표 정지 화면을 라이브러리 캡처 4컷·신규 생성 13컷·원본 구조판 2컷으로 확보하는 제작 명세
> 상태: 설계 발행 가능. gpt-6-astra·high 2차 독립 검증 통과. 이미지 생성·캡처 파일 제작·영상 제작은 수행하지 않음. 원본 일부 프레임은 메모리에서 디코드해 열람. 구조판 2컷은 완성 룩 승인 대상이 아님
> 판: v1.1

이번 결과는 **컷마다 대표 이미지 한 장을 고르고 만드는 방법**이다. 최종 대상은 s01~s16, s10b, s15b, s1718의 19컷이다. s1718은 하나로 세며 s19는 기존 12초 엔딩이므로 생성표에서 제외한다. 기존 `prompts.json`은 열지 않았고 문구를 재사용하지 않았다. 아래 영문은 이번 정지 화면용으로 새로 작성했다.

원자료를 직접 보니 결말의 관문이 구체적으로 드러났다. `s16_2.png`는 직사각형 군집이고 `s1718_0.png`는 이미 글자의 빈 획이 보이는 군집이다. **이 두 화면만으로 같은 대열의 연속 상승이라고 승인할 수 없다.** 따라서 이 둘은 브리프가 허용한 (c) 구도 참조판으로 출발한다. 생성 모델에 정확한 8192개체나 FOOTHOLD 배치를 다시 그리게 하지 않는다. c 두 장까지 모두 같은 룩의 완성 키비주얼을 얻었다고 보고하지 않는다. 필요한 후속 구조 수정·험지화·룩 합성 조건은 4절에 명시했다.

`확인됨`은 문서·파일 또는 직접 본 정지 화면으로 확인한 범위다. `설계값`은 제작자가 이번에 정한 수치다. 렌즈·카메라 높이·화면 점유율은 EXIF나 Isaac 카메라에서 잰 값이 아니다. `미확인`은 동영상 정상속도 검수·실제 생성 성능·현 계정 UI처럼 이번에 직접 확인하지 않은 것이다. 정지 화면의 발 위치만으로 미끄러짐 없는 보행이나 연구 성능을 입증하지 않는다.

## 0. 전체 톤 기준선

**모래빛 대기 속에서 흰 Go2가 바위와 자갈의 높이를 골라 디디고, 긴 그림자와 반복되는 대열이 무게를 만든다.** 따뜻한 황갈색 빛을 쓰되 정서는 냉정하고 정밀하다. ‘냉정’을 청색 필터로 번역하지 않는다. 주인공은 특정 영웅 로봇이 아니라 같은 보행 정책의 수많은 실행이다.

| 항목 | 고정할 문장 |
|---|---|
| 색 | 흙은 낮은 채도의 황갈색·회갈색, 돌의 그늘은 짙은 갈회색, 먼지는 옅은 모래색이다. 흰 차체의 밝은 면은 누렇게 칠하지 않고 따뜻한 반사광만 받는다. 청록·주황의 강한 이중 색조나 일괄 세피아를 쓰지 않는다. |
| 빛 | 같은 낮은 태양 하나와 긴 그림자를 유지한다. 새 컷의 월드 진행을 +X, 주광을 진행 전방의 옆쪽으로 정하고, s12~14에서는 화면 왼쪽 위의 역측광으로 통일한다. 기존 컷의 태양 좌우를 그대로 복제하지 않고 해당 시점의 방향과 그림자로 비교한다. |
| 대기 | 먼 배경의 모래빛 안개, 중경의 얇은 부유 먼지, 발 근처의 개별 입자가 다른 깊이에 있다. 폭풍 안에서도 가까운 발과 땅을 확인할 틈이 남는다. 먼지를 불투명 갈색 덩어리로 채우지 않는다. |
| 지형 | 하나의 넓은 건조 분지에 낮은 암반 돌출, 박힌 자갈, 모래가 찬 홈과 작은 둔덕이 공존한다. 바위가 화면 가장자리에만 있고 보행면은 평평한 길인 후보는 탈락이다. 절벽·점프 코스·협곡 종주로 규모를 과장하지 않는다. |
| 로봇 | 승인 v3의 흰 차체, 검은 전면 센서와 하부 센서 구조, 둥근 검은 발끝, 단단한 관절 연결을 유지한다. 흰 재질에는 부드러운 반사가 있고 발·하부에만 얇은 흙먼지가 묻는다. 새 장갑·발톱·램프·센서를 추가하지 않는다. |
| 험지 반응 | 읽을 수 있는 근경에서는 지지발이 서로 다른 실제 지면 높이를 받치며 다른 발은 돌을 넘는 높이를 확보한다. 관절 굽힘과 작은 몸통 피치가 그 지형과 맞아야 한다. 모든 발을 같은 수평선에 놓고 바위 텍스처만 덧칠한 후보는 탈락이다. |
| 규모 | 원경은 작은 실루엣과 층층이 사라지는 대열, 근경은 실제 Go2 크기의 접점으로 장엄함을 만든다. 큰 발 하나를 괴수 크기로 확대하지 않는다. 로고를 읽기 전까지는 전체 글자 윤곽을 숨긴다. |
| 브랜드 | 다크는 지면·그늘·엔딩의 바탕이다. 본편을 검게 뭉개지 않는다. 새 주황 격자나 측정선을 생성하지 않고 주황의 명시적 신호는 승인된 엔딩 자산이 맡는다. |

### 무드 앵커 세 개

아래 앵커 시점은 **해당 원본 MP4 시작 0.000초**다. `_0` 섬네일로 룩을 검토한 뒤 39·44·46 원본의 실제 0.000초도 메모리에서 디코드해 직접 확인했다. 섬네일의 `_0`을 정확한 타임코드로 간주하지 않는다. 앞으로 입력용 캡처는 원본 영상의 첫 디코드 프레임에서 만들며, 프리비즈의 자막이 붙은 화면이나 640×360 섬네일을 최종 소스로 쓰지 않는다.

| 앵커 | 파일·시점 | 승인한 정보 | 모델에 넘길 부분 |
|---|---|---|---|
| 39 · 대기와 흰 차체 | `39-1548-seedance-02_aisle.mp4`, 0.000초 | 모래빛 안개, 차체의 밝은 면과 그늘, 낮은 태양 | 하늘·먼지만 있는 부분. 군집·가까운 로봇·통로 배치는 제거한다. 전체 이미지는 제작자 비교용이다. |
| 44 · 돌과 접점 | `44-1548-seedance-01_side.mp4`, 0.000초 | 날카롭지 않게 닳은 암석, 자갈과 모래의 입자 차, 역측광 | 하단 중앙의 로봇·그림자 없는 흙과 작은 돌 부분. 머리·발·수평선은 넣지 않는다. |
| 46 · 거리와 규모 | `46-1556-seedance-06_dolly.mp4`, 0.000초 | 가까운 대열과 먼 대열의 대비 감소, 먼지 속 흰 점의 반복 | 하늘·먼지 띠만 분리. 군집 배치는 검토용이며 생성 입력의 배치 권한은 없다. |

39~47은 전체 룩의 기준 구간이지 모든 프레임의 배치·모델·보행이 자동 승인됐다는 뜻이 아니다. 40은 이번 목표에 비해 성기고, 45는 중앙 한 줄만 남는 구도다. 47은 먼지와 압도감은 좋지만 직사각 대군과 비교적 평평한 외곽 땅을 그대로 물려받지 않는다. 세 앵커로만 입력 룩을 관리하고 45·47을 추가해 서로 다른 지형과 배치를 섞지 않는다.

### 참조를 업로드하기 전에

입력 준비는 다음 제작 세션에서 수행할 작업이다. 이번 워커는 아래 명세 외의 파일을 만들지 않았다. 원본 캡처·배경 분리·크롭의 저장 위치는 제작 담당자가 승인된 기존 작업 위치에서 정한다.

| 코드 | 실제 원본 | 입력용으로 남길 것 |
|---|---|---|
| C-F / C-B | `charsheet3/front.png` / `back.png` | 해당 뷰의 로봇 외곽만 선택·마스킹한다. 하늘·격자·원본 접지 그림자는 제거한다. |
| C-L / C-R | `charsheet3/left.png` / `right.png` | 좌·우를 뒤집지 않고 실제 해당 면을 쓴다. 몸통과 연결된 네 다리의 실루엣만 남긴다. |
| C-Q | `charsheet3/q34.png` | 앞사선 외형만. 이 파일은 오른사선 시트가 아니므로 반전해서 맞추지 않는다. |
| C-foot | `charsheet3/foot.png` | 검은 발끝과 흰 하부 다리의 형태만. 원본은 발밑 틈처럼 보이는 경계가 있어 접지 자세·그림자의 정답으로 쓰지 않는다. |
| M39 / M46 | 위 앵커 39 / 46의 0.000초 캡처 | 화면 상부에서 로봇·땅·고유 산세 없는 대기 조각 하나. 태양 원반을 잘라내도 색·산란의 관계는 유지한다. |
| T44 | 앵커 44의 0.000초 캡처 | 화면 하단 중앙의 자갈·모래·작은 돌 조각. 로봇의 일부, 차체 그림자와 큰 바위 윤곽이 들어오면 더 좁힌다. |
| K컷번호 | 이번 설계로 앞으로 만들고 감독이 선택할 이미지 | 승인된 새 구도·지면·외형만. 아직 파일이 존재하지 않는 계획 자산이다. 다음 컷에 넣기 전 결함 검수를 다시 한다. |

C 입력은 원본 로봇 픽셀을 보존하는 마스크 편집으로 준비한다. 자동 배경 제거가 발끝·센서까지 깎으면 수동으로 복구한다. 배경을 제거하지 못한 원본 시트 전체를 대신 업로드하지 않는다. 모델에서 ‘격자는 무시’라고 지시하는 것으로 이 절차를 대체하지 않는다. M·T는 작아도 의미가 분리된 크롭을 쓰며 저해상도 크롭을 세부 형상의 증거로 쓰지 않는다. 원본 구조를 보존할 수 없는 크롭은 참조를 더 넣기보다 제외하고 그 사실을 기록한다.

## 1. 컷별 대표 키비주얼과 확보 방법

**a**는 원본 캡처, **b**는 무제한 이미지 모델 신규 생성, **c**는 Isaac 프리비즈를 그대로 놓는 톤 변환 전 구조판이다. a의 시점은 원본 MP4 기준이다. b의 모델은 모두 **Seedream 4.5**로 고정한다. 여러 참조 역할을 나누고 16:9로 만드는 한 파이프라인에서 룩을 맞추려는 선택이며, 이 로봇에서 모델별 성공률을 실험해 얻은 우열은 아니다. c는 웹 이미지 생성 입력으로 업로드하지 않는다.

대표판은 그 컷의 **가장 중요한 한 순간**이다. 영상 시작 이미지를 뜻하지 않는다. 특히 s03의 접지판·s15b의 안정판을 그대로 영상 G0으로 넣으면 앞선 사건이 사라진다. 영상 단계에서는 제작 설계 v1.2의 앞 핸들·사건·뒤 핸들을 별도로 만든다.

| 컷·역할 | 대표 한 장의 정의: 구도·높이/렌즈감·순간·지형·먼지·빛 | 기본 확보 경로·선택 이유 | 참조 사용: 캐릭터 / 앵커 / 프리비즈 | 합격 기준 세 줄 | 실패 시 되돌아갈 곳 |
|---|---|---|---|---|---|
| s01 · 불확실한 땅 | 낮은 암반 너머 넓은 분지. 높이 3~5m·28~35mm 느낌. 로봇 등장 전의 빈 지면. 가까운 암반·중경 자갈·먼 모래 언덕. 낮은 사광과 층진 안개. | **b**, Seedream 4.5. 기존 오프닝의 깊은 계곡을 새 보행 공간의 필수 구조로 묶지 않기 위해 새 로케이션판 생성. | 없음 / M39+T44 / 업로드 없음, s01은 사람이 원경 기능만 참고 | ① 바위·자갈·홈이 전경과 진행할 중경에 있다.<br>② 같은 분지의 먼 진입 구역을 배치할 공간이 있다.<br>③ 낮은 광원과 모래빛 안개가 39·44에 이어진다. | 산이 과대하면 거대 협곡 문장을 추가하지 말고 낮은 분지로 다시 생성. K01이 로케이션 기준이 된다. |
| s02 · 먼 지평선 접근 | 관측점 A, 높이 0.5~0.8m·50~70mm 느낌. 지평선 바로 아래 작은 Go2 실루엣. 가장 큰 개체 높이 약 화면 0.5~1.5%를 출발점으로, 넓은 빈 험지가 화면 하부에 남는다. | **b**, Seedream 4.5. 빈 평지 격자·가까운 등장 대신 원거리 실루엣을 새로 설계. | C-F / M39+승인 K01 / 원본 업로드 없음 | ① 먼저 멀리 있는 무언가로 읽힌다.<br>② 빈 지면은 요철 있는 험지이며 먼 발의 높낮이는 해상도 밖이라고 기록한다.<br>③ K04와 같은 능선·전경 돌·광원을 유지할 기준판이다. | 처음부터 로봇이 크면 화면 점유율만 낮춘다. 공간이 달라지면 K01부터 비교한다. |
| s03 · 첫 디딤 | 관측점 B의 발목 아래, 높이 8~12cm·28~35mm 느낌. 오른앞발이 박힌 낮은 돌에 처음 하중을 받는 순간. 다른 지지는 낮은 모래에 있고 다리 각도가 다르다. 발밑이 보이며 옆먼지와 작은 접지 후 먼지가 구별된다. | **b**, Seedream 4.5. 첫발 인과·다른 높이의 접점을 새로 만들며 평지 트롯 프레임을 배제. | C-foot+C-R / M39+T44 / 없음 | ① 검은 발끝이 돌의 접촉면에 닿고 부유 틈·관통이 없다.<br>② 후속 지지와 계속 진행할 몸통 일부가 읽히며 마지막 정지처럼 보이지 않는다.<br>③ 먼지는 발 형태를 가리지 않고 미래 접점에서 솟지 않는다. | 먼저 전경 한 발과 지지 한 발만 읽히게 단순화. 바위·발 경계를 고친 후 먼지량 조정. |
| s04 · 같은 원경의 진전 | K02와 같은 A·같은 렌즈. 실루엣이 조금만 커지고 흰 몸통·검은 센서 구별의 단서가 생기지만 여전히 멀고 먼지 속이다. 전경 돌과 능선은 고정. | **b**, Seedream 4.5. 승인 K02에 기반한 후속 정지 화면으로 같은 카메라 보존. | C-F / M39+K02 / 없음 | ① K02의 전경 돌·수평선이 같은 자리에 있다.<br>② 확대가 갑작스러운 근접 등장으로 읽히지 않는다.<br>③ 험지와 주광이 이어지고 K03의 근접 표식을 복사하지 않는다. | K02로 돌아가 변경량 축소. 카메라가 달라지면 그 후보를 버린다. |
| s05 · 행렬 내부 | 통로 안 몸통 높이·28~35mm 느낌. 오른쪽 가까운 차체와 중앙 여러 거리의 로봇. 자갈·암반 사이 보행면과 긴 그림자. 먼지 가시성은 발밑을 남긴다. | **a**, `39-1548-seedance-02_aisle.mp4` **0.000초**. 내부 거리감과 기본 룩이 이미 있다. | v3는 옆 비교만 / 39 자체 / 없음 | ① 가까운 차체·중경 접점·먼 군집의 세 깊이가 읽힌다.<br>② 원본 크기에서 접점과 지면 단차의 대응을 확인한다.<br>③ 로봇 외형·과도한 가림이 v3 및 K03과 충돌하지 않는다. | 우선 같은 원본의 인접 프레임에서 선택. 접지나 외형 결함이면 a를 폐기하고 C-B·M39·T44로 해당 구도 신규 작성. |
| s06 · 넓은 횡대 통과 | 높이 0.4~0.6m·35~50mm 느낌. 넓은 대열의 정면에 가까운 사선. 가까운 소수는 화면 높이 약 10~15%로 지지를 읽히고 뒤에는 반복 대열. 낮은 암반 턱·모래 홈 위 서로 다른 발 높이와 작은 피치, 긴 그림자·얇은 먼지. | **b**, Seedream 4.5. 41의 지정 캡처는 험지 반응이 식별되지 않아 제외. 넓은 통과 기능을 유지하면서 가까운 지지를 새로 구성. | C-F / M39+T44 / 없음, 41은 사람 구도 비교만 | ① 넓은 횡대와 뒤의 반복이 읽힌다.<br>② 가까운 같은 로봇의 두 지지 높이와 몸통 피치가 실제 요철에 대응한다.<br>③ s05보다 넓어지되 s11의 전체 밀도와 규모를 미리 소진하지 않는다. | 전경 소수의 점유율·낮은 암반 턱부터 고친다. 지지 대신 주변 바위만 늘리는 후보는 폐기. |
| s07 · 근접 기체와 반복 | 발목보다 높은 낮은 앵글·35mm 느낌. 가까운 등·후측면, 다른 높이의 돌과 모래 위로 이어지는 대열. 역광이 흰 패널 경계를 만든다. | **a**, `43-1548-seedance-00_foot.mp4` **0.500초**. 원본 0.000·0.250·0.500초 비교 후 선택.  프리비즈 s07의 실화면은 이 계열이며 파일 이름의 ‘foot’만으로 s03에 매핑하지 않음. | C-B 비교만 / 43을 39와 비교 / 없음 | ① 근경 Go2 하체와 먼 반복이 동시에 읽힌다.<br>② 낮은 앵글이 실제 크기를 유지하며 지지와 들어 올린 발을 구별할 수 있다.<br>③ 바위·모래·빛이 s05~06과 같은 세계다. | 관절 합체·공중 네 발이면 인접 프레임 또는 신규 생성. 잘못된 형태를 단순 톤 수정으로 살리지 않는다. |
| s08 · 측면에서 통로의 깊이 | 차체 아래 높이·28~35mm 느낌. 화면 가까이 스치는 Go2 측면, 그 뒤 양옆 대열이 먼 통로로 수렴. 돌·자갈이 전경 프레임을 잡고 낮은 태양이 몸통 테두리를 밝힌다. | **a**, `44-1548-seedance-01_side.mp4` **0.000초**. 측면 구조와 통로를 동시에 보여주는 기존 룩. | C-R 비교만 / 44 자체 / 없음 | ① 실제 측면 패널과 센서 구조가 v3에 맞는다.<br>② 가장자리에서 잘린 발을 접지 증거로 세지 않고 남은 지지·중경 발을 확인한다.<br>③ 가까운 몸통 때문에 통로 깊이가 전부 사라지지 않는다. | 인접 프레임에서 가림이 적은 지점 선택. 지지 자체가 읽히지 않으면 신규 구도로 전환. |
| s09 · 스침 직전 | 지면에 가까운 24~28mm 느낌. 오른쪽 가까운 Go2가 진행 중이고 왼쪽과 후경에 다른 개체. 움푹 팬 모래·자갈, 전경 큰 돌. 낮은 역측광과 발목 아래 먼지. | **a**, `42-1548-seedance-04_underfoot.mp4` **0.250초**. 원본 0.000·0.250·0.500초 비교 후 선택.  확정 프리비즈 s09 계열의 근접 통과. | C-F+C-R 비교만 / 42를 44와 비교 / 없음 | ① 공중 스윙발과 실제 지지발을 구별할 수 있다.<br>② 가까운 발이 땅을 관통하거나 전체가 공중에 뜨지 않는다.<br>③ 작은 돌과 접점이 남고 s10 발밑 앵글로 시선이 이어진다. | 근접 스침을 이유로 접지를 가린 테이크는 제외. 주변 프레임 검수 후에도 실패하면 s10b 방식의 새 정지판으로 교체. |
| s10 · 발밑 험지 대응 | 높이 5~8cm·24~28mm, 카메라는 몸통 아래가 아니라 열린 발 사이 통로 가장자리. 한 발은 낮은 암반 위에 지지, 다른 발은 홈 너머 스윙. 몸통 하단에 지형에 맞춘 작은 피치. | **b**, Seedream 4.5. 평지 프리비즈의 인상만 취하고 접지 구조를 새로 설계. | C-F+C-foot / M39+T44 / 없음 | ① 두 지면 높이가 원근 착시가 아닌 같은 근경에서 보인다.<br>② 발목·몸통 연결과 여유 공간이 보인다.<br>③ 첫발·정지 슬램을 반복하지 않고 진행 중인 지지 교대다. | 렌즈를 28~35mm 쪽으로 줄이고 한 전경 로봇에 집중. 카메라 관통·거인화는 즉시 폐기. |
| s10b · 발 스침 | 높이 8~12cm·28~35mm. 가까운 오른쪽 다리가 프레임 가장자리, 중앙 통로는 열려 있다. 스윙발이 박힌 돌을 넘고 반대 발은 낮은 모래를 받친다. 바닥 먼지와 낮은 사광. | **b**, Seedream 4.5. 평지 보행 대신 가까운 발의 회피 높이와 지지를 함께 보임. | C-R+C-foot / M39+승인 K10 / 없음 | ① 스치는 다리와 지지발이 별개의 연결된 다리다.<br>② 돌 위 스윙 높이·낮은 지지·몸통이 맞물린다.<br>③ K10의 지질·빛이 유지되고 새 방향 전환이 없다. | K10으로 복귀해 카메라 옆 이동만 수정. 과도한 가림이면 전경 다리를 바깥으로 이동. |
| s11 · 선회 중 규모 | 높이 1~2m·28~35mm, 높은 사선이지만 탑뷰 아님. 통로 하나 외에는 여러 열이 전경부터 안개 속까지 밀도 있게 연결. 박힌 돌·모래 홈에 각기 다른 지지. | **b**, Seedream 4.5. 40의 성긴 군집을 고정하지 않고 규모 보강. | C-Q / M46+T44 / 없음 | ① 의도한 통로와 의도하지 않은 빈 구역이 구별된다.<br>② 근경 발·관절이 지형에 반응하고 로봇이 겹치지 않는다.<br>③ 아직 글자 형상은 읽히지 않으며 s12로 갈 열린 통로가 있다. | 가까운 열 수부터 정리. 반복 실패하면 제어 가능한 군집 배치판을 만들고 룩만 합성. |
| s12 · 폭풍 접근 | Go2 등 상단 높이 약 0.45~0.65m·35mm. 같은 +X를 향한 등·후사선과 열린 통로. 앞의 R-A, 통로 왼쪽 낮은 돌 L-A. 렌즈 앞과 중경 땅은 맑고 먼 전방의 유한한 먼지 띠가 보인다. | **b**, Seedream 4.5. 프리비즈의 높고 이미 뿌연 시작을 배제하고 공간을 새로 확정. | C-B / M39+T44+승인 K14는 사람이 역검토 / 없음 | ① 렌즈와 먼지 띠 사이에 맑은 험지가 남는다.<br>② 가까운 지지발의 높낮이·통로·R-A가 읽힌다.<br>③ L-A·빛·진행축이 다음 K13·K14에서 유지될 구조다. | 먼저 먼지 적은 통로를 확정. 구조가 맞기 전 큰 폭풍으로 덮지 않는다. |
| s13 · 폭풍 안의 지속 | K12와 같은 높이·렌즈·진행 방향. 띠 안에서 한순간 시야가 열려 R-A의 등과 접지, L-A와 바닥을 동시에 봄. 가까운 먼지 가닥·중경 베일·먼 층이 분리. 빛은 같은 방향에서 산란. | **b**, Seedream 4.5. 승인 K12의 구조를 이어받아 내부 상태만 변경. | C-B / K12+M39 / 원본 없음 | ① R-A·L-A·통로가 같은 위치 관계다.<br>② 폭풍 속에도 한 지지와 다음 디딤 높이가 읽힌다.<br>③ 별도 폭풍·새 사막·정면 영웅 포즈로 바뀌지 않는다. | K12로 복귀. 같은 통로에 세 깊이의 먼지를 얹는 구조로 단순화. |
| s14 · 일렬 행군과 감속 | K12~13의 출구, 등 높이~약 1m·35~40mm. 중앙 한 줄이 멀리 이어져 일렬 행군을 읽히고 양옆에는 대군의 보조열이 남는다. R-A는 앞에, L-A는 같은 쪽. 짧아진 보폭과 낮은 돌 위 지지, 하부의 먼지 흔적. | **b**, Seedream 4.5. 실제 Go2로 재생성. 기존 45의 ‘전체가 단 한 줄’인 구조를 입력에서 뺀다. | C-B / M39+T44, 연속성 조정 때 K13 / 없음 | ① 중앙 일렬의 읽힘과 주변 대군의 존재가 함께 남는다.<br>② 바위·모래 단차에 맞춘 지지가 있으며 최종 오른앞발 접지는 아직 아니다.<br>③ R-A·주변 열·통로가 s1718 같은 구역 및 s16과 일치한다. 자료 확보 전 잠정판이며, 폭풍은 옆·뒤 잔여로만 남는다. | 중앙열 구도를 유지하고 보조열만 보강. 시점이 다른 로봇으로 바뀌면 K12의 R-A부터 재확인. |
| s15 · 마지막 지지의 인계 | 높이 15~25cm·35~50mm, R-A 우측면. 머리 방향과 발·L-A 계열 표식이 함께 보인다. 다른 발들은 받치고 오른앞발이 마지막 짧은 스윙을 막 시작. 낮은 모래와 돌 접점, 잔먼지. | **b**, Seedream 4.5. 완전 정지·평지 트롯 프레임 대신 마지막 발 이전 상태 작성. | C-R+C-foot / M39+T44, K15b는 사람이 역검토 / 없음 | ① 이미 지지 중인 발과 마지막 스윙발을 구분한다.<br>② 오른앞발이 닿을 낮은 돌이 K15b와 같다.<br>③ 머리·빛·표식으로 타이트와 시점이 이어지고 최종 접점이 s1718 같은 구역 및 s16에 대응한다. 자료 확보 전 잠정판. | K15b 접점으로 돌아가 지형·발을 고정하고 사건 시점만 앞당긴다. 완료 정지 포즈 재사용 금지. |
| s15b · 디딜 곳을 확보한 순간 | s15와 같은 우측, 높이 8~15cm·35~50mm. 마지막 오른앞발이 낮은 돌에 닿아 하중 흡수를 마치고, 다른 발은 모래·자갈의 다른 높이를 받친 순간. 뒤에 가까운 2~3대 지지와 먼 열. 발 주위 낮은 잔먼지만. | **b**, Seedream 4.5. 최종 접지·안정 상태가 이 영화의 절정이므로 신규 작성. | C-foot+C-R / M39+T44 / 없음 | ① 전경 접점이 선명하고 몸통과 지지다리가 안정돼 있다.<br>② 주변 로봇은 네 발 동시 점프가 아닌 각자 필요한 지지를 마친 상태다.<br>③ 안정된 최종 접점·주변 열이 s1718 같은 구역 및 s16과 일치한다. 자료 확보 전 잠정판이며 승전·고장·주저앉음은 제외. | 한 전경 로봇부터 통과시킨 뒤 배경 소수·정지군집을 별도 합성. ‘쿵’을 먼지 폭발로 해결하지 않는다. |
| s16 · 끝없는 후퇴의 규모 | 실제 원본의 높은 정면 사선과 원근을 유지한 `s16_2.png`. 반복 대열과 한 점으로 수렴하는 깊이. 최종 룩 목표는 46의 대기·낮은 태양, 지지 아래 실제 요철·잔먼지다. 원본은 평지 격자다. | **c**, `previs_frames/s16_2.png` 그대로. 연결 구조를 확인하기 전 자유 생성으로 배치를 바꾸지 않는 선택. | v3 비교만 / 46 비교만 / 사람·합성의 구조 참조만, 모델 업로드 없음 | ① c 판정: 원본 프레이밍을 그대로 보여준다.<br>② 최종판 관문: 근경 정지 지지와 험지화가 일치해야 한다.<br>③ 최종판 관문: s1718 배치·카메라 경계를 실제 소스로 맞춰야 한다. 현재 ②③ 미통과. | s1718의 정본 배치에서 s16 관측 구역을 다시 정하고 같은 카메라 경로·정지 군집·험지 지지를 제어해서 재렌더. |
| s1718 · 상승 끝의 이름 | 대표는 전체 FOOTHOLD가 군집으로 읽히는 `s1718_1.png`. 높은 하향 시점·압축된 원근. 최종은 같은 돌·모래 지형의 미세 기복 위 고정 군집, 획을 가리지 않는 옅은 대기. 시작·끝은 검수용 옆 비교. | **c**, `previs_frames/s1718_1.png` 그대로. 정본 글자·개체 배치를 이미지 모델의 추측에 맡기지 않음. | v3 비교만 / 46 비교만 / 사람·합성의 구조 참조만, 모델 업로드 없음 | ① c 판정: 소스의 획·빈 공간을 바꾸지 않는다.<br>② 최종판 관문: 8192는 씬 객체 자료로 재계수하고 접지·험지·정지를 확인한다.<br>③ 최종판 관문: 같은 상승의 s1718_2 도달 크기가 정본 엔딩으로 이어져야 한다. 현재 ②③ 미확인. | 정확한 대형 원본·마스크를 보존하고 지면·대기·빛을 합성. 글자 형태나 위치를 바꾼 생성물로 교체하지 않는다. |

### 컷마다 남길 다섯 줄의 참조 기록

아래 다섯 필드를 각 컷의 기록으로 사용한다. ‘합격 증거’는 앞으로 검사할 비교 대상을 뜻하며 이미 합격했다는 진술이 아니다. a는 캐릭터·무드 파일을 옆에 놓고 비교하되 모델에는 아무것도 업로드하지 않는다.

| 컷 | 다섯 줄 기록 |
|---|---|
| s01 | 그대로: 빈 원경의 서사 기능.<br>새로: 넓은 분지와 지면 기복.<br>제외: 기존 협곡 전체·로봇·격자·프리비즈 자막.<br>슬롯 권한: M39 대기 / T44 재질.<br>합격 증거: 39·44와 명도 비교, K02가 들어갈 중경 공간. |
| s02 | 그대로: 멀리서 접근하는 실루엣·긴 빈 지면.<br>새로: K01 장소의 관측점 A.<br>제외: s02 평지·팝업 동작·원본 영상.<br>슬롯 권한: K01 장소 / C-F 외형 / M39 대기.<br>합격 증거: K04의 같은 전경 돌·능선, 먼 개체 점유율. |
| s03 | 그대로: 근접 관측점 B·첫 디딤의 인과.<br>새로: 요철 위 하중을 받는 오른앞발.<br>제외: s03 트롯·시트의 발밑 그림자·A의 전경 돌.<br>슬롯 권한: C-foot 발 형태 / C-R 몸통·연결 / M39 대기 / T44 재질.<br>합격 증거: 전경 발-돌 경계·다른 지지 높이·옆먼지와 접지 후 먼지. |
| s04 | 그대로: K02 카메라·전경·수평선.<br>새로: 조금 진전한 먼 대열.<br>제외: s04 격자 프레임·급격한 크기 확대.<br>슬롯 권한: K02 구도·장소 / C-F 외형 / M39 대기.<br>합격 증거: K02와 전경 표식 중첩, 가까워짐의 정도. |
| s05 | 그대로: 39의 내부 구도·빛.<br>새로: 없음, 원본 첫 프레임 캡처.<br>제외: 39 중간의 과도한 차체 가림·이전 프롬프트.<br>슬롯 권한: 생성 슬롯 없음, v3는 비교.<br>합격 증거: 원본 캡처의 접점·차체·통로 세 깊이. |
| s06 | 그대로: 넓은 대열이 통과하는 화면 기능.<br>새로: 가까운 험지 지지와 뒤의 반복 대열.<br>제외: 41의 평평해 보이는 보행면·지지 증거가 부족한 0.000초 캡처.<br>슬롯 권한: C-F 외형 / M39 대기 / T44 재질; 41은 사람 비교만.<br>합격 증거: 같은 근경 로봇의 두 지지 높이·작은 몸통 피치·s05~s11 규모 관계. |
| s07 | 그대로: 43의 낮은 후측면·반복 대열.<br>새로: 없음, 원본 0.500초 캡처.<br>제외: 파일명만 보고 첫발 장면으로 바꾸는 매핑.<br>슬롯 권한: 생성 슬롯 없음, C-B 비교.<br>합격 증거: v3 후면·근경 관절·바닥 접점. |
| s08 | 그대로: 44의 측면 구조·통로 원근.<br>새로: 없음, 원본 첫 프레임 캡처.<br>제외: 프리비즈 자막·옆면 좌우 반전.<br>슬롯 권한: 생성 슬롯 없음, C-R 비교.<br>합격 증거: 센서·몸통 패널·읽히는 지지와 먼 통로. |
| s09 | 그대로: 42의 가까운 통과와 낮은 시점.<br>새로: 없음, 원본 0.250초 캡처.<br>제외: 공중 네 발·잘못 붙인 발밑 매핑.<br>슬롯 권한: 생성 슬롯 없음, C-F/C-R 비교.<br>합격 증거: 스윙발과 지지발의 구분, K10으로 이어질 바닥. |
| s10 | 그대로: 발밑 앤트 관측 기능.<br>새로: 실제 단차·지지와 스윙의 높이.<br>제외: s10 전체 격자 화면·평지 발높이.<br>슬롯 권한: C-F 구조 / C-foot 발 / M39 대기 / T44 재질.<br>합격 증거: 같은 근경의 두 지면 높이·몸통 하단 공간. |
| s10b | 그대로: K10 지면·빛·진행축.<br>새로: 열린 통로 가장자리의 스치는 다리.<br>제외: s10b 전체 프리비즈·가려진 잘못된 접점.<br>슬롯 권한: K10 장소 / C-R 외형 / C-foot 발 / M39 대기.<br>합격 증거: K10과 지질 비교·돌을 넘는 스윙·남은 지지. |
| s11 | 그대로: 선회 중 규모를 읽히는 사선 기능.<br>새로: 충분한 대열과 지면 대응.<br>제외: 40의 성긴 배치·조기 탑뷰·글자 형상.<br>슬롯 권한: C-Q 외형 / M46 대기 / T44 재질.<br>합격 증거: 열린 통로 외의 연속 밀도·근경 접지. |
| s12 | 그대로: +X 진행과 R-A/L-A의 지속 관계.<br>새로: 맑은 접근 통로와 먼 유한 폭풍 띠.<br>제외: s12의 높은 시점·초반 전체 안개·원본 영상.<br>슬롯 권한: C-B 외형 / M39 대기 / T44 재질; K14는 사람 검토.<br>합격 증거: 빈 지면의 깊이·K13의 같은 R-A/L-A. |
| s13 | 그대로: 승인 K12의 장소·진행·R-A/L-A.<br>새로: 같은 띠 내부의 가시성 변화.<br>제외: s13 원본 격자·틀린 자세·새 진입.<br>슬롯 권한: K12 공간 / C-B 외형 / M39 색·산란.<br>합격 증거: 마지막 보이는 지면·앞 로봇·출구 방향. |
| s14 | 그대로: 중앙 일렬의 원근·진행축.<br>새로: v3 Go2·주변 대군·출구 지지와 감속 상태.<br>제외: 45/s14 전체 이미지·하나뿐인 열·다른 로봇.<br>슬롯 권한: C-B 외형 / M39 대기 / T44 재질; 조정 때 K13 공간.<br>합격 증거: K13 R-A/L-A와 K15b 최종 접점의 같은 지질·방향. |
| s15 | 그대로: K15b로 이어질 같은 오른앞발·오른쪽 시점.<br>새로: 최종 접지 직전의 지지 교대.<br>제외: s15 트롯·완료 정지·과도하게 긴 하강 포즈.<br>슬롯 권한: C-R 구조 / C-foot 발 / M39 대기 / T44 재질; K15b는 사람 검토.<br>합격 증거: K15b의 발·돌·머리 방향, 아직 닿지 않은 마지막 발. |
| s15b | 그대로: R-A 오른앞발과 주변의 같은 Go2.<br>새로: 험지 위 정지 지지와 낮은 잔먼지.<br>제외: s15b 원본 트롯·네 발 점프·시트의 평지 접지 그림자.<br>슬롯 권한: C-foot 발 / C-R 구조 / M39 대기 / T44 재질.<br>합격 증거: 발-돌 접촉·다른 지지 높이·안정된 몸통. |
| s16 | 그대로: 승인 후퇴의 구도 기능과 실제 소스 프레임.<br>새로: 후속 단계의 정지·험지 접지·일치 배치·룩.<br>제외: 걷는 상태를 정지의 정답으로 승인하기·생성 전체화면 교체.<br>슬롯 권한: 이미지 모델 슬롯 없음; 원본은 사람·합성의 구조 자료.<br>합격 증거: s1718 씬 배치와 같은 좌표계·경계 프레임·근경 접점. |
| s1718 | 그대로: 원본 글자 윤곽·개체 배치·엔딩 도달 크기.<br>새로: 구조를 보존하는 지면·빛·대기 처리.<br>제외: 자유 생성 글자·8192를 텍스트 요구만으로 보존했다는 주장.<br>슬롯 권한: 이미지 모델 슬롯 없음; 원본/마스크가 배치 권한.<br>합격 증거: 씬 개체 목록·같은 상승의 시작/끝·정본 SVG/엔딩 중첩. |

## 2. 무제한 이미지 생성의 실행 명세

### 모델·해상도와 UI 입력 순서

기본 13컷은 **Seedream 4.5 · 16:9 · 2K 목표 · Unlimited · 한 번에 1장**으로 만든다. 2K는 UI의 해상도 표기이며 정확히 2048×1152 파일이 나온다는 보장은 아니다. 내려받은 실제 픽셀 치수를 기록하고 16:9 여부를 확인한다. 승인본의 비교 캔버스는 1920×1080을 기준으로 삼되 원본은 보존한다. 참조 처리 중 근경 발을 늘이거나 종횡비를 왜곡하지 않는다.

**계정 권한의 근거는 2026-09-14 브리프의 실측**이다. 이 워커는 계정 화면을 직접 열지 않았다. 공식 모델 목록에서 Seedream 4.5의 16:9 및 다중 이미지 참조는 확인했다. 다만 공식 CLI 스키마는 웹 UI 위치·계정별 무제한 해상도를 증명하지 않는다. [Higgsfield 공식 모델 목록](https://github.com/higgsfield-ai/cli/blob/main/MODELS.md#seedream_v4_5--seedream-45)

공식 안내는 무제한을 웹 본체에서 사용하고 계정의 `Profile → Manage Account → Subscription → Active unlimited models`에서 실제 적용 범위를 확인하도록 한다. 2K를 목표로 하되 이 계정에서 그 조합의 비용이 0인지 생성 버튼에서 확인한다. 일반 프로모션 문서의 모델·기간을 이번 계정의 365일 권한에 덮어쓰지 않는다. [Higgsfield 무제한 이용 안내](https://higgsfield.ai/blog/new-unlimited-more-models)

1. Higgsfield 웹 본체의 **Image**로 들어가 모델 선택기에서 정확히 **Seedream 4.5**를 고른다. Video·Cinema Studio·Canvas·MCP·CLI로 생성하지 않는다. Seedance 2.5는 이번 정지 화면 모델이 아니다.
2. **Unlimited**를 켠다. 계정의 활성 모델 목록에 해당 모델이 있는지와 최종 버튼의 비용 **0 credits**를 확인한다. 2K가 유료로 바뀌면 0인 지원 설정으로 낮춘 후 실제 치수를 기록한다. 모든 조합이 유료이면 실행을 멈추고 그 화면 상태를 제작 담당자에게 보고한다. 추가 구매·유료 생성으로 자동 전환하지 않는다.
3. 참조 이미지 추가 영역에서 해당 컷의 **S1, S2… 순서대로** 준비된 깨끗한 이미지를 업로드한다. UI가 `Reference`, `Add image`, `+` 중 어떤 이름을 쓰는지는 현 화면을 따른다. 아래 S번호는 실제 UI의 업로드 순서를 뜻하는 문서 표기이며, 파일 경로나 `@Image1`을 글자로 적는 것만으로 업로드되지는 않는다. 영상 파일은 넣지 않는다.
4. 업로드 미리보기에서 순서와 내용을 눈으로 확인한다. 전체 캐릭터시트, 격자 바닥, 프리비즈 제목, 앵커의 불필요한 로봇이 남으면 되돌아가 참조를 정리한다. 역할 분리를 지원하지 않는 경우에도 아래 프롬프트의 첫 문장이 각 이미지 권한을 설명한다. 설명문 자체가 격자·틀린 포즈를 안전하게 제거해 준다고 간주하지 않는다.
5. 해당 컷의 **영문 전문**을 Prompt에 붙인다. 자동 프롬프트 확장·스타일 프리셋이 켜져 있으면 해제하거나 적용하지 않는다. 카메라 운동 프리셋을 선택하지 않는다. 아래 **공통 네거티브 + 컷별 네거티브**를 같은 입력 맨 끝에 붙인다. 별도 Negative prompt 필드가 실제로 있으면 그 필드에 두 부분을 넣어도 된다. 모든 모델에 그 필드가 있다고 가정하지 않는다.
6. 비율 **16:9**, 해상도 **2K 목표 중 무제한 지원값**, 수량 **1**을 선택한다. 동일 참조·설정으로 두 후보를 순차 생성한다. 모델명·해상도·비용을 마지막으로 읽고 Generate를 누른다. 한 장이 끝난 뒤 다음 한 장을 실행한다.
7. 결과를 확대해 해당 컷의 세 합격 조건, v3 외형, 앵커 색을 비교한다. 정지 화면에서는 접점·부유·관통·지지 자세를 판정하고, 미끄러짐·감속·동시성은 이후 영상 검수 항목으로 남긴다. 합격 후보만 K컷번호로 승인 관리한다. 실패한 이미지는 다른 컷의 참조에 넘기지 않는다.

한 컷의 형태 실패가 네 후보에서 반복되면 문장만 늘리며 무한 반복하지 않는다. 같은 Seedream 4.5에서 참조·구도·마스킹을 먼저 바꾼다. 복잡한 관계 지시가 계속 무너지면 브리프의 **GPT Image 무제한**을 대안으로 한 컷만 시험하고 동일 앵커로 재검수한다. 모델 이름을 임의로 GPT Image 2나 유료 Pro 계열로 바꾸지 않는다. 이것은 검증 전 대안이며, 모든 b 컷의 기본 선택은 Seedream 4.5다.

### 공통 네거티브 전문

아래를 각 컷 원고 끝에 그대로 붙인 뒤 그 컷의 추가 네거티브를 잇는다. 정본 Go2의 원래 표면 표식은 유지하되 새로운 타이틀·슬로건은 생성하지 않는다.

```text
Exclude: weapons, combat equipment, conquest, threatening attack poses, victory gestures, soldiers, laser beams, glowing eyes, neon circuits, luminous grids, fantasy armor, giant robot scale, animal paws, claws, extra or disconnected legs, merged robots, elastic chassis, altered sensor housings, floating support feet, feet penetrating stones, identical foot heights on uneven ground, a smooth parade road disguised by rocks at its edges, explosive dust, an opaque brown slab covering the subject, crushed black contact areas, excessive orange grading, blue science-fiction lighting, generated titles, invented brand marks, captions, watermarks, storyboard labels, split screens, collages, motion trails.
```

### s01 · 빈 땅

설정: Seedream 4.5, 16:9, 2K 목표. S1=M39, S2=T44. 캐릭터·프리비즈 없음.

```text
Create one photoreal cinematic still, not a collage. Reference image 1 provides only the warm sand-colored atmosphere and low-sun scattering. Reference image 2 provides only the granular sand, gravel and embedded stone material. Neither reference dictates a camera or a landform layout.

Establish a vast dry basin before any robots are visible. Look across a low rock shelf from approximately three to five meters above the ground, with the perspective of a 28 to 35 mm full-frame lens. Foreground worn rocks lead into traversable but genuinely uneven ground: embedded stones, shallow erosion grooves, loose gravel and low sand ridges continue through the middle distance. Keep a low distant ridge and a broad approach area available for a later formation. Avoid a dramatic deep canyon.

Use a single low oblique sun, long readable shadows and layered beige dust haze that becomes denser with distance. Dark brown-gray stone shadows retain texture. This world feels monumental, solemn and physically weighty through geological scale and light, with cool emotional restraint and precise observation. The subject is uncertain ground awaiting a foothold. Show no robot, text or science-fiction effects.
```

추가 네거티브:

```text
Exclude: visible robots or silhouettes, giant cliffs, bottomless valleys, buildings, roads, pristine flat sand, a second sun, decorative orange lines.
```

### s02 · 지평선의 작은 실루엣

설정: Seedream 4.5, 16:9, 2K 목표. S1=승인 K01, S2=C-F, S3=M39.

```text
Create one photoreal cinematic still. Reference image 1 establishes the approved basin, geology and light, not the new camera height. Reference image 2 supplies only the authentic white Unitree Go2 robot design. Reference image 3 supplies atmospheric color only.

Observe the same basin from a fixed distant viewpoint A, about 0.5 to 0.8 meters above the ground with a restrained 50 to 70 mm full-frame lens perspective. Leave a very broad stretch of empty uneven terrain between the camera and an advancing formation just below the distant ridge. The largest robot silhouettes should initially occupy only about 0.5 to 1.5 percent of image height. They must feel far away and already present, not suddenly arriving at the lens.

Place recognizable fixed foreground stones and a low ridge that can remain identical in shot 04. Sand-filled grooves, embedded rocks and gravel continue into the formation's route. The tiny bodies sit at subtly varied elevations following that terrain; do not enlarge them just to expose their feet. Individual contact physics will be inspected in closer shots.

Use the same low sun, muted warm beige haze, long subdued shadows and white highlights. Suggest awe and enormous scale through distance and repetition, with precise, calm, grounded certainty rather than threat or conquest. No typography.
```

추가 네거티브:

```text
Exclude: foreground robots, large hero robot, a formation filling the near ground, an empty perfectly level grid, spectacular storm at the lens, telephoto flattening that removes the empty distance.
```

### s03 · 첫 접지

설정: Seedream 4.5, 16:9, 2K 목표. S1=C-foot, S2=C-R, S3=M39, S4=T44.

```text
Create one photoreal cinematic still of the first visible foothold, captured immediately after a right forefoot has contacted the terrain and begun accepting load. Reference image 1 supplies foot and lower-leg shape only, never its original pose or shadow. Reference image 2 supplies authentic Go2 chassis and limb connections only. Reference image 3 supplies atmospheric color; reference image 4 supplies ground material.

Place a locked observational camera eight to twelve centimeters above the ground, beside the distant leading row at viewpoint B, with a restrained 28 to 35 mm full-frame lens perspective. The robot travels left to right across the frame. Frame mostly lower legs and terrain, with enough connected structure to understand support. Use actual compact Go2 scale.

The black rounded right forefoot is visibly seated on the top of a low embedded stone. Another supporting foot meets a lower patch of granular sand. Their leg angles and the small visible chassis pitch respond to these different heights. The planted foot has a continuous, precise contact edge, without a hovering gap or rock penetration. Weight is transferring while the body continues its stride, not settling into a final halt.

A thin lateral veil of sand comes from outside the frame. A much smaller fresh disturbance lies directly beside the already contacted foot. Neither hides the contact. Use a low warm sun, beige suspended dust, white rigid panels and brown-gray stone shadows. Make a modest physical contact feel decisive and solemn, without a giant stomp, threat or fantasy spectacle.
```

추가 네거티브:

```text
Exclude: airborne principal foot, suspended freeze before landing, dust erupting below a foot before contact, a whole-body landing, four airborne feet, a fully stopped formation, a close copy of shot 02's foreground landmark.
```

### s04 · 같은 관측점으로 복귀

설정: Seedream 4.5, 16:9, 2K 목표. S1=승인 K02, S2=C-F, S3=M39.

```text
Create one photoreal cinematic still of a slightly later moment at exactly the distant viewpoint in reference image 1. Preserve its camera, lens perspective, horizon, foreground stones, terrain relief and low-sun direction. Reference image 2 supplies Go2 identity only. Reference image 3 supplies matching atmospheric color only.

Advance the same distant formation a modest distance within the same basin. The robots become only somewhat easier to recognize: faint white chassis and dark sensor accents emerge through the haze, while the formation remains remote behind a large stretch of empty ground. This must not resemble a lens zoom or an arrival at the close foot-insert viewpoint.

Continue the uneven stone, gravel, sand grooves and low ridges all the way to the formation. Distant body levels follow those small terrain variations. Keep granular foreground detail sharp enough to prove that the observation point has not changed. Use the same warm sand-colored haze and long subdued shadows, with controlled white highlights and deep textured stone shadows. Convey persistent progress, solemn scale and mechanical precision without aggression, weapons or luminous technology. Show no text.
```

추가 네거티브:

```text
Exclude: changed foreground stones, changed horizon, a new lens angle, abrupt size increase, robots at the near-camera foot-insert location, additional suns, a completely clear dust-free formation.
```

### s06 · 험지 위로 통과하는 넓은 대열

설정: Seedream 4.5, 16:9, 2K 목표. S1=C-F, S2=M39, S3=T44. 41번 원본은 사람이 화면 기능만 비교하며 업로드하지 않는다.

```text
Create one photoreal cinematic still of a broad Go2 formation progressing through uneven terrain. Reference image 1 supplies only the authentic compact white Go2 design. Reference image 2 supplies only low-sun beige atmospheric color, and reference image 3 supplies only sand, gravel and embedded stone material. No old formation image is attached.

Use a low oblique viewpoint roughly 0.4 to 0.6 meters above the ground and a restrained 35 to 50 mm full-frame lens perspective. The broad formation is seen from near the front rather than a strict side profile. Let a few nearer robots occupy approximately ten to fifteen percent of image height, while many smaller rows continue behind them. This remains a broad passage view, not a giant hero close-up or the film's final aerial scale reveal.

Make low bedrock lips and sand-filled grooves run through the actual walking surface. On one clearly readable near robot, one supporting foot is seated on a raised embedded stone and another supports lower granular ground; their different joint angles and slight rigid-chassis pitch correspond to those real heights. A swinging foot clears a nearby protrusion. Keep every limb connected and separate the near contact edges from the background.

Use one low warm sun, long textured shadows, thin ground-level dust and distance-dependent beige haze. White bodies retain neutral highlights and modest dust deposits. Express majestic repetition, steady progress and physical weight without threatening attack, conquest, weapons or glowing technology. No text or overlays.
```

추가 네거티브:

```text
Exclude: a perfectly level walking strip with rocks only at its edges, tiny unreadable near contacts, identical foot heights despite visible relief, a giant leader, empty gaps replacing the broad formation, a fully top-down view, a military charge.
```

### s10 · 발밑의 다른 높이

설정: Seedream 4.5, 16:9, 2K 목표. S1=C-F, S2=C-foot, S3=M39, S4=T44.

```text
Create one photoreal cinematic still from an ant-height observation point at the safe edge of an open path between Go2 legs. Reference image 1 supplies the authentic robot structure, reference image 2 the foot shape, reference image 3 atmospheric color, and reference image 4 ground material. None supplies a flat-ground pose.

Use a camera five to eight centimeters above the surface with a 24 to 28 mm full-frame perspective. Look beneath the nearest compact white Go2 without passing through its chassis. Show one supporting black foot fixed on a low bedrock lip while another leg lifts its foot over a protruding stone toward a lower sand-filled groove. Keep at least one additional support readable. The small rigid chassis pitch and different joint angles must agree with the actual terrain heights.

Use worn embedded rock, loose gravel and coarse sand on the walking surface, not just beside it. A few low grains drift near the ground; no impact explosion. Similar robots continue farther away at smaller scale. Use a low warm oblique sun, soft white body highlights, layered beige haze and textured brown-gray shadows. Let real mechanical support carry the scene's weight and grandeur. This is locomotion continuing across uncertain terrain, not a staged stomp or threatening machine display.
```

추가 네거티브:

```text
Exclude: camera inside a body or leg, fisheye giant feet, all feet on the same ground plane, another first-foot ceremony, synchronized jumping, a stopped hero pose, unreadable dark underbody.
```

### s10b · 돌을 넘는 발의 스침

설정: Seedream 4.5, 16:9, 2K 목표. S1=승인 K10, S2=C-R, S3=C-foot, S4=M39.

```text
Create one photoreal cinematic still of a close leg passing the camera while the Go2 keeps walking. Reference image 1 supplies the approved terrain, travel direction, light and robot scale from shot 10, not a mandatory identical framing. Reference images 2 and 3 supply authentic right-side structure and foot shape only. Reference image 4 supplies atmospheric color only.

Move the viewpoint slightly to the safe side of the same open route, eight to twelve centimeters above the ground with a 28 to 35 mm full-frame lens perspective. A near right-side lower leg occupies only the outer edge of the image. Its swinging black foot clears a small protruding stone. A distinct connected supporting leg remains planted in the lower sand beside it, with a readable contact edge. Preserve mechanical linkage and a slight terrain-induced body pitch.

Keep the center open enough to see receding Go2 rows and the granular uneven surface. Separate the near moving limb from the distant bodies; do not create a wall of merged legs. Use restrained ground-level dust, a low warm sun, beige haze, white rigid panels and textured dark stones. Show tactile proximity and immense repetition with calm precision and physical weight, without collision, aggression or fantasy effects.
```

추가 네거티브:

```text
Exclude: central corridor fully blocked by a leg, unconnected floating foot, the near limb covering every support, new geology, reversed robot heading, an explosive dust wipe.
```

### s11 · 밀도 있는 선회

설정: Seedream 4.5, 16:9, 2K 목표. S1=C-Q, S2=M46, S3=T44.

```text
Create one photoreal cinematic still from an oblique point during an orbit around a dense Go2 formation. Reference image 1 supplies authentic Go2 identity only. Reference image 2 supplies distant atmospheric depth and color only, never the formation layout. Reference image 3 supplies rough ground material.

Use a camera approximately one to two meters high with a 28 to 35 mm full-frame perspective. Keep a strong view into repeated rows without reaching a top-down aerial view. Preserve one deliberate navigable corridor. Elsewhere, continuous rows extend from the foreground into the haze, with enough individual spacing to prevent body or leg collisions. Do not leave large accidental empty fields between small isolated groups.

The walking surface contains embedded stones, gravel, sand ridges and shallow grooves. In the nearest readable robots, feet support different terrain heights, one swinging foot clears a rock, and rigid bodies show small corresponding pitch differences. Farther robots lose contrast naturally in warm beige dust. Low sunlight creates long shadows and controlled white highlights over dark textured stone. The image is majestic, monumental and weighty, presenting repeated executions of one locomotion policy, without conquest, menace, weaponry or glowing technology. Reveal no letter shape or text.
```

추가 네거티브:

```text
Exclude: sparse groups, overlapping bodies, a top-down logo view, perfectly identical airborne poses, an unnaturally smooth parade surface, a giant central leader.
```

### s12 · 아직 멀리 있는 폭풍

설정: Seedream 4.5, 16:9, 2K 목표. S1=C-B, S2=M39, S3=T44. 먼저 정한 K14는 옆 비교만 하며 완성 출구판을 시작 상태로 잠그지 않는다.

```text
Create one photoreal cinematic still of the clear approach to a finite projecting band of a larger dust storm. Reference image 1 supplies rear-view Go2 identity only. Reference image 2 supplies warm sand-colored atmospheric light only. Reference image 3 supplies rough sand and stone material.

Place the camera at the upper-back height of an actual compact Go2, approximately 0.45 to 0.65 meters, with a 35 mm full-frame lens perspective. The camera looks along positive X, the same direction as the robots travel, through an open corridor between rows. Show backs and rear three-quarter surfaces. A designated lead robot R-A remains ahead slightly right of center. A low embedded rock L-A marks the left edge of this corridor. Never label them in the image.

Keep the air directly at the lens clear and show a substantial readable stretch of uneven ground before the distant dust band. Near robots plant feet on different rock and sand heights with matching joint flexion and slight rigid-body pitch. The band belongs to a larger layered dust body, not a flat opaque wall. Wind has a main component toward the camera and a slight lateral component.

Use a low warm sun from the forward-left side, beige haze, textured brown-gray shadows and softly reflecting white bodies. Convey awe and determined physical progress through uncertain ground, without threat, warfare or luminous science-fiction effects.
```

추가 네거티브:

```text
Exclude: fog already filling the lens foreground, tall human-height or aerial camera, robots facing the camera, a featureless expanding wall, a storm covering the entire ground, a new sun on the opposite side.
```

### s13 · 폭풍 안의 보이는 접점

설정: Seedream 4.5, 16:9, 2K 목표. S1=승인 K12, S2=C-B, S3=M39.

```text
Create one photoreal cinematic still of a later moment inside the same finite dust band shown in reference image 1. That image is the authority for corridor geometry, camera height and lens perspective, robot heading, lead robot R-A and landmark L-A. Reference image 2 supplies Go2 identity only; reference image 3 supplies matching atmospheric color. Advance through the same world without recreating the approach.

The camera still looks along the robots' forward travel direction at Go2 upper-back height. R-A remains ahead, never behind the camera. Near backs and shoulders frame a safe open corridor. Capture a brief clear gap between moving dust wisps: the left low rock, a patch of the same granular ground, one firmly planted foot on a raised stone and another foot clearing uneven ground are visible together. Body pitch and leg angles agree with those local heights.

Separate nearby dusty filaments, a middle veil and the distant mass. Maintain the established wind and the same forward-left low sunlight, now scattered through beige dust. The far exit is becoming faintly readable, but there is no second storm wall. White panels remain recognizable under fine deposited dust. Make the continued support feel heroic in compositional strength and monumental in scale, yet precise, solemn and non-aggressive. No weapon, luminous technology or text.
```

추가 네거티브:

```text
Exclude: another approach opening, a new corridor, a different lead robot, front-facing hero pose, a solid brown screen, invisible terrain for the whole image, camera penetration through a chassis, a clean newly replaced robot.
```

### s14 · 일렬과 다음 지지의 준비

설정: Seedream 4.5, 16:9, 2K 목표. 최초 S1=C-B, S2=M39, S3=T44. K13 승인 후 연속성 조정 때만 S4=K13을 추가한다. 아래 마지막 문단은 S4를 실제 첨부한 조정 시에만 함께 붙인다.

```text
Create one photoreal cinematic still of authentic white Unitree Go2 robots emerging from a finite dust band into a controlled braking approach. Reference image 1 supplies rear-view Go2 identity only. Reference image 2 supplies low-sun beige atmospheric light. Reference image 3 supplies rough ground material. Do not import any old single-file robot image.

Look forward along the same open corridor at roughly Go2 back height to one meter, with a 35 to 40 mm full-frame lens perspective. One dominant file of robots stretches far ahead and clearly reads as single-file marching. Include quieter parallel supporting rows at the sides so that the visible world remains part of a much larger formation. R-A stays ahead slightly right of center; the low rock L-A stays at the left corridor edge.

The lead robot is still progressing with shortened stride and an earlier supporting foot accepting weight, before its final right-forefoot braking swing. Show different support heights on low embedded rocks and sand grooves, corresponding joint angles and a small controlled body pitch. Keep low dust deposits on its feet and lower chassis. The crossed band leaves thin wisps at the sides and behind the camera, not a new wall straight ahead.

Maintain one forward-left low sun, warm beige haze, softly reflecting white panels and textured dark rocks. The mood is majestic, deliberate and secure, expressing preparation for a foothold rather than defeat, exhaustion, conquest or military triumph. No generated text.
```

S4를 넣은 조정 시 추가:

```text
Reference image 4 is the approved earlier view inside the same band. Preserve its corridor, R-A, L-A, heading, camera-side relationship and light in this later exit state. Change visibility and support phase, not the location or robot identity.
```

추가 네거티브:

```text
Exclude: the entire formation reduced to one isolated file, a front-facing replacement robot, a completed final stop, an already landed final right forefoot, damage, sagging exhaustion, a fresh storm wall ahead.
```

### s15 · 마지막 발이 닿기 전

설정: Seedream 4.5, 16:9, 2K 목표. S1=C-R, S2=C-foot, S3=M39, S4=T44. 승인 K15b는 먼저 옆에 놓고 지면·접점 위치를 역설계한다. 프롬프트로 같은 돌을 보장할 수 없으면 마지막 문단의 정합 검수를 통과할 때까지 선택하지 않는다.

```text
Create one photoreal cinematic still of the last support transfer before a Go2 formation finishes stopping. Reference image 1 supplies authentic right-side Go2 structure. Reference image 2 supplies right-forefoot shape only. Reference image 3 supplies atmospheric color, and reference image 4 rough sand and stone material. None supplies the braking pose.

Use a low right-side observation point, approximately fifteen to twenty-five centimeters above the ground with a 35 to 50 mm full-frame lens perspective. The lead robot faces screen right. Include enough head direction, connected chassis, legs and fixed terrain to make the orientation unambiguous. Other supporting feet remain planted on slightly different heights of sand and embedded rock. The designated right forefoot has only just begun its short final swing toward a low embedded stone; it has not yet made the final contact.

Keep its rigid body nearly level with a small physically plausible pitch from the uneven support heights. Show nearby robots completing their own necessary support transfers, without a collective jump. Thin residual dust lies near the ground after the storm. No new dust erupts at the upcoming contact point.

Use the same low warm sunlight, beige air, dusty white lower panels and textured dark rocks. Convey converging, deliberate support with solemn collective weight and readiness, without attack, triumph or collapse. This is a single moment, not a sequence or a diagram.
```

추가 네거티브:

```text
Exclude: final forefoot already planted, four-foot jump, all robots fully airborne, a long dramatic airborne reach, repeated stomping, obscured head direction, dust bursting from the future contact point, a completely finished stop.
```

K15b와 같은 돌·발·지질을 재현하지 못한 경우에는 새로운 K15를 승인하지 않는다. 승인 K15b의 **몸통·발 외형과 지면만 분리한 참조**를 S1·S4 대신 넣되 완료 정지 자세를 통째로 입력하지 않는다. 분리 작업에서 같은 접점 위치를 보존할 수 없으면 생성보다 지면판 위 제어된 포즈 합성으로 해결한다. 이는 동일성을 확보하기 위한 대안이며 첫 프롬프트가 그 정합을 보장한다는 뜻이 아니다.

### s15b · 한 번 디디고 안정된 발

설정: Seedream 4.5, 16:9, 2K 목표. S1=C-foot, S2=C-R, S3=M39, S4=T44.

```text
Create one photoreal cinematic still of the exact secure footing after the formation's final braking contact has accepted load. Reference image 1 supplies authentic right-forefoot and lower-leg shape only, not its original ground gap or shadow. Reference image 2 supplies the authentic connected Go2 body and right-side structure. Reference image 3 supplies atmospheric light and color, and reference image 4 rough terrain material.

Place a steady camera eight to fifteen centimeters above the ground on the robot's right side, with a 35 to 50 mm full-frame perspective. The robot faces screen right. Its black rounded right forefoot is firmly seated on a low embedded stone. Other feet support lower sand and gravel at different real elevations. Show a continuous visible contact edge, appropriate joint flexion and a rigid chassis that has settled with only a small terrain-related pitch.

Behind this close contact, two or three nearby Go2 robots have completed their necessary supports, while more settled rows recede into haze. They have not jumped or dropped all four feet together. A small low residue of dust spreads beside already grounded feet, leaving their shapes and contact shadows readable. The implied motion is now over; the formation is stable and ready for another step later.

Use a low warm sun, beige haze, textured brown-gray stone shadows, softly reflecting white panels and dust on the lower bodies. Make this collective stillness monumental, precise and physically weighty. It means finding a secure foothold, not conquest, threat, defeat, damage or an explosive stomp. No typography.
```

추가 네거티브:

```text
Exclude: principal foot still descending, continuing trot, lifted supporting feet, a jump landing, four synchronized airborne legs, a kneeling or broken robot, exaggerated body recoil, explosive contact cloud, terrain covered by a smooth flat floor.
```

## 3. 생성 순서·세션 규모·되돌림

제작 설계 v1.2 §G의 순서인 **결말 구조 확인 → 정체성과 룩 → 첫발·마지막 발 → 정지 앞부분 → 폭풍 → 규모 → 연결 컷**을 따른다. 이번에는 영상 테스트 대신 정지판을 선별한다. 아래 수량은 비용이나 성공률 실측이 아닌 탐색 예산이다.

| 순서·세션 | 그 세션에서 할 일 | 신규 이미지 생성 수 | 판정 후 진행 또는 되돌림 |
|---|---|---:|---|
| 사전 점검 | s16 시작·끝, s1718 시작·중간·끝, s19 참조와 실제 12초 엔딩 구별. v3·무드 앵커 세 개와 참조 분리판 준비. s05·s07~s09는 각각 표에 지정한 원본 시점의 캡처 네 장을 추출·확대 검수. | 0 | 결말 자료가 아직 없으면 c는 미승인으로 표시하고 독립적인 s03·s15b 작업을 시작할 수 있다. |
| 세션 1 · 접점 | s03 두 후보, s15b 두 후보. 순차 실행하며 총 네 장 비교. 두 컷에서 같은 흰 재질·검은 발·자갈 크기가 맞는지 먼저 본다. | 4 | 하나씩 통과하면 다음. 둘 다 외형이 틀리면 캐릭터 마스크로, 둘 다 지형이 평평하면 T44와 접점 정의로 돌아간다. |
| 세션 2 · 정지의 앞 | 승인 K15b에서 접점·방향을 역으로 정해 s15 두 후보, s14 출구 구도 두 후보. s14~15b의 R-A·주변 열·통로·최종 접점을 s1718의 같은 구역에 대응시켜 s16까지 일치해야 승인한다. 씬 자료 전에는 잠정판으로 둔다. | 4 | K15가 이미 완전 정지이면 사건 시점 수정. K14가 외딴 한 줄이면 보조열과 대군 관계 수정. |
| 세션 3 · 폭풍의 인과 | K14 출구 구도를 제작자가 옆에 놓고 s12 두 후보를 먼저 판정. 통과한 K12만 입력해 s13 두 후보. K13을 실제 입력한 s14 연속성 수정은 필요할 때만 추가한다. | 기본 4 | 폭풍이 다른 장소가 되면 K12로 돌아간다. K14 재조정이 필요하면 별도 후보로 세어 기본 수량에 숨기지 않는다. |
| 세션 4 · 규모와 결말 관문 | s11 두 후보. 이와 함께 원본 씬 담당자가 c 두 컷의 정확한 배치·정지·험지 지지·카메라 연결을 확인한다. | 기본 2 | 정본 배치와 연결이 틀리면 군집 구조 작업으로 복귀. 새 AI 이미지의 멋진 대군을 대체 정답으로 쓰지 않는다. |
| 세션 5 · 오프닝 연결 | 룩이 정해진 뒤 s01 두 후보, 통과 K01로 s02 두 후보, 통과 K02로 s04 두 후보. | 6 | K02·K04를 겹쳐 전경 돌·수평선·크기 변화를 확인. 다르면 K02로 복귀. K03은 다른 관측점이므로 전경 돌까지 억지로 같게 하지 않는다. |
| 세션 6 · 발밑 연결 | s06 두 후보, s10 두 후보, 승인 K10으로 s10b 두 후보. 기존 s05·s07~s09 캡처와 함께 연결감을 다시 본다. | 6 | 첫발과 발밑이 같은 사건처럼 보이면 카메라 위치·지지 위상 조정. 캡처가 A 조건을 못 채우면 해당 컷의 경로를 a에서 b로 변경 기록한다. |

기본 탐색은 **13개의 b 컷 × 2후보 = 26장**, 세션별 합계는 4+4+4+2+6+6=26장이다. 26장 전부를 한꺼번에 생성하지 않는다. 최종 라인에는 각 컷 한 장만 남겨 **a 4장 + b 13장 + c 2장 = 19장**이다. c는 구조 확인 단계의 자리표시이며 최종 룩 합격 수에 더하지 않는다. 추가 로케이션 시트, c의 룩 시험, a의 재생성, s14 재조정은 26장 기본 예산 밖이며 필요 이유와 장수를 별도로 센다.

한 장씩 생성하고 **두 장마다 판정**, 같은 컷에서 같은 구조 실패가 **네 장**이면 참조나 제작 방식을 바꾼다. 높은 난도의 s03·s15b·s12·s13은 구조를 고친 후 최대 네 장을 더 시험하는 작은 묶음으로 운영한다. 기존 영상 설계의 20~40테이크를 정지판 전 컷에 기계적으로 적용하지 않는다. 생성 시간은 실측하지 않았으므로 ‘몇 분이면 19장 완료’라고 약속하지 않는다.

최종 감독 검토에서는 오프닝 02·03·04, 폭풍 12·13·14, 정지 15·15b, 규모 16·1718의 관계를 순서대로 본다. 대표 한 장은 화면의 목표를 승인하는 자료이며 다음 단계의 운동 승인을 대신하지 않는다. 영상 생성으로 넘어갈 때에는 s03의 빈 지면과 사전 먼지, s15b의 짧은 하강과 접지 뒤 홀드, s12~13의 한 번의 진입과 출구, s16~1718의 실제 경계 핸들을 추가로 확보한다.

## 4. 감독 추가 지시 D·E·F

### D. 웅장함과 금지 범위의 해석

**웅장함·장엄함·압도감·스케일·무게는 이 영상이 달성해야 할 목표이며 금지하지 않는다.** ‘군사적 위압·승전·무기·과장 SF 금지’는 대군의 수와 대형 자체를 줄이라는 뜻이 아니라, 그 규모가 관객을 위협하거나 적을 정복하는 장면, 승리를 과시하는 제스처, 무기·전투 장비, 발광 눈·레이저·네온 회로·가상 갑옷으로 의미를 바꾸지 말라는 뜻으로 확정한다. 히어로 컷도 낮은 시점과 빛·지지의 명료함으로 힘을 보여줄 수 있다. 수천 대의 질서와 폭풍을 지난 무게는 살리되, 발이 실제 지면을 지지하는 정확함이 감정을 이끌게 한다. 프롬프트의 ‘monumental’, ‘majestic’, ‘solemn’, ‘weighty’는 허용하고 ‘threatening’, ‘conquest’, ‘victory’, 무기·발광 SF는 제외한다.

### E. 프리비즈를 어디에 주고 어디에 주지 않는가

**현재 주어진 프리비즈 전체 프레임을 이미지 모델에 직접 업로드하는 컷은 0개다.** 구도 참조가 필요하면 사람이 높이·시선·점유율을 읽어 원고에 옮긴다. c는 프리비즈를 감독의 보드와 제어 가능한 합성 작업에 주는 경우다. 이를 이미지 생성 모델에 주는 경우와 구별한다.

| 컷 | 제작자에게 보일 프리비즈 | AI 이미지 입력 | 제외할 이유·대체 정보 |
|---|---|---|---|
| s01 | s01_0~2, 원경의 기능만 | 없음 | 깊은 계곡 형상을 필수로 만들지 않고 새 분지를 원고로 정의. |
| s02·s04 | 각 _0~2, 먼 거리·같은 원경 관계 | 없음 | 평지 격자·빈 하늘·잘못된 등장 시점을 막고 K02로 카메라 공유. |
| s03 | s03_0~2, 낮은 카메라의 인상만 | 없음 | 트롯·평지 지지·발밑 여백이 새 첫발에 섞임. C-foot/C-R·T44로 재구성. |
| s05·s07~s09 | 각 _0~2로 확정 매핑만 대조 | 없음 | 원본 MP4에서 자막 없는 캡처. 중복 참조 불필요. |
| s06 | s06_0~2와 41 원본은 넓은 대열의 기능 비교만 | 없음 | 기존 캡처의 지형 반응이 불충분해 C-F·M39·T44로 새 대표판 구성. |
| s10·s10b | 각 _0~2, 발밑·스침 기능 | 없음 | 평지 발 높이와 격자, 원치 않는 지지 자세가 따라옴. 신규 지면 대응을 명세. |
| s11 | s11_0~2, 사선 관측 기능 | 없음 | 성긴 배치를 승인하지 않음. 열린 통로와 충분한 열을 새로 지정. |
| s12·s13 | 각 _0~2, 현재 안과 새 설계의 차이 확인 | 없음 | 높이·시야·폭풍 인과가 다름. 동일 K12를 다음 컷 공간 권한으로 사용. |
| s14 | s14_0~2, 일렬의 원근 인상만 | 없음 | 한 줄 전체와 외형을 그대로 잠그지 않음. 중앙 주도열·보조열·v3 후면으로 재구성. |
| s15·s15b | 각 _0~2, 기존 안의 문제 확인 | 없음 | 이 프레임은 요청한 정지와 발 타이트를 보증하지 않음. 새 오른측 접점과 지지 상태로 대체. |
| s16 | s16_0~2, 원본 카메라·밀도 자료 | 없음. c 구조판은 사람·합성에만 전달 | 걷는 위상과 평지 지형을 잠그지 않음. 정지군집·지지와 s1718 연결은 별도 원본 작업. |
| s1718 | s1718_0~2, 글자 형태·도달 크기 자료 | 없음. c 구조판은 사람·합성에만 전달 | 정확한 수·글자·좌표는 원본의 권한. 8192를 텍스트 프롬프트로 맞추려 하지 않음. |
| s19 | s19_0~2는 비교용. 실제 12초 마스터는 별도 확인 | 없음 | 기존 엔딩 불변. 제공 컨택트시트에는 s19가 3.97초로 표시돼 있어 12초 마스터 자체로 간주하지 않음. |

새로 정리한 구도판을 나중에 AI에 넣는다면 그것은 이 프리비즈 원본이 아니다. 격자·잘못된 로봇·포즈·자막을 제거하고 승인한 구성 정보만 남긴 새 자산이며, 파일·버전·권한을 다시 기록해야 한다. 이번 설계에는 그런 정리판이 이미 존재한다고 적지 않았다.

### c 두 컷을 완성 룩으로 바꾸는 조건

1. s1718 원본 씬에서 **개체 목록·XY 배치·향하는 방향·글자 윤곽**을 인계받는다. 8192는 브리프와 프레임 제목의 제공값이다. 정지 이미지를 세어 확인한 수치가 아니다.
2. **s14~s15b의 R-A·주변 열·통로·최종 접점을 s1718의 같은 구역에 대응시키고 s16까지 일치해야 승인한다.** 자료를 확보하기 전 s14·s15·s15b는 동작·룩의 잠정판이며 군집 연결이 확정된 판이 아니다. 정지 직전의 진행도 그 최종 접점으로 이어져야 한다. 이어서 s16이 최종 글자 대형의 어느 일부를 보는지 정한다. 이미 긴 획 내부를 보는 카메라라면 그 사실을 씬 자료로 확인한다. 별도의 직사각 대형이면 s16의 관측 구역과 대열을 같은 최종 배치에서 구성한다. 화면에 보이지 않는 곳에서 대열이 재배열됐다고 설정하지 않는다.
3. **평지 위 발을 고정한 채 바위만 덧칠하면 험지 적응이 아니다.** 정확한 XY 글자 배치는 보존하되 실제 지면 기복을 만들고 제어 가능한 렌더에서 개체의 높이·다리 관절·접촉 위치를 맞춘다. 필요하면 지형을 지지 가능한 범위로 낮춘다. 바위 위를 관통하는 발이나 모든 발의 동일 높이를 ‘원본 보존’이라는 이유로 통과시키지 않는다. 이렇게 변하는 Z·다리 자세와 보존되는 XY·글자·수량을 구별한다.
4. 같은 카메라 경로의 정지군집·지형·그림자·깊이·개체 마스크를 얻는다. 컷 경계 앞뒤 최소 0.2초와 기존 핸들을 확인해 위치, 피치, 스케일, 바닥 흐름이 이어지는지 검사한다. s16_2와 s1718_0의 정지 화면 비교만으로 ‘카메라가 불연속’이라고 단정하지도, ‘매끄럽다’고 승인하지도 않는다.
5. 룩은 앵커 46의 거리별 대비 감소, 39의 대기색, 44의 돌·모래 물성을 같은 원본 위에 반영한다. 하늘·지면 재질용 AI 이미지는 위 무제한 모델로만 만들 수 있지만, 개체·글자까지 포함한 자유 생성 전체 화면은 완성판으로 사용하지 않는다. 이 보조 생성은 현재 b 13컷의 수량에 포함되지 않는다.
6. s1718의 대표판은 전체 형상을 읽는 `_1`, 엔딩 크기 비교는 `_2`를 쓴다. 원본 라벨은 감독 보드에서만 보이고 최종 프레임에는 들어가지 않는다. 합성 완료 후 획의 빈 공간, 글자의 화면 점유 크기, 정본 SVG와 실제 엔딩의 위치·크기·폰트를 중첩 비교한다. 단순 명암차 허용과 배치·형태 변경 금지를 구별한다.

이 단계까지 끝나야 c 두 장을 최종 룩으로 교체하고 **19컷 전체의 톤과 험지 조건 통과**를 선언한다. 현재는 두 구조판이 요구의 예외라는 뜻이 아니라, 브리프가 허용한 톤 변환 전 준비 단계라는 뜻이다. 이미지 모델만으로 끝낼 수 없는 정확한 배치 작업을 가짜 합격으로 덮지 않는다.

### F. 선택안 하나: ‘다음 디딤’

기본 납품은 기존 s19를 그대로 사용한다. 아래는 **감독이 마지막에 선택할 별도 안**이며 채택되지 않으면 기존 엔딩에 아무 변화도 없다. 룩소의 익살이나 특정 동작을 복제하는 대신, ‘글자가 발 디딜 곳’이라는 착상을 Go2의 작고 정확한 옮겨 디딤과 낮은 도약 한 번으로 바꾼다. 본편의 대군은 멈춘 채 두고, 엔딩의 작은 Go2만 별도 그래픽 캐릭터로 상호작용한다.

카메라는 기존 엔딩과 같은 고정 정면이다. FOOTHOLD는 정본 SVG를 그대로 렌더하는 보호 레이어다. 로고의 디자인·폰트·크기·자간·위치·기존 변환 키프레임·텍스트·12초 길이·시퀀스·기존 음향을 바꾸지 않는다. Go2와 최소한의 접촉 음영만 별도 레이어로 얹는다. 로고가 찌그러지거나 튀어 오르거나 한 글자가 Go2로 대체되지 않는다. 아래 시간은 **12초 안의 연출 배치 제안**이며 원본 이벤트 시각을 측정한 값이 아니다.

| 12초 내 제안 창 | 비트·Go2 동작 | 카메라·보호 조건 |
|---|---|---|
| 0.0~2.0초 | 기존 찢김과 워드마크 등장. Go2는 없음. | 기존 애니메이션 그대로. 첫 로고 인지를 가리지 않는다. |
| 2.0~2.5초 | 워드마크가 정착해 읽힌 뒤, F 상단 높이에 작은 Go2가 화면 위 여백에서 낮게 들어와 정확히 디딘다. | Go2 몸통은 글자 윗공간에, 발끝만 상단 획에 접한다. 로고 캔버스와 카메라 고정. |
| 2.5~3.3초 | F 위에서 한 번 무게를 옮기고 바로 옆 첫 O의 윗면으로 낮은 도약 한 번. 발을 모아 찍지 않고 앞 지지와 뒤 지지를 짧게 나눠 받는다. | 도약은 글자 높이보다 낮게. 바운스·스쿼시·웃는 얼굴·꼬리 흔들기 없음. |
| 3.3~3.8초 | O의 상단에서 짧게 안정. 몸통은 곧게, 다음 디딤 방향만 본다. | O의 내부 공간이나 F/O 형태를 가리지 않는다. 재질은 본편의 흰 Go2·검은 센서, 배경은 기존 다크. |
| 3.8~4.2초 | 워드마크와 상호작용을 마치고 상부 여백으로 짧게 벗어난다. 발 디딤의 방향을 기존 하얀 선·FIND THE NEXT STEP으로 인계한다. | 기존 하얀 선 등장·태그라인 전환보다 먼저 Go2가 완전히 빠져야 한다. 기존 텍스트를 움직여 공간을 만들지 않는다. |
| 4.2~12.0초 | 기존 하얀 선, FIND THE NEXT STEP, ‘불확실한 지형에서도, 다음 걸음을 이어갑니다’, 스택 락업을 원래 순서와 시간대로 재생. Go2는 다시 등장하지 않는다. | 문구의 읽기 시간과 마지막 락업 홀드 불변. 로고·심볼·영문 서브라인 재생성 금지. |

**적용 전제:** 실제 12초 마스터에서 워드마크가 읽힌 뒤부터 하얀 선·태그라인이 시작되기 전까지 위 2.2초 상호작용 창이 있어야 한다. 실제 창이 위 제안 시각과 다르면 Go2 레이어의 시작 시각만 그 빈 창에 맞춘다. 창이 부족하거나 로고 읽기 시간을 침범하면 이 선택안 전체를 채택하지 않는다. 로고·슬로건·엔딩을 리타이밍해 공간을 만들지 않는다. 제공 s19 섬네일만으로 이 전제가 충족됐다고 보고하지 않는다.

로고 훼손 방지는 **SVG 원본 불변 + 보호 레이어 + Go2 발끝 외 획 가림 금지 + 전환 전 완전 퇴장**으로 확인한다. 모델에 FOOTHOLD와 Go2를 함께 생성시키지 않는다. 귀여움이 앞서는 위험은 작은 몸집의 마스코트 쇼, 연속 통통 뛰기, 과장된 고개짓, 관객을 향한 반응, 장난스러운 새 효과음을 넣지 않는 것으로 줄인다. 작은 도약 한 번에도 실제 기계 관절과 짧은 안정 지지가 보여야 하며, 본편의 웅장함을 해치는 후보는 기본 엔딩으로 되돌린다.

## 5. 검토 이력·직접 확인 범위

### 문서와 파일

다음 문서는 끝까지 읽었다.

- `astra/keyvis-brief.txt`
- `astra/foothold-ultra/production-design.md` v1.2, 436줄 전체
- `astra/foothold-ultra/brand-brief.txt`
- `inbox/jay/20260904-launch/design/scenario-direction.md`
- `inbox/jay/20260904-launch/library/INDEX.md`

라이브러리 디렉터리의 실제 파일 수는 Python으로 **MP4 29개·PNG 18개**를 확인했다. 이 개수 확인은 영상 전부를 재생하거나 각 영상의 과금을 검증했다는 뜻이 아니다. 이번 저장소 수정 금지 지시에 따라 git pull·이슈 생성·브랜치·커밋·저장소 편집은 수행하지 않았다. 산출물은 지정된 이 Markdown 하나다.

### 이미지 열람 도구로 직접 본 파일

아래 경로에서 `scratchpad/`는 `C:/Users/AI-WS01/AppData/Local/Temp/claude/C--Users-AI-WS01-Desktop-jay----------foothold-lab/85e9e940-5633-48ed-a407-2d9aafc96e93/scratchpad/`를 뜻한다. 라이브러리 MP4 원본 경로는 저장소의 `inbox/jay/20260904-launch/library/`다.

| 직접 연 파일 | 확인한 범위 |
|---|---|
| `keyvis/library_contactsheet.png` | 47건의 전체적인 구도·색 차이. 긴 축소판이라 초기 1~38번의 세부 외형·접지 검수 자료로 쓰지 않았다. |
| `keyvis/previs_contactsheet.png` | 20개 세그먼트의 시작·중간·끝 개요, s10b·s15b 포함, s19의 3.97초 표기. |
| `keyvis/lib_thumbs/39-1548-seedance-02_aisle_{0,1,2}.jpg` | 세 파일 모두 개별 열람. 통로·과도한 중간 차체 가림·대기. |
| `keyvis/lib_thumbs/40-1548-seedance-05_orbit_{0,1,2}.jpg` | 세 파일 모두 개별 열람. 비교적 성긴 배치·선회 계열 시점. |
| `keyvis/lib_thumbs/41-1548-seedance-03_lead_{0,1,2}.jpg` | 세 파일 모두 개별 열람. 넓은 대열·바위 전경·낮은 태양. |
| `keyvis/lib_thumbs/42-1548-seedance-04_underfoot_{0,1,2}.jpg` | 세 파일 모두 개별 열람. 낮은 근경·지지와 스윙·스침. |
| `keyvis/lib_thumbs/43-1548-seedance-00_foot_{0,1,2}.jpg` | 세 파일 모두 개별 열람. 후면·낮은 대열·끝의 큰 가림. |
| `keyvis/lib_thumbs/44-1548-seedance-01_side_{0,1,2}.jpg` | 세 파일 모두 개별 열람. Go2 측면·통로·암석과 모래. |
| `keyvis/lib_thumbs/45-1556-seedance-07_rise_{0,1,2}.jpg` | 세 파일 모두 개별 열람. 중앙 한 줄인 배치. |
| `keyvis/lib_thumbs/46-1556-seedance-06_dolly_{0,1,2}.jpg` | 세 파일 모두 개별 열람. 거리별 군집·대기·지형. |
| `keyvis/lib_thumbs/47-1616-seedance-rise-retry_{0,1,2}.jpg` | 세 파일 모두 개별 열람. 직사각 대군·먼지·외곽 평탄함. |
| `keyvis/previs_frames/s03_1.png`, `s05_0.png`, `s06_1.png`, `s07_0.png`, `s08_0.png`, `s09_2.png` | 각각 개별 열람. 실제 매핑·자막·외형·평지 첫발 상태. |
| `keyvis/previs_frames/s10_1.png`, `s10b_1.png`, `s11_1.png`, `s12_0.png`, `s13_1.png`, `s14_1.png`, `s15_1.png`, `s15b_1.png` | 각각 개별 열람. 격자·성긴 밀도·폭풍의 현재 상태·일렬·타이트 부족. |
| `keyvis/previs_frames/s16_0.png`, `s16_2.png`, `s1718_0.png`, `s1718_1.png`, `s1718_2.png`, `s19_0.png` | 각각 개별 열람. 대열 구조 차이·전체 FOOTHOLD·도달 크기·기존 타이틀. |
| `launch_render/charsheet3/go2_charsheet_source_v3.png` | 승인 합본 전체를 이미지 도구로 확인. |
| `launch_render/charsheet3/front.png`, `back.png`, `left.png`, `right.png`, `foot.png`, `q34.png`, `head_front.png`, `head_left.png`, `head_right.png` | 개별 아홉 장 모두 열람. 흰 몸체·검은 센서/발끝·좌우 패널·격자 배경·발 상세의 접지 경계 한계. |

### 원본 MP4의 추가 정지 프레임 확인

이미지 파일을 새로 저장하지 않고 FFmpeg로 원본 프레임을 메모리에서 디코드한 뒤 1920×1080 JPEG 미리보기로 직접 열람했다. 검수용 JPEG 재압축이므로 원본 픽셀 동일성 검사는 아니다. 아래 여섯 원본의 메타데이터는 각각 1920×1080·24fps·약 3.71초로 읽혔다.

| 원본 파일 | 직접 디코드해 본 시점 | 반영 |
|---|---|---|
| `39-1548-seedance-02_aisle.mp4` | 0.000초 | 내부 구도와 중앙 접점 후보 유지. |
| `41-1548-seedance-03_lead.mp4` | 0.000초 | 넓은 대열은 보이나 지형 단차·지지 반응이 부족하다는 검증 지적을 수용. s06은 b로 전환. |
| `43-1548-seedance-00_foot.mp4` | 0.000·0.250·0.500초 | s07 대표 후보는 0.500초. 중앙 근경의 한 지지와 들린 발을 분리해 읽을 수 있는 순간을 선택. |
| `44-1548-seedance-01_side.mp4` | 0.000·0.250·0.500초 | 0.250·0.500초에는 가까운 몸통 가림이 커져 s08은 0.000초 유지. 잘린 전경 발은 접지 증거에서 제외. |
| `42-1548-seedance-04_underfoot.mp4` | 0.000·0.250·0.500초 | s09는 0.250초. 오른쪽 가까운 발이 낮은 돌 쪽에 닿는 순간을 선택하며, 네 발이 떠 보이는 0.000초는 후보에서 제외. |
| `46-1556-seedance-06_dolly.mp4` | 0.000초 | 앵커의 실제 시작 프레임 대기·거리 대비 확인. |

이 점검은 네 a 컷의 모든 A 조건을 최종 합격시킨 판정이 아니다. s06은 이 점검 뒤 신규 생성으로 전환했다. 남은 s07의 낮은 대비, s08의 잘린 발은 원본 접점·인접 프레임 검수에서 결함이 남으면 지정 시점을 폐기해야 한다. 캡처 한 장이 예쁘다는 이유로 험지 반응을 충족했다고 쓰지 않는다.

### 아직 확인하지 않은 것

- 29개 MP4의 정상속도 전체 재생, 모든 후보 접점의 연속 프레임 검사, 오디오와 컷의 실제 이동 속도. 지정 시점은 아래의 메모리 디코드 열람으로 보완했으나 납품용 캡처 파일은 만들지 않았다.
- 위 표에 따로 열었다고 적지 않은 개별 프리비즈 PNG. 그 화면은 컨택트시트 수준으로만 봤다. 초기 라이브러리 1~38의 PNG·MP4 원본 세부도 별도 열람하지 않았다.
- 8192 객체의 실제 씬 목록·좌표·카메라 높이와 렌즈·후퇴/상승 경계 핸들. 숫자와 이름을 프레임 제목에서 봤다는 사실을 독립 재계수로 바꾸지 않았다.
- 정본 로고 SVG 파일, 실제 12초 엔딩 마스터·정확한 이벤트 시각·해시. F는 이 자료를 확인한 뒤에만 채택할 선택안이다.
- 현 Higgsfield 로그인 계정 화면, 모델별 실제 이미지 생성 결과, 성공률·지연·최대 해상도의 계정별 실측. 계정 조건은 브리프 제공값이고 UI 일반 동작은 위 공식 문서로 보완했다.
- 이번에 명세한 C/M/T의 정리된 업로드 파일과 K컷번호 이미지. 아직 생성·추출하지 않았다. 따라서 ‘바로 업로드 가능한 새 참조 파일을 납품했다’고 주장하지 않는다.

### 독립 검증

1차 독립 검증은 `codex exec --model gpt-6-astra -c model_reasoning_effort=high`로 읽기 전용 수행했다. 검증자는 초기판의 19컷·a/b/c 5/12/2·12개 영문 본문·95개 참조 필드·24후보를 직접 재계수했고, s06의 험지 반응 증거 부족과 s14~15b의 최종 배치 대응 관문 누락 두 건을 지적했다. v1.1에서는 s06을 신규 생성으로 바꾸고 전체 수량·프롬프트·슬롯·세션을 갱신했으며, s14~15b의 같은 구역·접점 조건을 컷표·세션·c 후속 관문에 추가했다. 2차 검증자는 수정 주장을 믿지 않고 현재 본문과 원본을 다시 대조해 **설계 발행 가능·차단 지적 없음**으로 판정했다. 19컷·a/b/c 4/13/2·합격 기준 57개·참조 필드 95개·영문 본문 13개·기본 후보 26장을 독립 재계수했고, 기존 두 지적의 해결과 슬롯 역할의 일관성을 확인했다. 이전 제작 설계 v1.2의 검토 통과를 이번 문서의 통과로 대신하지 않았다.

이 판정은 글로 된 설계의 요구 충족에 대한 것이다. 검증자는 기존 이미지들을 직접 열람했지만 s07 0.500초·s09 0.250초는 이번 워커의 디코드 기록과 표의 일치를 확인했고 해당 원본 시점을 다시 디코드하지 않았다. 전체 영상·연속 접지·현 계정 UI·생성 성능·8192 씬 재계수·실제 12초 엔딩과 SVG 정합은 여전히 미검증이다. 검증 완료 시각은 2026-09-14 02:46 KST이며 별도 보고서 파일은 만들지 않았다.

| 판 | 변경 | 검증 상태 |
|---|---|---|
| v1.0 | 직접 이미지 확인을 반영한 19컷 확보표, 12개 영문 전문, 참조 정책, 세션 순서, c의 최종 관문, 선택 엔딩안 | 1차 독립 검증: 수정 필요 2건 |
| v1.1 | s06 신규 생성 전환, 13개 영문 전문·26후보, s14~15b의 최종 배치 연결 관문, s07·s09 캡처 시점 조정, 원본 메모리 디코드 확인 기록 | 2차 독립 검증: 설계 발행 가능, 기존 2건 해결·추가 차단 없음 |
