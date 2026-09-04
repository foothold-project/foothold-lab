# 컷 변환 기록

`seedance_2_5` · `mode: video_edit` · `resolution: 1080p` · `generate_audio: false`
입력은 `cuts4/` 의 4초 원본 컷. 출력은 `styled/`.

`mode` 를 안 주면 `t2v` 로 떨어지고 참조 영상을 받지 않는다 (422).
`medias[].role` 은 `video_references` 다. `video` 나 `video_edit` 을 넣어도
서버가 `video_references` 로 바꾸지만 `mode` 는 안 바꾼다.

## 실측 단가

| 무엇 | 크레딧 |
|---|---|
| 여덟 컷 일괄 | 284 (639.5 → 355.5) |
| `rise` 재변환 하나 | 36 (355.5 → 319.5) |
| `get_cost` 가 미리 말한 값 | 32.5 |

`get_cost` 의 32.5 와 실제 청구 36 이 다르다. 잔액 차이로 잰 값이 36 이다.
견적을 그대로 믿고 예산을 짜면 컷당 3.5 크레딧씩 모자란다.

### 걸린 시간 (실측)

`rise` 재변환 한 건. 4.04초 · 1080p.

| | |
|---|---|
| 제출 | 16:15:1x |
| 완료 확인 | 16:19:09 |
| 벽시계 | 237초 이내 |
| 영상 1초당 | 58.7초 이내 |

직전 폴링에서 아직 진행 중이었으므로 위 값은 상한이다.

## 프롬프트

여덟 컷에 공통으로 들어간 것

- 사진처럼 보이는 시네마틱 플레이트로 다시 조명하고 다시 입힌다
- 격자 · 개체 수 · 간격을 그대로 둔다
- 로봇 색을 지정하지 않는다. 원래의 흰 셸을 그대로 둔다
- 셸의 각인과 표기를 지운다는 말을 하지 않는다 (팀장 결정: 「글자 금지 없이 로고 있게해」)
- 없던 글자 · 로고 · 간판을 새로 그리지 않는다
- 중간 정도의 헤이즈, 부드러운 하이라이트와 필름 롤오프, 하드 클리핑 없음
- 해는 한쪽으로 비켜 둔다. 들어 올린 암부. 어두운 팔레트

가까운 컷 다섯 (`foot` `side` `aisle` `lead` `underfoot`)
- 림 라이트와 바운스 필

넓은 컷 셋 (`orbit` `dolly` `rise`)
- 열이 곧게 뻗어 있다는 절

## 각인이 살아 있는가

팀장 지시로 여덟 컷 전량 확인했다.

| 컷 | 원본의 글자 | 변환본 |
|---|---|---|
| foot | 없음 | 없음. 새로 그린 글자 없음 |
| side | 옆구리 `Go2` | 그대로 남았다 |
| aisle | 셸 각인 `Unitre` | 그대로 남았다 (`evidence/final/aisle_styled_mark.png`) |
| lead | 없음 | 없음. 새로 그린 글자 없음 |
| underfoot | 없음 | 없음. 새로 그린 글자 없음 |
| orbit | 없음 | 없음. 새로 그린 글자 없음 |
| dolly | 없음 (너무 멀다) | 없음. 새로 그린 글자 없음 |
| rise | 없음 (너무 멀다) | 없음. 새로 그린 글자 없음 |

없던 글자를 새로 그려 넣은 컷은 없다.

## 구도가 흔들린 컷

각인과 별개의 문제다. 모델이 컷을 다시 짜는 성질이 있다.

| 컷 | 무엇이 달라졌나 | 판단 |
|---|---|---|
| foot | 군이 더 뒤로 물러나고 작아졌다. 접사의 밀도가 준다 | 감수 |
| lead | 같은 방향으로 물러났다 | 감수 |
| rise | **컷이 통째로 바뀌었다.** 원본은 격자 전체를 위에서 내려다보며 올라가는 컷인데 1차 변환본은 지면 높이에서 한 줄로 늘어선 로봇이 길을 따라 걸어간다 | 다시 걸었다 |

`rise` 1차 변환본은 「수천 대가 격자로 선다」는 이 영상의 전제를 깨뜨렸다.
증거는 `evidence/final/scan-rise.jpg` (왼쪽 원본 · 오른쪽 1차 변환본).

## rise 를 어떻게 되살렸나

길이 셋 있었다. 셋 다 만들어 놓고 견주었다. `evidence/final/rise-choice.jpg`
(왼쪽 위 원본 · 오른쪽 위 1차 변환본 · 왼쪽 아래 원본 그레이딩 · 오른쪽 아래 재변환).

| 길 | 결과 |
|---|---|
| 1차 변환본 그대로 | 군이 한 줄이 된다. 전제가 깨진다 |
| ffmpeg 그레이딩만 (`scripts/grade-source-cut.py`) | 시뮬레이션은 지키지만 화면이 보랏빛 격자다. 앞 컷들의 사막 톤과 안 맞고 탈물질화가 드러낼 것을 한 컷 먼저 드러낸다 |
| **구도를 못 박아 다시 변환** | 격자와 개체 수와 간격이 남는다. 톤이 `dolly` 와 이어진다. **이것을 썼다** |

재변환 프롬프트에 넣은 절. 1차에는 없던 것이다.

- 카메라 · 프레이밍 · 샷을 바꾸지 마라
- 로봇 수를 줄이지 마라
- 대형을 한 줄 · 좁은 열 · 길 · 통로로 바꾸지 마라
- 로봇 하나하나의 자리 · 크기 · 간격을 그대로 두어라

전문은 `scripts/` 가 아니라 이 문서에 남긴다. 재변환은 MCP 호출 한 번이라
스크립트가 없다. 다시 걸 일이 있으면 아래를 그대로 쓴다.

```
Relight and re-texture this exact simulation render as a photoreal cinematic
plate. CRITICAL: do not change the camera, the framing, or the shot. The camera
stays high above, looking down at a steep angle over a vast open plain, and the
same enormous grid of many hundreds of identical four-legged robots fills the
frame in perfectly straight rows and columns with even spacing. Do not reduce
the number of robots. Do not turn the formation into a single file, a narrow
column, a road or a path. Keep every robot in its exact position, size and
spacing, and keep the same camera move. Only the world changes: replace the dark
synthetic floor and the glowing grid lines with real hostile ground, dry cracked
earth and fine dust, under a hazy overcast sky with the sun low and off to one
side, moderate atmospheric haze receding into depth, soft highlights with filmic
rolloff and no hard clipping, lifted deep shadows, a dark restrained palette. The
robots keep their original clean white shell exactly as it is; do not tint,
recolour or dirty them. Preserve every existing marking and engraved lettering on
the shells. Do not add any new text, logo, signage or writing anywhere in the
frame. No people, no vehicles, no structures.
```

재변환본도 카메라가 원본과 똑같지는 않다. 원본은 거의 수직으로 내려다보는데
재변환본은 조금 낮은 데서 열을 따라 본다. 다만 이 컷이 할 일은 「수천 대가
격자로 있다」를 보이는 것이고 그것은 지켰다. 480 화소로 보면 로봇이 어두워
보이지만 전체 해상도에서는 흰 셸이다 (`evidence/final/rise_v2_crop.png`).

`styled/retry/` 에 1차와 재변환본을 둘 다 남겨 두었다.
`scripts/grade-source-cut.py` 와 `build-launch-a.py --fallback rise` 도 남긴다.
다음에 모델이 컷을 갈아 치우면 재변환이 먹히지 않을 수도 있고 그때 쓸 길이다.
