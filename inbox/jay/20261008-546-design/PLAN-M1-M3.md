# M1 · M3 실행 계획: 영상 faststart 재포장 · 배포 뒤 바깥 경로 재생 관문

> 분류: 계획
> 작성: 오흥재 · 2026-10-09
> 근거: 10/8~10/9 lead 실측 (NAS mp4 원자 구조 전수 · 헤드리스 Chrome 재생 시작 시간 · ffmpeg 재포장 시험) · `web/_build/build.py` · `web/_build/media_offload.py`
> 요지: M1 은 빌드 안에서 배포본 mp4 를 화질 그대로 faststart 로 재포장하고 «moov 가 끝인 mp4 0개» 를 관문으로 건다. M3 은 배포 뒤 바깥 경로로 「함께 재생」 시작 시간을 재서 기록한다. 둘 다 Funnel 대역 제한을 고치지는 못한다(M2 몫)
> 상태: 계획 · ASTRA 검증 전 · 팀장 진행 지시(10/9)

## 1. 사실

| 항목 | 값 | 근거 |
|---|---|---|
| NAS mp4 | 345개 · 609 MB. faststart 247 · **moov 가 끝 98개(110.1 MB)** | NAS `media/site` 전수 원자 판별 (`_out/tools/mp4probe.py` 와 같은 판별) |
| 98개의 원본 위치 | 전부 `foothold-lab/web/` 아래. git 추적 50 · 추적 밖 48. foothold-site 에만 있는 것 0 · NAS 에만 있는 것 0 | 경로 대조 |
| 빌드 순서 | `deploy()` 가 web → foothold-site 복사 → `[3.05] media_offload` (sha256 대조로 NAS 에 올리고 배포본에서 뺌) → `[3.06] image_slim` | `build.py` 221 · 785~794행 |
| 재포장 시험 | ffmpeg 9.0.2 `-map 0 -c copy -movflags +faststart -fflags +bitexact`. 같은 입력 두 번 → **같은 sha**. 영상 패킷(크기 · pts) 목록 md5 원본과 **같음**. moov 가 mdat 앞으로 | `axis2-hold-nvidia.mp4` 한 개 |
| 바깥 경로 효과 | 같은 파일, 헤드리스 Chrome, 공개 IP 고정, 클릭 → 0.3 초 움직임까지 3회: 원본 **8.6 · 8.6 · 12.6 초** → faststart **7.1 · 7.3 · 8.1 초** | NAS `_m1test/` 에 잠깐 올려 잼 · 잰 뒤 지움 |

**해석:** faststart 는 1.3~4.5 초를 줄인다. 그래도 7 초대가 남는다. 남는 대부분은 Funnel 의 첫 연결 · 첫 바이트(3~4 초)와 대역(50 KB/s~1 MB/s)이다. M1 · M3 만으로 휴대폰 지연은 안 풀린다.

## 2. M1 · 빌드 안 faststart 재포장

**자리:** 새 `web/_build/video_faststart.py`, `build.py` 에 `[3.04]` 로 `deploy()` 뒤 · `media_offload` 앞.

**원본 `web/` 은 고치지 않는다.** 까닭 둘: git 추적 바이너리 50개(합 수십 MB)를 다시 커밋하면 저장소가 그만큼 커진다. 그리고 다른 세션이 영상을 새로 렌더하면 다시 moov 가 끝으로 돌아온다. 빌드가 매번 고치면 원본이 어떻든 배포본은 늘 faststart 다.

**하는 일**
1. 배포본의 `.mp4` 를 모두 원자 순서로 판별한다(파일을 다 읽지 않고 상자 머리만).
2. moov 가 mdat 뒤면: 입력 sha256 으로 캐시 `_out/cache/faststart/<sha>.mp4` 를 찾고, 없으면 위 ffmpeg 명령으로 만든다.
3. 만든 것을 검증한다: moov 가 앞 · 스트림 수 같음 · 스트림마다 패킷(크기 · pts) 목록 해시 같음 · 길이 같음. 하나라도 다르면 **빌드 실패**.
4. 배포본 파일을 교체한다. 그 뒤 `media_offload` 가 sha 가 바뀐 것을 NAS 로 올린다(첫 빌드만 98개 · 약 110 MB). `MANIFEST.sha256` 갱신.

