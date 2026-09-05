# 힉스필드 라이브러리 전량

> 분류: 운영
> 근거: 실측. `show_generations` 를 종류별로 넘겨 받고 원장과 대조했다
> 요지: 47건 전량을 원본 그대로 내려받았다. 47건이 모두 과금과 짝지어지고 남는 과금 3건이 정확히 환불된 실패 3건이다.
> 파일 위치: `inbox/jay/20260904-launch/library/` (343 MB. 저장소에는 안 넣는다)

## 전량이라는 증거

`show_generations` 를 종류마다 `next_cursor` 가 null 이 될 때까지 넘겼다.

| 종류 | 건수 | `next_cursor` | 받은 파일 |
|---|---|---|---|
| video | 29 | null (한 쪽에서 끝) | **29** |
| image | 18 | null (한 쪽에서 끝) | **18** |
| audio | 0 | null | 0 |
| 3d | **확인 못 함** | 서버 오류 2회 | 0 |
| **합** | **47** | | **47** |

**목록 건수와 받은 파일 수가 같다. 실패 0건이다.**

3d 목록은 두 번 다 서버 오류(`Something went wrong`)로 못 읽었다. 다만 **원장에
3d 과금이 한 건도 없다.** 원장에 나오는 모델 이름은 Seedance 2.5 · Gemini Omni
Flash 1.1 · Nano Banana Pro 셋뿐이다. 그러니 3d 로 만든 것은 없다.

### 크레딧으로 다시 검산한다

47건을 원장의 과금 행과 시각으로 짝지었다. 결과가 이렇다.

| | 크레딧 |
|---|---|
| 47건에 짝지어진 과금 | 680.5 |
| 짝이 안 남은 과금 3건 | 11.0 |
| **합** | **691.5** = 원장 총 과금 |

**짝이 안 남은 3건이 정확히 환불된 실패 3건이다.** gemini 4.5 두 건과 nano
banana 2 한 건이고 합이 11.0 으로 환불 총액과 같다. 결과물이 없으니 짝지을 것도
없는 것이 맞다. 이것이 「전량을 받았다」의 독립적인 증거다.

## 원본 그대로다

재인코딩하지 않았다. `curl` 로 바이트를 그대로 가져왔다.
**gemini 14건 전부 오디오가 살아 있다.** 확인했다.

```
Stream #0:0 Video: h264 (High), yuv420p, 1920x1080, 24 fps
Stream #0:1 Audio: aac (LC), 48000 Hz, stereo, 128 kb/s
```

seedance 15건에는 오디오가 없다. 우리가 `generate_audio: false` 로 껐기 때문이다.
켜도 크레딧은 36 으로 같다. `ARCHIVE.md` 에 적었다.

## 파일 이름

`순번-시각-모델-용도.확장자` 다. 시각은 KST 다. 순번이 시간 순이라 그대로 정렬된다.

`컷` 열의 확신이 「아마」인 것은 입력 미디어 기록이 없어 **화면 구도로 맞춘 것**이다
(`scripts/match-generation-to-cut.py`). 원경끼리는 잘 안 갈린다. 파일 이름에 든
컷 이름도 그만큼만 믿어야 한다.

`x` 로 끝나는 파일 셋은 컷을 못 맞춘 것이다.

## 프롬프트

**전문을 `library/prompts.json` 에 남겼다.** 파일 이름이 열쇠다.

저장소 규칙상 em dash 를 쓸 수 없어서 JSON 안에서 `\u2014` 로 이스케이프해 두었다.
`json.load` 로 읽으면 원문 그대로 돌아온다. 요지로 줄이지 않았다.

## 목록

