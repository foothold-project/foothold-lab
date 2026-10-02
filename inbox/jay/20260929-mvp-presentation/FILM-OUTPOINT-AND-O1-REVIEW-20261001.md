# E5pre 끝점과 O1 탐색 수정 검토

- `확인됨` 사용자가 지적한 것은 비교 영상의 POV OUT -2 FRAMES 구간이다. v5는 채택하지 않는다.
- v4의 1193~1206번 프레임은 직전 보행에 비해 화면 변화가 매우 작다. v6에서는 14프레임(24fps, 약 0.583초)을 제거했다. 출력에서 1192번까지 움직임이 있고 1193번부터 E5가 나온다. 수치는 assets/film-outpoint-v6-audit.json에 있다.
- 접지음 마지막 꼬리는 기존 전체본 약 49.575초까지이며 새 끝점은 약 49.708초다. 접지음은 유지했다. 음향 이음새에는 4ms 페이드를 적용했다.
- O1 새 후보 작업 ID: 9af80866-fc3e-4b09-a56e-dcd0e22b5cc9. Seedance 2.5, 480p, 8초, 음향 포함. 견적 24크레딧.
- `확인됨` 표본 영상에서 암전·작은 빨간 점, 왼쪽 기둥과 수면, 오른쪽 길, 마지막 근접 바닥이 나타난다. O2 2.25초를 뒤에 붙여 연결 검토본을 만들었다. 생성 원음이며 최종 음악 믹싱은 아니다.
- 검토 위치: output/FOOTHOLD-film-storyboard.html 상단의 정지 꼬리 제거 비교와 O1→O2 좌우 탐색 후보. O1 카드에도 새 연결 영상 버튼을 붙였다.
- 기본 전체본은 v4를 유지한다. v6 전체·Ending과 O1 교체는 사용자 검토 후보이며 승인 또는 최종 완성으로 기록하지 않는다.

근거: 이 대화의 사용자 수정 지시, assets/film-outpoint-v6-audit.json, assets/opening-o1-seedance25-v4.request.json, assets/film-o1-o2-lookaround-v4.delivery.json.