**관문**
- 단계가 끝난 뒤 배포본 mp4 중 moov 가 끝인 것 **0개**. 아니면 실패.
- ffmpeg · ffprobe 가 없으면 실패하고 설치 안내를 찍는다.
- 「★ 이 관문이 «못 잡는 것»」(gatepolicy [3.441]): 원자 구조가 깨진 파일 · fragmented mp4(moof) · `.webm` · `.mov` · `.m4v` (mp4 만 본다) · 재생 속도 자체(서버 몫) · 영상 내용이 맞는지.

**자기시험 (알려진 답 먼저)**
1. ffmpeg 로 2초짜리 moov-끝 표본을 만들어 재포장 → faststart 판정 · 패킷 해시 동일.
2. 이미 faststart 인 표본은 건드리지 않음(파일 sha 그대로).
3. **관문 깨기:** 재포장 단계를 건너뛴 배포본(moov-끝 1개 남김)에서 관문이 실패하는지.
4. **검증 깨기:** 패킷 하나를 바꾼 가짜 출력을 넣었을 때 3번 검증이 실패하는지.

**되돌리기:** `build.py` 의 `[3.04]` 한 줄을 지우면 다음 빌드에서 media_offload 가 원본 sha 를 NAS 에 다시 올린다.

## 3. M3 · 배포 뒤 바깥 경로 재생 관문

**자리:** 새 `web/_build/live_media_check.py`. 빌드가 아니라 **배포가 끝난 뒤** 돈다(빌드 시점에는 새 배포가 아직 없다).

**하는 일**
1. foothold-site 최신 커밋의 Vercel 배포가 `success` 인지 `gh api repos/foothold-project/foothold-site/deployments` 로 확인한다(curl 로 사이트를 두드리지 않는다 · 봇 차단).
2. `vercel.json` 의 미디어 돌림 목적지 호스트를 읽어 **공개 DNS(DoH)** 로 푼 IP 를 헤드리스 Chrome `--host-resolver-rules` 로 고정한다. 테일넷 MagicDNS(100.80.160.84)를 비켜 휴대폰과 같은 길을 탄다.
3. 대표 화면 셋에서 실제 마우스 클릭으로 재생하고, **클릭부터 칸마다 currentTime > 0.3 초까지** 와 오류 코드를 잰다.
   - `/gallery/axis2?scenario=hold` 「함께 재생」 3칸
   - `/report-v2` 첫 영상 1칸
   - `/gallery/view` 첫 비교 「함께 재생」
4. `_out/media-check/<날짜>.jsonl` 에 배포 sha · 경로 · 칸별 시간 · 오류를 남긴다.

**기준(제안 · 팀장 결정):** 칸마다 3 초 이하 · 오류 0. 지금 Funnel 로는 반드시 넘으므로 **M2 전까지 «기록» 모드**(실패를 찍되 막지 않음), M2 뒤 «실패» 모드.

**자기시험 (알려진 답 먼저)**
1. 테일넷 경로 + `--disable-features=LocalNetworkAccessChecks` → 3칸 0.3~0.45 초 (10/8 실측값) → 통과.
2. 없는 영상 주소를 가리킨 화면 → 오류로 실패.
3. 기준을 0.01 초로 낮추면 실패하는지(관문 깨기).

**덧붙여 기록만:** 테일넷 경로 + 새 프로필(로컬 네트워크 접근 차단 켬) 결과. 10/8 에는 3칸 모두 error 4 즉시. M2 뒤에는 사라져야 한다.

**못 잡는 것:** 실제 휴대폰 망(LTE 지연 · 손실) · iOS Safari · 팀장 기기 Chrome 의 로컬 네트워크 허용 상태 · 대표 셋 밖 화면 · Funnel 공개 IP 가 바뀐 경우(DoH 로 매번 풀어 줄인다).

**빈도:** 배포마다 한 번. 폴링으로 두드리지 않는다.

## 4. 검증 받을 물음

- M1 을 빌드 안에서 하는 것이 원본 수정보다 나은가. 놓친 위험(빌드 시간 · 캐시 · NAS 재업로드 · 재현 모드 `write=False`)이 있는가.
- 패킷 해시 대조가 «화질 그대로» 를 보증하기에 충분한가.
- M3 를 «기록» 모드로 시작하는 것이 관문 원칙에 맞는가.
- 둘 다 M2 와 부딪히는 곳(호스트가 바뀌면 M3 의 IP 고정 · M1 결과물의 업로드 대상)이 있는가.
