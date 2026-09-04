# 힉스필드 MCP 로 무엇이 되는가 · 런칭 영상 관점에서

> 분류: 리서치
> 작성: 오흥재 · 2026-09-04 09:35
> 근거: 실측
> 요지: 힉스필드 MCP 도구 목록을 전수로 읽고 런칭 영상에 쓸 것과 못 쓸 것을 가른다. 영상 변환은 되고 음악과 효과음은 안 된다.
> 상태: 초안
> 판: v1.0

도구 116개가 붙어 있다. 그중 이 작업에 닿는 것만 추린다.

근거 표기를 붙인다. 크레딧 단가와 도구 목록은 `get_cost` · `models_explore` 응답을 그대로 받은
`확인됨` 이다. 뒤쪽 「이렇게 하자는 제안」 의 소요 크레딧은 계산값이라 `추측` 이다.

## 계정

| | |
|---|---|
| 잔액 | 980 크레딧 |
| 요금제 | plus |
| 무제한 생성 | 없음 (`unlim.available` 이 false) · `확인됨` |

## 1. 영상 변환 · 우리가 쓸 것

러프컷을 통째로 넣어 배경과 질감만 바꾸는 길이 있다.
「video edit」 이라는 모드다. 원본 영상을 참조로 넣고 프롬프트로 바꿀 것만 지시한다.

| 모델 | 모드 | 길이 | 해상도 | 실측 단가 |
|---|---|---|---|---|
| `seedance_2_5` | `video_edit` | 원본 길이대로 과금 | 480p · 720p · 1080p | 1080p 초당 9.0 · 720p 초당 6.5 |
| `gemini_omni_flash_1_1` | `edit` | 원본 길이. 30초 상한 | 360p · 720p · 1080p · 4k | 1080p 초당 4.5 · 4k 초당 9.0 |
| `wan3_0` | 참조 입력 | 2초에서 30초 | 480p · 720p · 1080p | 1080p 초당 5.5 |
| `hf_mult_replace_object` | 겐주츠 | 원본 길이 | 480p · 720p · 1080p | 참조 영상 없이는 견적 거부 |

프리플라이트 응답 그대로다. 전부 `확인됨` 이다.

```
seedance_2_5  video_edit 1080p 12초 -> 108 크레딧
seedance_2_5  video_edit 1080p  4초 ->  36 크레딧
seedance_2_5  video_edit  720p  4초 ->  26 크레딧
gemini_omni_flash_1_1 edit 1080p 5초 ->  22.5 크레딧
gemini_omni_flash_1_1 edit   4k  5초 ->  45 크레딧
wan3_0                     1080p 5초 ->  27.5 크레딧
```

**우리가 손댈 구간은 0.00 에서 10.00초, 딱 10초다.** formation 과 타이틀은 금지다.
그러면 전량 변환 비용이 이렇게 나온다.

| 방식 | 계산 | 크레딧 | 잔액 대비 |
|---|---|---|---|
| gemini 1080p 10초 | 4.5 x 10 | 45 | 4.6 퍼센트 |
| seedance 720p 10초 | 6.5 x 10 | 65 | 6.6 퍼센트 |
| seedance 1080p 10초 | 9.0 x 10 | 90 | 9.2 퍼센트 |

한 번에 다 태워도 10퍼센트를 안 넘는다. 시험 컷 몇 번을 돌려도 여유가 있다.
위 표는 단가에 길이를 곱한 계산이라 `추측` 이다. 최소 과금 길이가 있으면 올라간다.

## 2. 사운드 · 여기가 막힌다

**힉스필드에는 쓸 수 있는 음악 생성도 효과음 생성도 없습니다.**

오디오 모델이 6개인데 성격이 이렇게 갈린다.

| 모델 | 무엇 | 우리에게 |
|---|---|---|
| `seed_audio` | 바이트댄스 음성 합성 | 나레이션용. 음악 아님 |
| `qwen_audio_tts` | 알리바바 음성 합성 | 나레이션용 |
| `text2speech_v2` | 일레븐랩스 등 5개 엔진 음성 | 나레이션용 |
| `sonilo_music` | 텍스트에서 음악 | **게임 파이프라인 전용. 단독 사용 금지** |
| `mirelo_text_to_audio` | 텍스트에서 효과음 | **게임 파이프라인 전용. 단독 사용 금지** |
| `inworld_text_to_speech` | 음성 | **게임 파이프라인 전용. 단독 사용 금지** |

뒤 셋은 카탈로그 설명에 「Game pipeline only」 라고 박혀 있고,
`generate_audio` 도구 자체가 「단독 오디오로 이 셋을 쓰지 말고 요청을 거절하라」 고 지시한다.
우회할 구멍을 찾지 않았다. 규칙대로 안 쓴다.

영상 모델의 `generate_audio` 옵션은 있다. 다만 그것은 그 영상에 붙어 나오는 소리라
우리가 원하는 「144 BPM 격자에 정확히 앉은 사운드 디자인」 을 만들 수 없다.
발 접지 208 ms 에 펄스를 맞춰야 하는데 모델이 그 격자를 지킬 근거가 없다.

### 그래서 사운드는 직접 합성한다

이게 오히려 맞다. 우리 숫자는 전부 실측이다.

