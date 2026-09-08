# 기획발표 엔딩 타이틀

> 분류: 운영
> 작성: 오흥재 · 2026-09-03 23:50
> 근거: 실측
> 요지: 4096체 대군 영상 뒤에 붙일 12초 엔딩 타이틀. HTML 원본과 1080p MP4.
> 상태: 확정
> 판: v1.0

평지 대군 영상(`sim/eval/results/20260903-flat-army-cine/`)이 부감 상승으로 끝난 뒤
이어 붙일 타이틀이다. 발표 마무리에 쓴다.

| 파일 | 무엇 |
|---|---|
| `foothold-ending-title.mp4` | 1920 x 1080 · 30 fps · 12초. 편집 타임라인에 바로 얹는다 |
| `foothold-ending-title.html` | 원본. 브라우저로 열면 재생 · 구간 이동 · 문구 수정이 된다 |

## 순서

| 시간 | 무엇 |
|---|---|
| 0.0 - 1.4 | 부감 격자가 멀어진다. 주황 10 m 선이 중앙에 남는다 |
| 1.3 - 2.4 | 화면이 가로로 찢기고 게이트 주황이 샌다 |
| 2.1 - 3.6 | 찢긴 틈으로 FOOTHOLD 워드마크가 드러난다 |
| 3.6 - 4.0 | 한 번 더 찢기며 워드마크가 사라진다 |
| 4.0 - 4.2 | 중앙에 하얀 선이 그어진다 |
| 4.2 - 4.9 | 그 선에서 FIND THE NEXT STEP 이 위아래로 펼쳐진다 |
| 5.85 - 7.1 | 같은 선이 되돌아와 자른다. 위는 우측, 아래는 좌측으로 나간다 |
| 7.0 - 9.6 | 불확실한 지형에서도, 다음 걸음을 이어갑니다 |
| 9.4 - 12.0 | 스택 락업. 심볼 · FOOTHOLD · Terrain-Adaptive Locomotion Policy |

선이 문구를 열고 같은 선이 문구를 가른다. 여는 선과 자르는 선은 같은 축이다.

## 브랜드 정본을 어떻게 썼나

로고는 `foothold-brand/assets/logo/v1` 의 SVG 를 **바이트 그대로** 넣었다.
시스템 폰트로 다시 그리지 않았고 기하도 포크하지 않았다.

- `foothold-wordmark-reverse.svg` · 2.1 - 4.0초 구간
- `foothold-lockup-stacked-dark.svg` · 마지막. `pitch.html` 엔딩 슬라이드와 같은 자산

기울기 `skewX(-3)` 은 워드마크가 원래 갖고 있는 것이다.
FIND THE NEXT STEP 은 로고가 아니라 디스플레이 타이포라서, 새 서체를 들이지 않고
브랜드 웹 스택(`Pretendard` · `Malgun Gothic` · `Segoe UI`)에 같은 3도 기울기를 걸었다.

색은 전부 `foothold-brand/tokens/foothold.tokens.json` 의 다크 모드 값이다.

| 쓰임 | 토큰 | 값 |
|---|---|---|
| 바탕 | `primitive.color.paper` dark | `#12161d` |
| 격자 | `primitive.color.rule` dark | `#2b323d` |
| 글자 · 워드마크 | `primitive.color.ink` dark | `#e9e7e1` |
| 강조 | `primitive.color.teal-brand` dark | `#3ec7b4` |
| 눈썹 | `primitive.color.amber` dark | `#dc9a30` |

주황 `#f2440d` 하나만 브랜드 색이 아니다. 렌더의 10 m 게이트 큐브 색
(`diffuse_color=(0.95, 0.18, 0.04)`) 을 그대로 가져온 것이며, 영상을 묘사하는
부분에만 쓴다.

## 마크 왜곡은 승인 사항이다

`BRAND_USAGE_POLICY.md` 는 마크에 glow · recolour · rearrange 를 금지한다.
이 모션 한 편에 한해 **팀장이 그 목록을 풀었다**. 그래서 2.1 - 4.0초 구간에서
워드마크에 색분리 · 블러 · 흔들림 · 찢긴 조각이 걸린다.
다만 **기하는 그대로**이고 **마지막 락업은 손대지 않았다**.
망가뜨렸다가 깨끗하게 착지시키는 것이 이 연출의 뼈대다.

## 문구는 승인본이다

`VOICE_AND_MESSAGE.md` 기준이다.

| 쓰인 문장 | 상태 |
|---|---|
| 불확실한 지형에서도, 다음 걸음을 이어갑니다. | 2026-08-09 승인 |
| Terrain-Adaptive Locomotion Policy | 2026-08-07 채택 · 락업에 포함 |

FIND THE NEXT STEP 은 승인된 브랜드 문구가 아니라 이 영상의 연출 문구다.
승인 영문 슬로건은 `Find the next foothold.` 다.

`Target Vision` 눈썹은 원래 North Star 문장
(`시뮬레이터에서 천 번 넘어지고, 현장에서는 넘어지지 않는다.`)에 의무로 붙는 라벨이다.
지금은 승인 슬로건 위에 얹혀 있으므로, 브랜드 상태 표기로 읽히지 않게 할 것이면
HTML 의 「문구 위 눈썹」 칸을 비우면 된다.

## 하단 기술 스택

`SIM TO REAL · ISAAC SIM 5.1 · RSL-RL PPO · UNITREE GO2 · ROS2 JAZZY`

`ROS2 JAZZY` 는 이 저장소에서 근거를 찾지 못했다. Track B 실물 쪽 사용이라면 맞다.

## 다시 굽는 법

HTML 은 `?shot=1&t=<초>` 로 열면 그 시각 한 장만 그린다. 이 성질을 이용해
Chrome 헤드리스로 360장을 찍고 ffmpeg 으로 묶었다.
`scripts/shoot-ending-title.py` 가 그 과정 전부다.

```
python inbox/jay/20260903-ending-title/scripts/shoot-ending-title.py
```

30 fps · 12초 · 360프레임 · H.264 crf 17.
