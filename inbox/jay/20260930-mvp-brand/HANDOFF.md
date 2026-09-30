# lead 세션 작업물 구조 기록 (제작 계획서가 아니다)

> 분류: 운영
> 작성: 오흥재 · 2026-10-01
> 근거: 실측 (lead 세션 scratchpad 전수 바이트·해시 대조 · `git check-ignore`)
> 요지: Temp 에 있던 1.1 GB 를 건져 온 기록. **제작 계획은 이 문서가 아니라 `20260929-mvp-presentation/` 의 최신 문서를 따른다**
> 상태: 확정

## 0. 이 문서의 범위 · 먼저 읽을 것

**이 문서는 «건져 온 기록» 이지 제작 계획이 아니다.**

살아 있는 제작 계획은 여기다.

| 무엇 | 어디 |
|---|---|
| **최신 연출** | `inbox/jay/20260929-mvp-presentation/FILM-DIRECTION-20261001.md` |
| **이미지 작업 목록** | 같은 폴더 `FILM-IMAGE-WORKLIST.md` |
| 영상 제작 현황 | 같은 폴더 `FILM-VIDEO-PRODUCTION-20261001.md` |
| 검수 화면 | 같은 폴더 `output/FOOTHOLD-film-storyboard.html` |
| 캐릭터 시트 | 같은 폴더 `output/FOOTHOLD-Go2-character-sheet.html` |
| 이슈 | #490 |

> **★ 내가 처음 쓴 이 문서는 틀렸다.** 2026-10-01 에 첫 판을 쓸 때 컷을
> `s01`~`s1718` 열아홉으로 적었다. 그것은 **2026-09-14 astra 설계 v1.1**
> (아티팩트 「키비주얼 스토리보드 A」) 이고 **이미 폐기된 안**이다.
> 지금 쓰는 컷 이름은 **O 계열(오프닝) · E 계열(엔딩)** 이다.
> 옛 폴더 `20260904-launch` 가 9/16 에 멈춰 있어서 그것을 현재 상태로 읽었다.
> **멈춘 폴더를 최신으로 착각한 것이다.**

## 1. 건져 온 것 `2026-10-01 실측`

lead 세션 작업물이 **저장소에 한 번도 담긴 적이 없었고** OS 임시 폴더에만 있었다.

    원래 자리  C:/Users/AI-WS01/AppData/Local/Temp/claude/
               C--Users-AI-WS01-Desktop-jay----------foothold-lab/
               85e9e940-5633-48ed-a407-2d9aafc96e93/scratchpad/launch_render
    옮긴 자리  inbox/jay/20260930-mvp-brand/_out/launch_render

`85e9e940-…` 는 lead 세션 id 다 (기억 파일의 `originSessionId` 와 같다).

**왜 급했나.** `cleanupPeriodDays` 가 설정돼 있지 않아 기본 30 일이고, 마지막
수정이 9/16 이라 **10 월 중순에 쓸려 나갈 자리**였다.

| | |
|---|---|
| 파일 | 1,279 개 |
| 바이트 | 1,098,031,454 |
| 대조 | 빠진 것 0 · 남는 것 0 · 크기 다른 것 0 |
| 핵심물 sha256 | `full43_snd.mp4` · `build_full43.py` · `render_brand.py` · `s03_block/s03_src_3s_1080p.mp4` · `reveal8k/…` · `band_sweep/…` **여섯 다 같음** |

`_out/` 은 `.gitignore` 가 무는 자리다 (`git check-ignore` 로 확인). 그래서
**깃을 1.1 GB 불리지 않으면서** Temp 삭제에서는 벗어났다. 조립·렌더 코드만
`code/` 로 올려 담는다.

## 2. 무엇이 들어 있나

프리비주얼 시절(9/13~9/16) 산출물이다. **지금 제작의 컷 원본이 아니라 그때의
카메라 블로킹과 참조다.**

| | |
|---|---|
| `full43_snd.mp4` (12.0 MB) | 조립된 43 초 프리비즈 (소리 포함) |
| `reveal8k/…_8192_reveal8k.mp4` (12.7 MB) | 엔딩 상승 · 로고 픽셀 매칭 |
| `band_sweep/…_4096_sweep.mp4` (7.5 MB) | 엔딩 앞 스윕 |
| `s03_block/` · `s03_block3/` (24 MB) | 첫 디딤 Isaac 블로킹 (hfov 33 · 카메라 0.7 m · 하향 45° · Go2 0.6 m/s) |
| `charsheet/` · `charsheet2/` · `charsheet3/` (82 MB) | Isaac 소스 앵글 (캐릭터 시트 입력) |
| `code/build_full43.py` · `code/render_brand.py` | 조립·렌더 코드 |

`full43_seg/` · `climax_seg/` 등 나머지는 구간별 중간 산출물이다.

## 3. 어기면 안 되는 규칙 (기억에서)

- **시나리오 원문이 유일한 기준**
  (`inbox/jay/20260904-launch/design/scenario-direction.md`). 나온 렌더에 맞춰
  연출을 짜맞추면 꼬인다 (9/13 하루를 그렇게 썼다)
- **컷 매핑을 내 추측으로 「바로잡지」 말 것.** sb2 번호 재매핑 금지
- **팀장이 거부한 실험은 되살리지 말고 AI 참조로도 주지 말 것** (프리비즈 오염)
- **프롬프트는 astra 검증 후 사용.** 옛 `prompts.json` 재사용 금지
- Higgsfield 웹 프롬프트 한도 3,000 자. 「camera」 「cage」 는 소품/철망으로
  문자 그대로 그려지므로 **금지어**
- 렌더는 격리 복사본에서만. `sim/eval` 학습 코드 편집 금지
- Isaac 렌더는 **화면용 GPU** 를 쓴다. `CUDA_VISIBLE_DEVICES` 로 가리면 창
  생성에서 조용히 멈춘다

## 4. 내가 확인한 것과 안 한 것

**확인한 것**: 건진 파일의 바이트·해시 대조 · `_out/` 무시 규칙 ·
Higgsfield 잔량 (조회 시점 4,598.5 크레딧 · Plus).

**안 한 것 (미확인)**: `키비주얼 스토리보드 A.html`(이 폴더 · 1,377,467 바이트)이
아티팩트와 같은 판인지 · 건진 산출물 가운데 지금 O/E 계열 제작에 실제로 쓰이는
것이 무엇인지 · 라이브러리 캡처 프레임의 품질.