| 값 | 출처 |
|---|---|
| 지배 주파수 4.805 Hz | foot 컷 프레임차 FFT |
| 발 접지 간격 208 ms | 4.805 Hz 의 역수 |
| 보행 주기 2.40 Hz | 트롯 대각 두 쌍 |
| 템포 144 BPM | 8분음표가 4.8 Hz |

넘파이로 파형을 만들고 ffmpeg 으로 붙이면 샘플 단위로 격자에 앉는다.
생성 모델에 맡기면 못 맞추는 정확도다. 크레딧도 안 든다.

## 3. 그 밖에 붙어 있는 것

당장 안 쓰지만 있다는 것은 적어 둔다.

| 갈래 | 도구 |
|---|---|
| 화질 올리기 | `topaz_video` · `bytedance_video_upscale` (4k 까지) · `video_upscale` |
| 흔들림 잡기 | `video_deflicker` |
| 배경 빼기 | `sam_3_video` · `video_background_remover` |
| 화면비 바꾸기 | `reframe` (세로 컷 필요하면) |
| 이미지 | `nano_banana_pro` · `soul_2` 등. 배경 판 만들 때 |
| 3D | `generate_3d` |
| 립싱크 | `sync_so` |

`reframe` 은 발표 뒤 SNS 세로 버전을 만들 때 쓸 만하다. 지금은 아니다.

## 4. 파일 넣는 법

로컬 영상을 넣는 경로가 확인됐다.

1. `media_upload` 로 서명된 PUT 주소를 받는다
2. curl 로 바이트를 올린다
3. `media_confirm` 으로 확정한다
4. 받은 `media_id` 를 `medias[].value` 에 넣는다

이 컴퓨터에 curl 8.18.0 이 있다. 실제로 올려 봤다. `확인됨`

## 5. 로컬 도구

| | |
|---|---|
| ffmpeg | 7.1. `anaconda3/envs/isaac311/Lib/site-packages/imageio_ffmpeg/binaries/` 안에 있다. PATH 에는 없다 |
| python | 3.13.9. numpy · scipy · PIL 있음 |

러프컷을 다시 재 보니 20.36초 · 1920x1080 · 50 fps · 오디오 트랙 없음이다. `확인됨`
이 값은 v5 기준이다. 그 뒤 v6 과 v7 로 바뀌었다. `TEST-RESULTS.md` 와 `README.md` 를 보라.

## 6. 그래서 이렇게 하자는 제안

| 단계 | 무엇 | 도구 | 크레딧 |
|---|---|---|---|
| 시험 | 컷 하나만 변환해 결이 맞는지 본다 | `seedance_2_5` video_edit | 20에서 40 |
| 그림 | 0.00에서 10.00초 험지 변환 | 승인된 모델 | 45에서 90 |
| 색 | 컷별 밝기 하강을 유지하며 브랜드 톤 | ffmpeg | 0 |
| 소리 | 실측 격자에 맞춘 합성 | numpy 와 ffmpeg | 0 |
| 조립 | formation 과 타이틀은 원본 그대로 | ffmpeg | 0 |

시험 컷은 `foot` 이 좋다. 0.625초로 짧고 다리가 크게 잡혀서
「로봇 형태가 유지되는가」 를 가장 빨리 판별할 수 있다.
다만 video edit 모델의 최소 과금 길이가 있을 수 있어 4초 안팎이 될 수도 있다.

## 출처

이 문서가 읽거나 잰 것들이다.

- 러프컷 v8 · [`inbox/jay/20260904-roughcut/README.md`](../20260904-roughcut/README.md)
- 컷 구성의 원본 · [`inbox/jay/20260904-roughcut/scripts/build-roughcut.py`](../20260904-roughcut/scripts/build-roughcut.py)
- 연출 10컷 원본 · [`sim/eval/results/20260903-flat-army-cine/`](../../../sim/eval/results/20260903-flat-army-cine/)
- FOOTHOLD 대형 · [`sim/eval/results/20260904-flat-army-formation/README.md`](../../../sim/eval/results/20260904-flat-army-formation/README.md)
- 엔딩 타이틀 · [`inbox/jay/20260903-ending-title/README.md`](../20260903-ending-title/README.md)
- 브랜드 정본 토큰과 사용 정책 · `foothold-brand/tokens/foothold.tokens.json` · `foothold-brand/BRAND_USAGE_POLICY.md`
- 문서 규칙 · [`AGENTS.md`](../../../AGENTS.md)
- 저장소 · https://github.com/foothold-project/foothold-lab
  (러프컷 v6 는 PR #198 · v7 은 PR #200 으로 main 에 들어왔다)
- 쓴 ffmpeg 필터의 정의 · https://ffmpeg.org/ffmpeg-filters.html
  (`eq` 의 gamma 와 saturation · `colorbalance` · `select` · `setpts` · `minterpolate` ·
  `ebur128` · `psnr`. 감마와 프레임 선택의 의미를 이 문서 기준으로 썼다)
- 라우드니스 단위의 정의 · https://tech.ebu.ch/publications/r128
  (LUFS 와 트루 피크. -16 LUFS 목표와 -1 dBFS 상한이 이 단위계다)
- 힉스필드 모델 카탈로그와 단가 · `models_explore` 와 `get_cost` MCP 응답. 이 저장소 밖이라 링크가 없다

## 판 이력

| 판 | 언제 | 무엇이 바뀌었나 | 근거 |
|---|---|---|---|
| v1.0 | 2026-09-04 | 처음 씀 | 도구 목록 전수와 get_cost 프리플라이트 |
