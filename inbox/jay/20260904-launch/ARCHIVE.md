# 힉스필드에 남아 있는 생성물 전량

> 분류: 조사
> 근거: 실측. `show_generations` 목록에 전건을 내려받아 직접 쟀다
> 요지: 영상 29건이 남아 있고 URL 이 영구라 바로 열린다. 팀장이 지목한 셋(깔끔한 것 · Dune 톤 · 일렬 보행)이 무엇인지 다 찾았다. 그리고 gemini 오디오를 원본 길이로 재니 우리 사운드와 성질이 반대다.
> 상태: 조사 완료. 아무것도 걸지 않았다

## URL 은 영구다

`d8j0ntlcm91z4.cloudfront.net` 이고 **서명이 없다.** `HTTP 206` 으로 부분 요청도 받는다.
팀장이 링크를 그대로 열면 된다. 만료 시각이 붙어 있지 않다.

원본은 **`library/` 에 47건 전량**을 내려받아 두었다. 저장소에는 안 넣는다(343 MB).
목록은 `library/INDEX.md` 이고 프롬프트 전문은 `library/prompts.json` 이다.
`python scripts/fetch-library.py` 로 언제든 다시 받는다. 크레딧이 안 든다.

## 팀장이 지목한 셋

### 「일렬로 걷는 새 컷도 있는데 왜 안 썼나」