| 파일 | 시각 | 모델 | 길이 · 크기 | 해상도 | 오디오 | 크레딧 | 컷 | 확신 | 썼나 |
|---|---|---|---|---|---|---|---|---|---|
| `01-0900-img2vid-old-whale.mp4` | 09:00 | image2video | 5.37s | 1080p | 없다 | 0 | ? | 확실 | 이전 작업. 우리 것 아니다 |
| `02-0921-nano-keyvis.png` | 09:21 | nano banana 2 | 5504x3072 | 4k | 없다 | 4 | - | - | **키비주얼에 씀** |
| `03-0921-nano-keyvis.png` | 09:21 | nano banana 2 | 5504x3072 | 4k | 없다 | 4 | - | - | **키비주얼에 씀** |
| `04-0921-nano-keyvis.png` | 09:21 | nano banana 2 | 5504x3072 | 4k | 없다 | 4 | - | - | **키비주얼에 씀** |
| `05-0926-nano-keyvis.png` | 09:26 | nano banana 2 | 5504x3072 | 4k | 없다 | 4 | - | - | **키비주얼에 씀** |
| `06-0926-nano-keyvis.png` | 09:26 | nano banana 2 | 5504x3072 | 4k | 없다 | 4 | - | - | **키비주얼에 씀** |
| `07-0935-seedance-x.mp4` | 09:35 | seedance 2 5 | 3.71s | 1080p | 없다 | 36 | ? | 확실 | 버렸다 |
| `08-0935-gemini-x.mp4` | 09:35 | gemini omni flash 1 1 | 4.01s | 1080p | 있다 | 18 | ? | 못 맞춤 | B 에 씀 |
| `09-0944-gemini-00_foot.mp4` | 09:44 | gemini omni flash 1 1 | 0.68s | 1080p | 있다 | 4.5 | 00_foot | 아마 | B 에 씀 |
| `10-0945-gemini-06_dolly.mp4` | 09:45 | gemini omni flash 1 1 | 3.35s | 1080p | 있다 | 18 | 06_dolly | 아마 | B 에 씀 |
| `11-1010-gemini-01_side.mp4` | 10:10 | gemini omni flash 1 1 | 0.68s | 1080p | 있다 | 4.5 | 01_side | 아마 | B 에 씀 |
| `12-1010-gemini-02_aisle.mp4` | 10:10 | gemini omni flash 1 1 | 0.68s | 1080p | 있다 | 4.5 | 02_aisle | 아마 | B 에 씀 |
| `13-1011-gemini-05_orbit.mp4` | 10:11 | gemini omni flash 1 1 | 0.85s | 1080p | 있다 | 4.5 | 05_orbit | 확실 | B 에 씀 |
| `14-1011-gemini-06_dolly.mp4` | 10:11 | gemini omni flash 1 1 | 3.35s | 1080p | 있다 | 18 | 06_dolly | 아마 | B 에 씀 |
| `15-1011-gemini-x.mp4` | 10:11 | gemini omni flash 1 1 | 3.35s | 1080p | 있다 | 18 | ? | 못 맞춤 | B 에 씀 |
| `16-1012-gemini-00_foot.mp4` | 10:12 | gemini omni flash 1 1 | 0.68s | 1080p | 있다 | 4.5 | 00_foot | 확실 | B 에 씀 |
| `17-1018-gemini-03_lead.mp4` | 10:18 | gemini omni flash 1 1 | 0.85s | 1080p | 있다 | 4.5 | 03_lead | 아마 | B 에 씀 |
| `18-1018-gemini-01_side.mp4` | 10:18 | gemini omni flash 1 1 | 0.68s | 1080p | 있다 | 4.5 | 01_side | 아마 | B 에 씀 |
| `19-1036-gemini-00_foot.mp4` | 10:36 | gemini omni flash 1 1 | 0.68s | 1080p | 있다 | 4.5 | 00_foot | 확실 | B 에 씀 |
| `20-1048-gemini-05_orbit.mp4` | 10:48 | gemini omni flash 1 1 | 0.85s | 1080p | 있다 | 4.5 | 05_orbit | 아마 | B 에 씀 |
| `21-1114-seedance-dune-06_dolly.mp4` | 11:14 | seedance 2 5 | 4.04s | 1080p | 없다 | 36 | 06_dolly | 확실 | 버렸다 |
| `22-1122-seedance-dune-03_lead.mp4` | 11:22 | seedance 2 5 | 3.71s | 1080p | 없다 | 36 | 03_lead | 확실 | 버렸다 |
| `23-1122-seedance-dune-00_foot.mp4` | 11:22 | seedance 2 5 | 3.71s | 1080p | 없다 | 36 | 00_foot | 확실 | 버렸다 |
| `24-1154-gemini-06_dolly_grid.mp4` | 11:54 | gemini omni flash 1 1 | 3.35s | 1080p | 있다 | 18 | 06_dolly_grid | 아마 | B 에 씀 |
| `25-1229-seedance-00_foot.mp4` | 12:29 | seedance 2 5 | 3.71s | 1080p | 없다 | 36 | 00_foot | 확실 | 버렸다 |
| `26-1308-nano-tone-04_underfoot.png` | 13:08 | nano banana 2 | 2752x1536 | 2k | 없다 | 2 | 04_underfoot | 확실 | 버렸다 |
| `27-1308-nano-tone-03_lead.png` | 13:08 | nano banana 2 | 2752x1536 | 2k | 없다 | 2 | 03_lead | 확실 | 버렸다 |
| `28-1308-nano-tone-05_orbit.png` | 13:08 | nano banana 2 | 2752x1536 | 2k | 없다 | 2 | 05_orbit | 확실 | 버렸다 |
| `29-1308-nano-tone-07_rise.png` | 13:08 | nano banana 2 | 2752x1536 | 2k | 없다 | 2 | 07_rise | 확실 | 버렸다 |
| `30-1308-nano-tone-06_dolly.png` | 13:08 | nano banana 2 | 2752x1536 | 2k | 없다 | 2 | 06_dolly | 확실 | 버렸다 |
| `31-1308-nano-tone-01_side.png` | 13:08 | nano banana 2 | 2752x1536 | 2k | 없다 | 2 | 01_side | 확실 | 버렸다 |
| `32-1308-nano-tone-02_aisle.png` | 13:08 | nano banana 2 | 2752x1536 | 2k | 없다 | 2 | 02_aisle | 확실 | 버렸다 |
| `33-1308-nano-tone-00_foot.png` | 13:08 | nano banana 2 | 2752x1536 | 2k | 없다 | 2 | 00_foot | 확실 | 버렸다 |
| `34-1341-nano-tone-02_aisle.png` | 13:41 | nano banana 2 | 2752x1536 | 2k | 없다 | 2 | 02_aisle | 확실 | 버렸다 |
| `35-1341-nano-tone-02_aisle.png` | 13:41 | nano banana 2 | 2752x1536 | 2k | 없다 | 2 | 02_aisle | 확실 | 버렸다 |
| `36-1341-nano-tone-02_aisle.png` | 13:41 | nano banana 2 | 2752x1536 | 2k | 없다 | 2 | 02_aisle | 확실 | 버렸다 |
| `37-1355-nano-opening.png` | 13:55 | nano banana 2 | 2752x1536 | 2k | 없다 | 2 | - | - | 버렸다 |
| `38-1355-nano-opening.png` | 13:55 | nano banana 2 | 2752x1536 | 2k | 없다 | 2 | - | - | 버렸다 |
| `39-1548-seedance-02_aisle.mp4` | 15:48 | seedance 2 5 | 3.71s | 1080p | 없다 | 36 | 02_aisle | 확실 | **A 에 씀** |
| `40-1548-seedance-05_orbit.mp4` | 15:48 | seedance 2 5 | 3.71s | 1080p | 없다 | 36 | 05_orbit | 확실 | **A 에 씀** |
| `41-1548-seedance-03_lead.mp4` | 15:48 | seedance 2 5 | 3.71s | 1080p | 없다 | 36 | 03_lead | 확실 | **A 에 씀** |
| `42-1548-seedance-04_underfoot.mp4` | 15:48 | seedance 2 5 | 3.71s | 1080p | 없다 | 36 | 04_underfoot | 확실 | **A 에 씀** |
| `43-1548-seedance-00_foot.mp4` | 15:48 | seedance 2 5 | 3.71s | 1080p | 없다 | 36 | 00_foot | 확실 | **A 에 씀** |
| `44-1548-seedance-01_side.mp4` | 15:48 | seedance 2 5 | 3.71s | 1080p | 없다 | 36 | 01_side | 확실 | **A 에 씀** |
| `45-1556-seedance-07_rise.mp4` | 15:56 | seedance 2 5 | 4.04s | 1080p | 없다 | 36 | 07_rise | 확실 | 버렸다 |
| `46-1556-seedance-06_dolly.mp4` | 15:56 | seedance 2 5 | 3.71s | 1080p | 없다 | 36 | 06_dolly | 확실 | **A 에 씀** |
| `47-1616-seedance-rise-retry.mp4` | 16:16 | seedance 2 5 | 4.04s | 1080p | 없다 | 36 | 07_rise | 확실 | **A 에 씀** |
