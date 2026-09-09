# A 키비주얼 여덟 장 · 방향 확인용

> 분류: 운영
> 작성: 오흥재 · 2026-09-04
> 근거: 실측
> 요지: 컷마다 대표 프레임 한 장을 듄 2 결로 변환한 1920x1080 정지 이미지 여덟 장.
>       영상이 아니라 이미지로 뽑았다. 훨씬 싸고 훨씬 빠르다.
> 상태: 판단 대기

`graded/` 안의 여덟 장이 판단할 그림이다. 축소하지 않은 1920x1080 이다.

## 실측 비용과 시간

| | 이미지 | 영상 |
|---|---:|---:|
| 건당 크레딧 | **2** (프리플라이트) | 36 |
| 여덟 장 / 여덟 컷 | **16** | 288 |
| 걸린 시간 | **여덟 장 동시에 35초 안** | 영상 1초당 벽시계 36-62초 |

이미지가 18배 싸고 훨씬 빠르다. 방향을 정하는 데는 이쪽이 맞다.
업로드는 원본 여덟 장 9.2 MB 에 35.4초 걸렸다.

**모델.** `nano_banana_pro` 로 요청했는데 서버가 `nano_banana_2` 로 처리해 돌려줬다.
`image_references` 로 원본 프레임을 넣는 image to image 가 된다. 우회가 필요 없었다.

## 밝기 · 여덟 장 다 목표 안에 들어왔다

목표는 **235 초과 2 퍼센트 이하 · 250 초과 0.3 퍼센트 이하**다.

| 컷 | 원본 235초과 | 모델 출력 235초과 | **그레이딩 뒤 235초과** | **250초과** | 평균 |
|---|---:|---:|---:|---:|---:|
| `foot` | 1.220 % | 3.653 % | **0.072 %** | 0.000 % | 129.0 |
| `side` | 0.009 % | 2.352 % | **0.008 %** | 0.000 % | 115.2 |
| `aisle` | 2.474 % | 4.083 % | **0.022 %** | 0.000 % | 127.5 |
| `lead` | 1.182 % | 9.748 % | **0.027 %** | 0.000 % | 122.1 |
| `underfoot` | 1.091 % | 6.737 % | **0.026 %** | 0.000 % | 122.0 |
| `orbit` | 0.055 % | 9.235 % | **0.024 %** | 0.000 % | 124.6 |
| `dolly` | 0.792 % | 6.331 % | **0.010 %** | 0.000 % | 108.6 |
| `rise` | 0.027 % | 2.370 % | **0.039 %** | 0.000 % | 93.2 |

**모델 출력만으로는 여덟 장 다 넘었다.** 2.35 에서 9.75 퍼센트다.
프롬프트에서 haze 를 moderate 로, blown 을 soft 로 낮추고 해를 옆으로 보냈는데도 그렇다.

**2층 ffmpeg 그레이딩을 얹으니 여덟 장 다 들어왔다.** 최대 0.072 퍼센트다.
B 판에 쓴 것과 같은 그레이딩이다. 크레딧이 안 든다.
`graded/` 가 그것이고 이것이 최종 파이프라인의 모습이다. 모델 출력만 보고 판단하면 안 된다.

## 눈으로 본 것

**좋다.** 낮은 해 · 역광 · 안개로 지워진 거리 · 황토와 본 화이트 · 젖빛 검정 ·
바위와 자갈의 미지 지형 · 긴 그림자. 한낮의 평평한 조명이 없어졌다.
`dolly` 는 대군이 지평선까지 뻗고 열이 남아 있다.

**두 가지를 짚어 둔다. 판단에 넣으십시오.**

- **`aisle` 에 「Unitree」 글자가 생겼다.** 앞쪽 로봇 몸통에 모델이 글자를 그려 넣었다.
  원본 프레임에는 없다. 생성 모델이 만든 것이므로 그대로 쓰면 안 된다고 본다.
  프롬프트에 글자 금지를 넣어 다시 걸면 된다. 2 크레딧이다.
- **구도가 원본에서 꽤 벗어난 장이 있다.** `aisle` 은 앞쪽에 큰 로봇이 새로 생겼다.
  키비주얼로는 인상이 강하지만 영상으로 가면 컷 연결이 달라진다.
  영상 변환(`video_edit`)은 이보다 구도를 덜 바꾼다.

## 이것으로 무엇을 정하나

여덟 장을 보고 **A 의 방향**을 정한다. 톤이 이 결로 가면 되는지,
어느 컷을 새로 연출할지, 어느 컷을 그대로 둘지다.

**컨펌 전에는 A 영상 변환을 걸지 않는다.** 전량은 컷 여덟에 288 크레딧이다.

## 다시 만드는 순서

```
python scripts/cut-plan2.py          컷마다 원본 프레임을 뽑는다 (cuts4/)
                                     대표 프레임은 쓰는 구간의 한가운데다
힉스필드 generate_image_batch        image_references 로 image to image
                                     프롬프트는 아래 절에 있다
ffmpeg 2층 그레이딩                  build-launch-b.py 의 GRADE 와 같은 값
```

## 쓴 프롬프트

공통이다.

```
Regrade and redress this frame. Keep every robot exactly where it is:
strict regular rectangular grid, keep the exact number and spacing,
do not merge, remove, duplicate, thin out or displace any robot.
Robots stay pure white, no colour cast on the robots, no green, no teal.
Change only the ground, the sky and the air. The flat grid floor becomes
uncharted hostile terrain: broken rock, gravel, angular stones, wind scoured dirt,
a vast unknown expanse with no landmarks and no path,
the machines are the first thing to ever walk here.
Low sun near the horizon and well off to one side, not in the centre of frame.
Moderate atmospheric haze, soft highlights with gentle filmic rolloff and
no blown white areas, ochre and bone desaturated palette, lifted milky blacks,
airborne dust, fine grain, anamorphic wide.
```

근접 컷(`foot` `side` `aisle` `lead` `underfoot`)에 더한 것.

```
Robots remain clearly visible and readable, rim light on robot bodies,
bounce light filling their shadow side,
do not silhouette the robots into black shapes.
```

부감 컷(`orbit` `dolly` `rise`)에 더한 것.

```
The columns must stay straight all the way to the horizon;
each robot keeps a solid visible body and four distinct legs;
do not blur small distant robots into clumps of legs.
```