**`02b81e90` 이다.** A 여덟 컷 배치의 `07_rise` 1차 변환본이다.
[열기](https://d8j0ntlcm91z4.cloudfront.net/user_2vTkMQm9Kz0TWEHiovxqGSzlE6v/hf_20260904_064856_02b81e90-3d59-4d19-8d34-45b0e3d9e2f4.mp4)

**내가 버렸다.** 이유는 이것이다. 원본 `07_rise` 는 격자 전체를 위에서 내려다보며
올라가는 컷인데 모델이 지면 높이에서 한 줄로 늘어선 행렬로 바꿔 놓았다.
23초 판에서 그 자리는 「수천 대가 격자로 선다」를 보여야 하는 자리였고,
한 줄이 되면 그 전제가 깨진다고 봤다. 그래서 구도를 못 박아 다시 걸었다(36 크레딧).

**그 판단은 23초 구조에서는 맞았지만 43초 17컷 구조에서는 다시 봐야 한다.**
컷이 열일곱 개면 「대군이 격자로 선다」와 「한 줄로 지평선까지 이어진다」가
같이 들어갈 자리가 있다. 오히려 한 줄 행렬은 승이나 전에서 규모를 다르게 보여 준다.
그림 자체는 좋다. 버릴 이유가 구조에 있었지 그림에 있지 않았다.

### 「Dune 판 톤이 더 좋다」

**넷이다.** 11:14 에서 12:29 사이에 건 시험이고 전부 seedance 다.
프롬프트에 `Dune Part Two desert battlefield` 절이 들어간 것이 이 넷뿐이다.

| id | 컷 | 열기 |
|---|---|---|
| `aa6b571a` | 06_dolly | [열기](https://d8j0ntlcm91z4.cloudfront.net/user_2vTkMQm9Kz0TWEHiovxqGSzlE6v/hf_20260904_022250_aa6b571a-16ba-4b31-a3ba-6e37e0c40f5e.mp4) |
| `736f5696` | 03_lead | [열기](https://d8j0ntlcm91z4.cloudfront.net/user_2vTkMQm9Kz0TWEHiovxqGSzlE6v/hf_20260904_022250_736f5696-e91f-4b4b-a1a5-4ba0ab5c3cd7.mp4) |
| `be2906a1` | 00_foot | [열기](https://d8j0ntlcm91z4.cloudfront.net/user_2vTkMQm9Kz0TWEHiovxqGSzlE6v/hf_20260904_021425_be2906a1-b6a4-4c9c-a0f5-a2d16d4d1a17.mp4) |
| `9786e5e6` | 00_foot 재시도 | [열기](https://d8j0ntlcm91z4.cloudfront.net/user_2vTkMQm9Kz0TWEHiovxqGSzlE6v/hf_20260904_032919_9786e5e6-7ea1-4c3a-9b8e-52ad2e79d54b.mp4) |

**144 크레딧이고 전부 버렸다.** 나란히 놓은 것이 `evidence/archive/discarded.jpg` 다.
역광 먼지에 실루엣이 서 있고 완성본보다 세다. 팀장 말이 맞다.

버린 이유가 기록에 없다. 이 넷을 걸고 나서 프롬프트에서 `Dune Part Two` 절을
빼고 「moderate haze · soft highlights · filmic rolloff」로 바꿨다. 아마 과노출을
잡으려던 것으로 보이는데 **짐작이라 근거로 쓰면 안 된다.** 기록이 없다는 것이 사실이다.

### 「깔끔한 게 많다」

`show_generations` 에 완료로 남은 것이 29건이고 그중 우리 것이 28건이다
(`80e7f301` 고래는 이전 작업이다). **완성본에 실제로 들어간 것은 8건뿐이다.**
나머지 20건이 남아 있고 다 열린다. 아래 전량 표를 보면 된다.

## 전량 표

`컷` 이 「아마」인 것은 입력 미디어 기록이 없어 **화면 대조로 맞춘 것**이다.
`scripts/match-generation-to-cut.py` 로 구도 상관을 재서 정했다.
원경 컷끼리는 96x54 로 줄이면 비슷해서 `06_dolly` 와 `05_orbit` 이 잘 안 갈린다.
확실한 것만 「확실」로 적었다.

| id | 모델 | 컷 | 길이 | 오디오 | 무엇 | 열기 |
|---|---|---|---|---|---|---|
| `03a67e63` | gemini omni flash 1 1 | 00_foot | 0.68s | 있다 | 본 변환 | [열기](https://d8j0ntlcm91z4.cloudfront.net/user_2vTkMQm9Kz0TWEHiovxqGSzlE6v/hf_20260904_004452_03a67e63-0df6-4d4f-ac08-b8d89ccd2cbb.mp4) |
| `05c995f2` | gemini omni flash 1 1 | 01_side | 0.68s | 있다 | 본 변환 | [열기](https://d8j0ntlcm91z4.cloudfront.net/user_2vTkMQm9Kz0TWEHiovxqGSzlE6v/hf_20260904_011815_05c995f2-d55c-430e-9f3c-9314745d3208.mp4) |
| `11a0a427` | gemini omni flash 1 1 | ? | 4.01s | 있다 | 본 변환 | [열기](https://d8j0ntlcm91z4.cloudfront.net/user_2vTkMQm9Kz0TWEHiovxqGSzlE6v/hf_20260904_003517_11a0a427-043d-4d85-a366-ca50e597e232.mp4) |
| `17c3939d` | gemini omni flash 1 1 | 06_dolly | 3.35s | 있다 | 격자 유지 강화 시험 | [열기](https://d8j0ntlcm91z4.cloudfront.net/user_2vTkMQm9Kz0TWEHiovxqGSzlE6v/hf_20260904_011120_17c3939d-3057-45ee-8b09-9cf13c3e0a1a.mp4) |
| `28f7eae0` | gemini omni flash 1 1 | 00_foot | 0.68s | 있다 | 본 변환 | [열기](https://d8j0ntlcm91z4.cloudfront.net/user_2vTkMQm9Kz0TWEHiovxqGSzlE6v/hf_20260904_013649_28f7eae0-bc7b-4500-86cf-cf4636531d89.mp4) |
| `532fd25e` | gemini omni flash 1 1 | 00_foot | 0.68s | 있다 | 본 변환 | [열기](https://d8j0ntlcm91z4.cloudfront.net/user_2vTkMQm9Kz0TWEHiovxqGSzlE6v/hf_20260904_011252_532fd25e-5025-4eb6-b2eb-58bdff48fe4a.mp4) |
| `6d11568e` | gemini omni flash 1 1 | 05_orbit | 0.85s | 있다 | 본 변환 | [열기](https://d8j0ntlcm91z4.cloudfront.net/user_2vTkMQm9Kz0TWEHiovxqGSzlE6v/hf_20260904_014845_6d11568e-3c2e-4ac8-abf6-aef6c0e7428c.mp4) |
| `74adbab6` | gemini omni flash 1 1 | 02_aisle | 0.68s | 있다 | 본 변환 | [열기](https://d8j0ntlcm91z4.cloudfront.net/user_2vTkMQm9Kz0TWEHiovxqGSzlE6v/hf_20260904_011028_74adbab6-75f2-42bc-8210-5ef19f906a59.mp4) |
| `97609734` | gemini omni flash 1 1 | 06_dolly_grid | 3.35s | 있다 | 격자 유지 시험 | [열기](https://d8j0ntlcm91z4.cloudfront.net/user_2vTkMQm9Kz0TWEHiovxqGSzlE6v/hf_20260904_025425_97609734-8f36-4fc3-bc75-98dca216e4dc.mp4) |
| `c39ea780` | gemini omni flash 1 1 | 06_dolly | 3.35s | 있다 | 본 변환 | [열기](https://d8j0ntlcm91z4.cloudfront.net/user_2vTkMQm9Kz0TWEHiovxqGSzlE6v/hf_20260904_004504_c39ea780-1418-430c-9570-0a89e5a4925d.mp4) |
| `e00512a2` | gemini omni flash 1 1 | ? | 3.35s | 있다 | 격자 유지 강화 시험 | [열기](https://d8j0ntlcm91z4.cloudfront.net/user_2vTkMQm9Kz0TWEHiovxqGSzlE6v/hf_20260904_011137_e00512a2-51ac-40ae-9e5e-39a5685f35ca.mp4) |
| `ec14b2d5` | gemini omni flash 1 1 | 01_side | 0.68s | 있다 | 본 변환 | [열기](https://d8j0ntlcm91z4.cloudfront.net/user_2vTkMQm9Kz0TWEHiovxqGSzlE6v/hf_20260904_011017_ec14b2d5-e7b8-4770-9385-0fb445924598.mp4) |
| `f19880ed` | gemini omni flash 1 1 | 03_lead | 0.85s | 있다 | 본 변환 | [열기](https://d8j0ntlcm91z4.cloudfront.net/user_2vTkMQm9Kz0TWEHiovxqGSzlE6v/hf_20260904_011802_f19880ed-4cba-4bd6-a50d-bc76020a9809.mp4) |
| `f914bdb3` | gemini omni flash 1 1 | 05_orbit | 0.85s | 있다 | 본 변환 | [열기](https://d8j0ntlcm91z4.cloudfront.net/user_2vTkMQm9Kz0TWEHiovxqGSzlE6v/hf_20260904_011107_f914bdb3-c0e2-4a76-b92e-1947b2bbd1d9.mp4) |
| `80e7f301` | image2video | ? | 5.37s | 없다 | 이전 작업. 우리 것 아니다 | [열기](https://d8j0ntlcm91z4.cloudfront.net/user_2vTkMQm9Kz0TWEHiovxqGSzlE6v/213c1707-7fb1-456c-9cdc-5110c0b331b2.mp4) |
| `02b81e90` | seedance 2 5 | 07_rise | 4.04s | 없다 | 본 변환 | [열기](https://d8j0ntlcm91z4.cloudfront.net/user_2vTkMQm9Kz0TWEHiovxqGSzlE6v/hf_20260904_065615_02b81e90-fbf6-4faf-a64a-4eaa46f53055.mp4) |
| `0df9eef0` | seedance 2 5 | 00_foot | 3.71s | 없다 | 본 변환 | [열기](https://d8j0ntlcm91z4.cloudfront.net/user_2vTkMQm9Kz0TWEHiovxqGSzlE6v/hf_20260904_064857_0df9eef0-1c18-4914-b487-db1edea86067.mp4) |
| `2b6f7138` | seedance 2 5 | 07_rise | 4.04s | 없다 | rise 재변환 (구도 고정) | [열기](https://d8j0ntlcm91z4.cloudfront.net/user_2vTkMQm9Kz0TWEHiovxqGSzlE6v/hf_20260904_071605_2b6f7138-9890-4f00-b417-fe23e899612b.mp4) |
| `40a89797` | seedance 2 5 | 02_aisle | 3.71s | 없다 | 본 변환 | [열기](https://d8j0ntlcm91z4.cloudfront.net/user_2vTkMQm9Kz0TWEHiovxqGSzlE6v/hf_20260904_064856_40a89797-e3c8-48c9-89fa-6a91f82dc786.mp4) |
| `62de860e` | seedance 2 5 | 04_underfoot | 3.71s | 없다 | 본 변환 | [열기](https://d8j0ntlcm91z4.cloudfront.net/user_2vTkMQm9Kz0TWEHiovxqGSzlE6v/hf_20260904_064857_62de860e-2a53-472c-9f89-1fbffac6be3e.mp4) |
| `736f5696` | seedance 2 5 | 03_lead | 3.71s | 없다 | **Dune 톤 시험** | [열기](https://d8j0ntlcm91z4.cloudfront.net/user_2vTkMQm9Kz0TWEHiovxqGSzlE6v/hf_20260904_022250_736f5696-9511-4e06-a0f1-33a43065392d.mp4) |
| `8470af96` | seedance 2 5 | ? | 3.71s | 없다 | 본 변환 | [열기](https://d8j0ntlcm91z4.cloudfront.net/user_2vTkMQm9Kz0TWEHiovxqGSzlE6v/hf_20260904_003504_8470af96-5484-4848-a489-14f175112526.mp4) |
| `84a93a8a` | seedance 2 5 | 01_side | 3.71s | 없다 | 본 변환 | [열기](https://d8j0ntlcm91z4.cloudfront.net/user_2vTkMQm9Kz0TWEHiovxqGSzlE6v/hf_20260904_064857_84a93a8a-a28f-411f-a9d0-b777fd8684ad.mp4) |
| `975360ed` | seedance 2 5 | 03_lead | 3.71s | 없다 | 본 변환 | [열기](https://d8j0ntlcm91z4.cloudfront.net/user_2vTkMQm9Kz0TWEHiovxqGSzlE6v/hf_20260904_064856_975360ed-5841-4b3d-b22f-ad7f9b1383b9.mp4) |
| `9786e5e6` | seedance 2 5 | 00_foot | 3.71s | 없다 | 본 변환 | [열기](https://d8j0ntlcm91z4.cloudfront.net/user_2vTkMQm9Kz0TWEHiovxqGSzlE6v/hf_20260904_032919_9786e5e6-913f-4f5d-a6b8-30836a4e380c.mp4) |
| `a312f119` | seedance 2 5 | 05_orbit | 3.71s | 없다 | 본 변환 | [열기](https://d8j0ntlcm91z4.cloudfront.net/user_2vTkMQm9Kz0TWEHiovxqGSzlE6v/hf_20260904_064856_a312f119-0caf-41df-8c48-43b886d9ba27.mp4) |
| `aa6b571a` | seedance 2 5 | 06_dolly | 4.04s | 없다 | **Dune 톤 시험** | [열기](https://d8j0ntlcm91z4.cloudfront.net/user_2vTkMQm9Kz0TWEHiovxqGSzlE6v/hf_20260904_021425_aa6b571a-79f1-43e8-918d-993a8320732d.mp4) |
| `be2906a1` | seedance 2 5 | 00_foot | 3.71s | 없다 | **Dune 톤 시험** | [열기](https://d8j0ntlcm91z4.cloudfront.net/user_2vTkMQm9Kz0TWEHiovxqGSzlE6v/hf_20260904_022250_be2906a1-d21b-4fd6-9664-249847d593b2.mp4) |
| `ce40af3b` | seedance 2 5 | 06_dolly | 3.71s | 없다 | 본 변환 | [열기](https://d8j0ntlcm91z4.cloudfront.net/user_2vTkMQm9Kz0TWEHiovxqGSzlE6v/hf_20260904_065616_ce40af3b-ea7a-4458-957b-a79391f3288d.mp4) |

## 사운드 전용 생성 · 팀장 질문에 대한 답

**단독으로 쓸 수 있는 음악·효과음 생성이 없다.** `generate_audio` 는 음성 전용이다.

`models_explore(type='audio')` 로 여섯이 나온다.

| 모델 | 무엇 | 단독으로 쓸 수 있나 |
|---|---|---|
| `seed_audio` (ByteDance) | 음성 합성. 목소리 참조 가능 | 음성만 |
| `qwen_audio_tts` (Alibaba) | 음성 합성 | 음성만 |
| `text2speech_v2` (Higgsfield) | 음성 합성. 엔진 5종 선택 | 음성만 |
| `sonilo_music` (FAL) | **음악** 생성. 길이 지정 | **안 된다. 게임 파이프라인 전용** |
| `mirelo_text_to_audio` (FAL) | **효과음** 생성. 길이 지정 | **안 된다. 게임 파이프라인 전용** |
| `inworld_text_to_speech` (FAL) | 음성 | 게임 파이프라인 전용 |

도구 설명에 그대로 적혀 있다. 「이 도구는 음성만 만든다. 일반 용도의 음악이나
효과음을 만들 수 없고 여기에 단독 음악·효과음 모델이 없다. `sonilo_music` ·
`mirelo_text_to_audio` · `inworld_text_to_speech` 는 게임 생성 파이프라인 전용이며
단독 오디오에 쓰면 안 된다.」

**그러니 「사운드만 하는 것」으로 우리 사운드를 만들 수는 없다.**

### 대신 길이 있다. 영상 모델이 소리를 낸다

| 모델 | 오디오 |
|---|---|
| `gemini_omni_flash_1_1` | **낸다.** 우리 변환본 14건 전부에 오디오 스트림이 있다 |
| `seedance_2_5` | `generate_audio` 파라미터가 있고 **기본값이 참**이다 |

**우리는 seedance 에 `generate_audio: false` 를 넣어 껐다.** 여덟 컷 전량이 그렇다.

그리고 껐다고 싸지지 않는다. 실측이다.

| 설정 | 크레딧 |
|---|---|
| `video_edit` · 1080p · `generate_audio` 참 | **36** |
| `video_edit` · 1080p · `generate_audio` 거짓 | **36** |

**같은 값이다. 공짜로 나오는 것을 우리가 껐다.**

## gemini 오디오를 원본 길이로 쟀다

1초짜리가 0.68초로 나오는 것은 우리가 자른 것이 아니다. **모델이 그 길이로 낸 원본이다.**
`show_generations` 의 결과를 그대로 받아 재도 0.68초다.

| id | 길이 | 20-60Hz | 60-250 | **500-3k** | 3k-8k | 무게중심 |
|---|---|---|---|---|---|---|
| `97609734` | 3.35s | 5.4 % | 9.5 % | **75.1 %** | 1.9 % | 883 Hz |
| `e00512a2` | 3.35s | 6.3 % | 46.1 % | **38.2 %** | 0.5 % | 369 Hz |
| `17c3939d` | 3.35s | 12.4 % | 24.8 % | **33.1 %** | 13.7 % | 1384 Hz |
| `c39ea780` | 3.35s | 1.6 % | 10.7 % | **60.1 %** | 9.7 % | 1387 Hz |
| `11a0a427` | 4.01s | 6.2 % | 13.7 % | **49.1 %** | 8.1 % | 1150 Hz |
| 3초 넘는 것 평균 | | | | **51.1 %** | | 1035 Hz |
| **우리 A 판 걷기** | | | | **1.1 %** | | **80 Hz** |
| **우리 A 판 엔딩** | | | | 8.2 % | | 117 Hz |

**팀장이 좋다고 한 소리가 우리가 낮추려던 그 대역이다.** 앞서 「피치가 높다」를
500-3000 Hz 문제로 잡고 그 대역을 내리는 판(v1 · v2)을 만들었는데, 그것이
팀장이 좋아하는 쪽에서 멀어지는 방향이었다.

### 그런데 같은 대역이라도 성질이 반대다

비중만으로는 「지속하는 음정」과 「두드리는 질감」이 안 갈린다. 갈라서 쟀다.

  스펙트럼 평탄도  0 에 가까우면 음정 · 1 에 가까우면 잡음

| 무엇 | 평탄도 | 성질 |
|---|---|---|
| gemini `17c3939d` | 0.481 | **잡음** |
| gemini `c39ea780` | 0.493 | **잡음** |
| gemini `11a0a427` | 0.421 | **잡음** |
| gemini `97609734` | 0.051 | 중간 |
| gemini `e00512a2` | 0.031 | 중간 |
| **우리 걷기** | **0.011** | **음정** |
| **우리 엔딩** | **0.038** | 음정에 가깝다 |

**gemini 의 중역은 바람과 자갈과 공기다. 우리 중역은 사람이 낸 음정이다.**
같은 500-3000 Hz 인데 하나는 환경음이고 하나는 무언 보컬 패드다.

이것이 「피치가 높다」와 「저런 발자국 소리랑 백그라운드 소리」가 동시에
성립하는 이유다. 팀장은 **중역을 줄이라는 것이 아니라 음정을 빼라는 것**이다.

### 그래서 내 앞 처방이 틀렸다

앞서 낸 v1 · v2 는 엔딩 보컬 포먼트를 내려 500-3000 Hz 를 20.4 에서 4.4 퍼센트로
떨어뜨렸다. **방향이 반대다.** 대역을 줄이는 것이 아니라 **그 대역을 음정에서
잡음으로 바꾸는 것**이 맞다. 평탄도 0.011 을 0.4 쪽으로 올리는 일이다.

구체적으로는 3층 무언 보컬 패드(포먼트 700 · 1200 · 2600 Hz)를 빼고 그 자리에
광대역 환경음을 넣는 것이다. 바람 · 흙 · 자갈 · 먼 울림이다.

### 그리고 우리 사운드 기준 자체가 그것을 막고 있었다

`SOUND-CRITERIA.md` 의 3번과 4번이 **우쉬 2k-12k 를 3 퍼센트 이상 요구한다.**
우쉬는 4층이고 팀장이 싫다고 한 두 소리 중 하나다. 기준이 그것을 강제하고 있었다.

기준을 다시 짜야 한다. 지금 아홉 항목은 「듄처럼 무겁게」를 재도록 만든 자였고
팀장이 원하는 것은 그것과 다르다. 새 기준의 후보는 이렇다.

- 500-3000 Hz **비중**이 아니라 그 대역의 **평탄도**를 잰다 (음정이 아닌가)
- 발자국 격자 208 ms 는 그대로 둔다. 이것은 팀장이 문제 삼지 않았다
- 우쉬 하한을 없앤다. 팀장이 싫어하는 소리를 자가 강제하면 안 된다

## 아직 못 맞춘 것

`e00512a2` 는 구도 상관이 최대 0.125 로 낮아 어느 컷인지 못 맞췄다.
`11a0a427` 과 `8470af96` 은 입력 미디어 id 가 `ecd94233` 인데 이 id 가 어느
업로드인지 기록에 없다. 앞 세션에서 올린 것이다.

