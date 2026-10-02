# 전체본·Ending 브랜드 클로징 연결

사용자 제공 영상 `hf_20260930_233959_ae4a4a56-1db5-4f21-bd67-15ec33363dab.mp4`를 기존 전체본과 Ending 뒤에 추가했다. Opening과 이전 v1은 보존했다.

- `확인됨`: 원본은 1920×1080, 24fps, HEVC 영상과 AAC 32kHz 스테레오 음성 스트림이며 약 11.709초다.
- Higgsedit native에서 기존 전체본 69.5초 뒤에 281프레임을 붙였다. 기존 E7 암전 뒤 제공된 브랜드 영상이 시작하며 추가 디졸브는 없다. 음원은 각 원본을 이어 붙였으며 신규 유료 생성은 하지 않았다.
- 전체 `assets/film-master-v2.mp4`는 영상 기준 81.208초, Ending `assets/film-ending-v2.mp4`는 50.083초다. MP4/AAC 컨테이너와 브라우저는 수 ms 차이를 표시할 수 있다.
- 동일한 `output/FOOTHOLD-film-storyboard.html` 상단을 갱신했다. 이전 버전 링크와 브랜드 구간 바로 재생 버튼을 함께 두었다.
- 연결부 프레임, 브라우저 재생 메타데이터, E7 버튼을 확인했다. JavaScript 오류 0건. 증거: `assets/film-master-v2.qa.json`, `output/film-master-closing-boundary-v2.jpg`.
- 사운드는 기존 임시 믹스와 제공 클립 원음이다. 전체 영화 음악과 최종 사운드 믹싱의 완료를 의미하지 않는다. E5pre 관련 수정은 이번 범위에 포함하지 않았다.
- 제공 클립 중간 문구는 `FIND THE NEXT STEP`이다. 앞서 요구한 슬로건과의 차이를 보고했으며 원본을 임의로 바꾸지 않았다.

원본·결과 URL과 타임라인은 `assets/film-append-closing-v2.outputs.json`, 재편집 가능한 native 스크립트는 `assets/film-append-closing-v2.jsx`에 있다.
