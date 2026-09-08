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

### 「견적이 낮게 나온다」는 것은 내가 틀린 것이었다

한때 「`get_cost` 32.5 대 실청구 36 이니 예산에 1.1 을 곱하라」고 적었다.
**그 규칙은 틀렸다. 지웠다.**

다시 재 보니 `get_cost` 는 정확하다. 내가 **다른 것의 값을 물었다.**
그 호출에 `mode` 와 `resolution` 을 안 넣어서 기본값인 t2v · 720p · 5초의 값이
돌아왔다. 실제로 제출한 것은 video_edit · 1080p 다.

파라미터를 맞춰 다시 부르면 이렇다. 전부 `get_cost` 실측이고 과금은 없다.

| mode | 해상도 | 견적 | 실청구 |
|---|---|---|---|
| `t2v` (기본) | 720p (기본) · 5초 | 32.5 | 안 걸었다 |
| `t2v` (기본) | 1080p · 5초 | 45 | 안 걸었다 |
| `video_edit` | 720p · 입력 4.04초 | 26 | 안 걸었다 |
| **`video_edit`** | **1080p · 입력 4.04초** | **36** | **36. 14건 전부** |

**견적과 실청구가 정확히 맞는다.** 배수를 곱할 일이 없다.

배울 것은 이것이다. **`get_cost` 를 부를 때 제출할 파라미터를 그대로 넣어라.**
`mode` 를 빠뜨리면 조용히 기본값 t2v 의 값이 돌아오고, 그것은 우리가 걸 것의
값이 아니다. 오류가 아니라 다른 질문에 대한 정답이 온다.

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

## 각인이 두 개다

원본 모델에 각인이 두 군데 있다. 둘 다 원래 있는 것이다.

| 자리 | 글자 |
|---|---|
| 옆면 셸 | `Unitree` |
| 측면 패널 | `Go2` |

컷마다 다른 글자가 보이는 것은 **카메라가 다른 면을 보기 때문이고 정상이다.**
어느 컷에 `Go2` 만 보인다고 해서 `Unitree` 가 지워진 것이 아니다.

원본 각인은 **몸체와 같은 색의 돋을새김**이다. 모델이 새로 그린 글자는
**납작한 회색 데칼**이라 생김새가 다르다. 이것이 판별 기준이다.

## 각인이 살아 있는가

**A 와 B 를 따로 걸어야 한다.** 아래는 A 기준이다. B 는 다음 절에 따로 적는다.
처음에 「여덟 컷 전량 확인, 없던 글자 없음」이라고 보고했는데 그것은 A 기준이었고
B 에는 해당하지 않는다.

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

## B 판에는 모델이 새로 그린 글자가 있다

리드가 잡았다. 내 손으로도 확인했다. **B 의 4번 `lead` 컷이다.**

| | 원본 `cuts4/03_lead.mp4` | B 변환본 |
|---|---|---|
| 앞을 막는 큰 로봇 | 없다 | **있다.** 모델이 만들었다 |
| 그 몸통의 글자 | 없다 | **`Unitree` 납작한 회색 데칼** |

증거는 `evidence/b-mark/b-lead-pair.jpg` 다 (왼쪽 원본 · 오른쪽 B).
B 의 3번 `aisle` 은 돋을새김 그대로라 문제없다.

A 의 같은 컷에는 이 로봇도 이 글자도 없다. 그래서 A 만 보고 「없다」고 하면 놓친다.

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
