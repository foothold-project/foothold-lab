# E5pre 기존 화면 유지·연결 음향 수정

사용자 지시에 따라 외부 시점의 Go2가 등장한 재생성 v4를 채택하지 않았다. 기존 전체본 `film-master-v2.mp4`의 영상을 그대로 두고 소리만 수정했다. 신규 유료 생성은 없다.

- `확인됨`: 기존 믹서가 다른 컷의 원음에는 0.62, E5pre에는 0.10을 적용해 E5pre 원음·공간음을 상대적으로 15.85dB 더 줄였다. E4 단일 발소리 조각을 8회 반복해 덧입히기도 했다.
- 원래 POV v3의 원음 비율을 0.62로 회복하고 반복 발소리 덧입힘을 제거했다. E4와 E5pre의 짧은 원음 꼬리를 각 다음 컷 첫머리에 한 번씩 감쇠해 연결했다.
- 전체본 45.00~50.50초에만 재구성한 음원을 적용했다. 핵심 POV는 45.25~50.25초이며 양끝 0.25초는 기존 음원과 교차 감쇠한다. 원래 임시 저음 배경은 유지했다. AAC를 다시 인코딩하므로 소리 파일 바이트 자체는 같지 않다.
- `확인됨`: 전체본과 Ending 영상은 stream copy했으며 v2/v3의 영상 스트림 SHA256이 각각 동일하다. 로봇·카메라·height scan·영상 속도·브랜드 클로징 픽셀은 변경하지 않았다.
- 전체본 `assets/film-master-v3.mp4`, Ending `assets/film-ending-v3.mp4`. Opening은 기존 v1 그대로다.
- 전후 비교 `assets/film-e5pre-audio-comparison-v3.mp4`: 같은 E4→E5pre→E5를 BEFORE 14.75초, 블랙 0.5초, AFTER 14.75초 순서로 재생한다. 비교판에만 식별 라벨을 넣었다.
- `output/FOOTHOLD-film-storyboard.html` 상단 플레이어와 해당 컷 버튼을 갱신했다. 이전 v2 링크도 남겼다.

측정 근거와 결과 URL은 `assets/film-audio-v3.audit.json`, 수정한 믹서는 `design/build-film-sound-v3.py` 및 `design/patch-film-sound-v3.py`에 있다. E5pre 전체 믹스 RMS는 -16.77→-15.83dBFS다. 이는 분리된 공간음 측정이나 청취 품질의 증명이 아니다. 최종 청취 승인은 사용자 확인을 기다린다. 별도 영화 음악과 전체 최종 믹싱은 아직 완료하지 않았다.
