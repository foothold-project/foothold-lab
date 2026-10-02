# PPT 최신 작업 인수인계 · ASTRA-MVP → lead

> 분류: 운영
> 작성: ASTRA-MVP · 2026-10-02
> 근거: 사용자 U207 직접 이관 지시 · 현재 작업 파일 · 브라우저 검증
> 요지: 37장 HTML의 최신 구현과 미완료 수정 요구를 lead가 이어받는다.
> 상태: 작업 소유권 이관. 아래 U177 기록은 역사 자료이며 현재 상태로 사용 금지
> 판: v2.0

## 1. 소유권과 바로 읽을 것

사용자가 직접 “지금 하고 있는 작업 'lead'세션에 이관해. 빠짐없이 이관해”라고 지시했다. 원문 전체와 첨부는 **PPT-REVISION-U207.md**. ASTRA-MVP는3쪽 WHY만 바로잡고 이번 전달 후 편집을 중단한다. 과거 “ASTRA가 PPT 직접 제작” 지시를 현재 소유권으로 해석하면 안 된다. 사용자도 lead에서 이어받을 예정이며, 새 세션/다른 HTML로 다시 시작하지 않는다.

작업 디렉터리: `C:/Users/AI-WS01/Desktop/jay/인공지능사관학교/foothold-lab/inbox/jay/20260929-mvp-presentation/`
공유 checkout: `feature/verify-v2-mvp-jay`. 이슈 #490 열림. PR #504는 기존 초안 기록이며 최신 push 상태는 이관 시 미확인. 이번 턴 pull은 up to date. **작업 파일 다수가 미추적/미커밋이며 현재 디스크가 최신이다.** git checkout/reset/clean/전체add 금지. 영상·다른 에이전트 파일이 다수 섞여 있다.100MB 초과 미디어를 git에 넣지 않는다.

읽는 순서:
1. 이 인계서 → PPT-REVISION-U207.md (이번 지시 전문)
2. USER-SPOKEN-NARRATIVE.md, PPT-SPOKEN-FLOW-MAP.md, PPT-INTRO-BRIEF-20261001.md (팀장 원고/질문/다음 이야기)
3. USER-REQUIREMENTS-LOG.md, PPT-REVISION-U205.md, PPT-REVISION-U206.md (누적 요구)
4. PPT-IMPLEMENTATION-STATUS.md, PPT-U206-EVIDENCE.md, PPT-U206-MEDIA-TRIMS.md, PPT-TECHNICAL-SCENE-EVIDENCE.md
5. 실제 HTML/생성기와 VERIFY-U206-20261002.md. 문서의 예전 장수28/34/42/39를 현재로 쓰지 않는다.

## 2. 최신 산출물과 실행 규칙

발표는 **output/FOOTHOLD-MVP-cover.html,37장**. HTML 클릭 발표 후 PDF 출력. PPTX 요청 없음. N메모/P별도발표자창/F전체화면/방향키·Space다음/이전 지원. 같은 슬라이드 안 단계 진행 후 다음 장으로 이동한다. 자동으로 다음 슬라이드 진행 금지. 영상은 진입 자동재생이며 실험은 muted+loop, 전체·브랜드 영화는 원음+비반복이다. 전체 영화는2쪽, 브랜드35쪽, Q&A36쪽, 기획발표 원본 마지막장37쪽.

실행: `python inbox/jay/20260929-mvp-presentation/build_presentation.py`
생성 순서: make_slides → apply_user_story_order → evidence_layouts.enrich → intro_story.revise → scene_revision.refine → research_revision.revise_research → closing_revision.revise_closing → media_u206.revise_media.
CSS/JS는 빌드 때 HTML에 합쳐진다. **출력 HTML만 고치면 재빌드로 사라진다.** `build_cover.py`도 전체덱빌드로 연결했다. 옛 build_layout.py는34장초안이며 실행해서 최신덱을 대체하면 안 된다.

| 수정 대상 | 원본 |
|---|---|
| 도입3~9쪽 | design/scene_revision.py, scene_revision.css, intro_story.py/css |
| 공통 배치/가독성/U206·U207 override | design/presentation_u206.css (로드 순서상 뒤쪽) |
| 10~12쪽 기술 장면 | design/technical_scene.py/css, intro_story.js |
| 연구15~30쪽 | build_presentation.py, design/evidence_layouts.py, research_revision.py/css, deck.css |
|31~37쪽 | design/closing_revision.py/css |
| 영상trim/loop/poster | design/media_u206.py, deck.js |
| 다음·이전·메모·자동재생 | design/deck.js; 상태 API window.footholdDeck.show(index,step), state |

공통1600×900기준, viewport scale. .content img 일반 규칙이 개별 Go2 크기와 충돌했던 전례가 있다. `policy-front`와 print용`policy-v5-print`의 구체적 선택자/명시 크기를 지우지 않는다. 푸터는 하단32px, 일반본문은top201px,bottom90px. 기술 장면/험지/영화는 별도좌표를 쓴다. 상단 제목·섹션·진행선은 전체에서 일관성 유지. 번호만 보지 말고 제목으로 매핑하라.

메모는 build에서 `spoken`/`note`를 deckNotes로 만든다. 표지USER_COVER_NOTES는 사용자의 아기 첫걸음 비유와인사를 보존한다. 이번 새 요구는 **실제 클릭 상태에 맞춰 (클릭)/(넘기기) 표시**를 간단히 삽입하는 것이다. 현재3쪽만 표시했으며 전체메모는 미완료.

## 3. 최신 피드백별 미완료 체크리스트

3쪽만 이번 턴 수정. 나머지는 아직 미수정이므로 완료로 말하지 말 것.

| 페이지/범위 | 해야 할 일 |
|---|---|
|3쪽 WHY| **수정됨**. 세 질문 등장 유지, 그 다음 픽셀변환/상단이동만 제거. stage0 정면Go2,stage1 로봇축소와선·세WHY 상승. 다음은4쪽. 3가지: 왜잘걷는가/왜사족보행인가/왜어려운가. 연구 당위성을 여는 질문이므로 다시 삭제금지. 이전U206의 제거승인 문구보다 이번정정이 우선 |
|10쪽 첫전환| 정면정지Go2 잔상이 턴테이블과 겹치는 것 제거. 현재v4정지→v5canvas,opacitytransition과sharedclone/hidden·visibility를 함께 검사 |
|10쪽 내단계| 설명카드만교체+디졸브가아닌, 같은기체·카메라·자세의 연속움직임. 각 segment 끝/다음 시작 일치. 분해→조립→관절→센서→모듈→명령연결. 기존완료선언 금지 |
|추가모듈3D| 사용자 제작요구. D435i/Orin NX16GB/HESAI-360의 실제메시·장착위치·브래킷부터확인. 공식 CAD/실기자료 확보 후 연속장착렌더. 아직없다. 상상장착을 실물처럼만들면안됨. 공식규격메시없을때근거있는단순형상도사용자와구분필요 |
|전체메모| 클릭/넘기기 텀 표시. 사용자 원고 화제제기→설명→다음질문 흐름 유지 |
|12쪽 병렬학습| 좌측설명박스가영상가림. 영상을작게하거나우측정렬하여서로영역분리. 현재army-film/army-caption좌표확인 |
|16쪽 높이도식| '표면 충돌점 있음' 글씨겹침. 좌측이동 등 실제도식과경계검사 |
|16쪽+1설명| 핵심은 **구멍/바닥미검출 정보를 정책에 알린다**. 단순히 낮은지면처럼보이기위해라고목적을설명하지말기. 코드부호는유지하여설명: 기존miss inf→-inf→clip -1,수정finite +1. 이것은관측인코딩이며별도binary구멍class학습을했다는뜻은아님. 코드와팀장메시지를대조해명확히수정 |
|계보전체15~21| 변경→얻은능력→잃거나남은능력→다음변경필요성. forward_gap10%+전진명령잠금에서이득만보여줬음. 명령을열어회복한것/다시잃은것→omni_gap으로모든방향틈→얻은것/잃은것을실험근거와영상·수치로. 인과분리안된동시변경은한가지원인효과로단정금지 |
|22쪽 평가조건| 빈공간/위쪽쏠림. 의미단위간균형과전체높이배분수정 |
|23쪽16종표| 숫자칸 배경으로채우는막대그래프가에러같음. rr-matrix linear-gradient방식재설계. 상단성공률·기존6종+gap/rails·오른쪽미경험표사이간격,아래여백균형 |
|25쪽 속도그래프| 속도라벨을더아래로내려그래프와간격. speedgroup h3/columns span 확인 |
|27쪽 정지비교| 두영상실제표시크기/프레임/비율동일하게. 원본두영상비율/letterbox차이를왜곡없이일관되게맞춤. 단순width100%만으로완료금지 |
|전체배치| 위쪽쏠림/하단빈칸,글씨·선·로봇·영상서로가림을실제화면으로재검사. 컨텐츠는보존하되단락·기준선·그림크기와상하균형을수정 |
|31쪽3DGS| 작게왼쪽아래넣은이미지를이번사용자캡처로교체하고충분한비중으로배치. 하단설명 '스플랫된 공간의 모습'과'발이 닿는 바닥 충돌 메시'. 캡처 assets/feedback-u207-splat.png. artifact https://claude.ai/artifact/QfEwWXSkhHn2Rafcv9KgYn (이번턴미열람). 시각복원과충돌바닥을구분하고실측축척/실제지면오차/주행검증미완료를지우지말기 |

사용자 평가 기준: 청자가 이 페이지에서 무엇을 이해하는가, 왜 다음 이야기로 가는가. 픽셀/브랜드/Prezi효과는 그 목적을 도와야 함. 의미 없는 애니메이션은 제거하되 기술 설명 동작은 보강. 밀도란 빈곳을 아무카드로메우는것이아닌 실제근거·비교·시각화다. Apple/Samsung 제품설명처럼 선끝이대상·카드테두리에정확히붙고,크기·비례·간격이안정적이어야함. 텍스트로제작행위('정면에서측면으로','몸을둘러보면')를설명하지말고 센서·관절·관측·출력의역할을전달한다.

## 4. 기술 자산과 연속 애니메이션에서 주의할 것

`assets/go2-blender/`에 실제USD/참조메시, geometry-manifest.json, joints-source.json 보존. 원본go2.usd + Props/instanceable_meshes.usd. 시각메시17,회전관절12. 기본센서는몸통메시일부이며추가모듈메시없음.

- v4: go2-technical-v4.blend, go2-front-v4.png, v4-manifest.js, v4-player.js, v4-web-frames, v4-sensor-and-joint-anchors.json. 한 다리hip/thigh/calf,12관절,forward/lateral/yaw 설명.
- v5: go2-continuous-v5.blend, go2-continuous-v5-preview.mp4, v5-manifest.js/json, v5-player.js,289WebP. GO2-V5-USAGE.md에API. states front/three_quarter/four_legs/assembled/side_grid/scan. segments turntable/four_legs/assemble/to_side/scan. Go2V5Player(canvas,base), ready,setState,playSegment,stop.
- 현재10쪽0정면(v4정지),1턴테이블(v5),2네다리분해(v5),3조립(v5)후관절(v4),4접촉,5기본센서(v4),6모듈이미지,7명령(v4). **v4/v5화각·카메라차이가연속성을깬다.** 새v5연속구간또는전환브릿지를제작해야함.
- v5 scan은 같은카메라에서기체와17×11격자렌더. 설명용형상이며실측높이로그가아님. 신경망은SVG,Manim완성아님. Actor/Critic은별도네트워크. Critic이로봇으로입력되고Actor로나오는직렬구조처럼그리지말기.
- 프레임플레이어는RAF첫timestamp가performance.now보다작을수있어elapsed를0이상으로clamp한다. 이를제거하면음수파일요청. 비동기setState/playSegment는seq로취소. pageleaving시v4/v5 stop해야잔상안남음.
- 기존분해는원본모양을유지한강체분리. 내부기어/케이블을추측생성하지않는다. L2외부하우징전체회전은부적절. 내부스캔원리와시각효과구분.
- 모듈이미지: assets/module-d435i-official.png (공식투명),orin-isolated-u206.png,hesai-isolated-u206.png; 후자2개는공식/제품영상참조배경분리imagegen.3D자산아님.
- Higgsfield /Exploded-view,/use-blender 및 blender-scene 지침은 GO2-BLENDER-PRODUCTION.md참고. 설치된연결은새편집전에라이브확인. 이전MCP서버이름higgsfield-use-blender. 실제접속상태는이관시미확인. Blender생성스크립트는 design/ 아래go2관련파일을rg로찾아기존blend로드기준으로수정.

## 5. 데이터·미디어·검증의 기준

핵심근거는PPT-U206-EVIDENCE.md의CSV/run_manifest/per_env경로. 전체16종×3속도×100=모델당4800. 성공1976/4266/4521→41.17/88.88/94.19%. gap·rails는추가학습포함. 공통미학습8종은개발중반복평가했으므로엄격한최종홀드아웃주장금지. d.9 inversepyramid v1.5에서v2생존100%,속도추종3%,종합3%를'넘어졌다'고말하지말기. pit v1.5는NVIDIA학습명령범위밖임도표시한다. 통과=생존∩전진∩속도추종∩방향. foot-air보상0.01/.1/1비교는한가중치보편우월주장아님.

실험원본: `../20260929-mvp-submission/source/media/`,기타sim/eval/results와docs/assets/video/v2. 실제영상600환경과학습4096환경을구분. trim assets/u206-axis2-stop-{nvidia,v1,v2}.mp4/JPG는모두원본2.00–8.74s6.74초. turn-v2는9–18s9초. 원본HUD시간보존,발표용mutedloop. 27쪽두영상은trim해상도1280×720동일이어도원본화면내용비율이달라현재사용자불만. frame크기검토필요.

완성콘셉트영화: assets/film-master-v8.mp4 (전체), film-opening-v7.mp4, film-ending-v8.mp4. `output/FOOTHOLD-film-storyboard.html`은영화진입점이고현재수정대상아님. 브랜드영화는 `../20260930-mvp-brand/_out/review/FULL_v6.mp4`. 잘끝난영화재생성금지. 초반전체상영,엔딩별도브랜드상영이다. 브랜드후속프로젝트경로 `inbox/jay/20260930-mvp-brand/키비주얼 스토리보드 A.html`,brand-launch-video는발표후별도과제.

U206독립검수 VERIFY-U206-20261002.md: 당시37장 SHA c37844341adbd47528557027520336f60171cda1dbfe924da744ed2ede46b4c4에서차단0. **사용자의디자인승인을뜻하지않고, 이번새레이아웃/모션피드백을해결했다는증거도아니다.** 인쇄Go2가사라짐/격자가1600폭으로커짐,11쪽stage0정면잘림을수정했던이력. 현재는3쪽추가수정으로SHA변경.

브라우저QA: Python Playwright deps `C:/Users/AI-WS01/AppData/Local/Temp/foothold-mvp-render-deps`, Chrome `C:/Program Files/Google/Chrome/Application/chrome.exe`. file://,1600×900기준,1280/1366/1920검사. design/verify-u206.py는기존전체검사. 최신3쪽은 output/u207-why-check.json 및u207-why-*.png. 기존 FOOTHOLD-MVP-review.pdf는최신37장으로갱신하지않았음. 독립review의PDF는TEMP에있으며최종배포PDF아님.

검수TUI term_f66cf249-4857-4b2f-8844-108fc30db902가누적Astra검증맥락보유. AGENTS절차: orca terminal wait satisfied확인후send; codex exec금지. 사용자검수와Astra검수구분. 선/도식/그래프/표의실제화면확인필수.

## 6. lead가 이어서 할 순서

1. 공유디스크의현재HTML과U207원문확인.3쪽복원은유지하고전체37장상하균형·겹침우선검사.
2. 12/16/22/23/25/27/31쪽요구와전체메모클릭표시수정.매번생성원본수정후동일HTML재빌드.
3. 계보의얻음/잃음/다음실험동기를보고서·원로그와대조하여그림·영상·수치로보강. 미확인손실은창작금지.
4. 10쪽정지잔상과v4/v5연속성보완. 추가모듈실제자산확보→장착연출제작. 수행불가능조건은구체적으로기록.
5. 앞뒤클릭/빠른연타/자동재생·원음/메모/인쇄/화면크기검사. 재수정주장도Astra에검증. 승인된영상·기획클로징보존.
6. 실제사용자에게동일HTML로전달. 변경범위·미완료를구분. 안전한파일만선별해git연결하고팀장검토전머지금지.

## 7. 인계 시점 스냅샷

이번 턴 실제수정: scene_revision.py, presentation_u206.css, 빌드HTML·메타생성물, 3쪽메모, U207요구기록/첨부복사/이인계서.10쪽이후피드백은아직미수정. lead와동시편집하지않기위해전달후ASTRA-MVP는중단한다.

최신HTML SHA256: `290414fd8ce8d51537376703c381bad01722817e7d0456ee734a55466b93f9a1`

---

# 아래는 U177 당시 인계 기록 · 현재 구현에 적용 금지

## 1. U177 대기 시점의 실제 구현 상태

아래 경로는 모두 `inbox/jay/20260929-mvp-presentation/` 기준이다.

- `output/FOOTHOLD-MVP-cover.html`: 새 방향으로 제작한 표지 1장. 인사 메모, N 패널, P 별도 메모 창, F 전체화면, B 암전, R 진입 연출 재생까지 구현. 다음 슬라이드 이동이나 오프닝 영상 연결은 없다.
- `output/FOOTHOLD-MVP-layout.html`: 이전 34장 스케치. 새 표지가 여기에 합쳐져 있지 않다. 최신 서사로 다시 만든 본문 덱이 아니다.
- `output/FOOTHOLD-MVP-design-system.html`: 디자인 견본이며 발표 본문이 아니다.
- U177 이후 새 본문 슬라이드 제작 없음. 표지와 본문을 통합한 최신 발표 파일도 없다. 위 표지·초안 생성기 관련 마지막 커밋은 `b47e4795`다. 대기 지시의 정확한 시각은 기록 없음.

## 2. 문서 밖 요구·구두 보류

제공된 대화와 지정한 다섯 문서를 대조했으나, 추가로 복원할 수 있는 **문서 밖 PPT 요구는 확인하지 못했다**. 별도 비공개 구두 합의는 기록 없음. 뒤쪽 발표 흐름을 팀장이 추가 구술해 확정한 기록도 없음. USD·Blender 제안은 `GO2-SPEC-ANIMATION-PLAN.md`에 이미 기록되어 있으므로 여기서 반복하지 않는다.

## 3. 열려 있던 결정

- 기존 문서의 발표 시간·최종 장수·후반부 구성 미결 사항을 닫는 추가 확인 답변은 기록 없음. 기존 34장을 확정 장수로 간주하면 안 된다.
- 인계 당시 최종 통합 덱의 파일명은 미정이었다. 2026-10-01 팀장이 기존 `output/FOOTHOLD-MVP-cover.html`에 발표 본문을 이어 붙이고 이후 PDF로 출력한다고 확정했다. 영상까지 HTML에 내장할지 별도 미디어 폴더를 동반할지는 추가 확정 기록 없음.
- 영상 파일이 존재한다는 이유로 최종 승인본으로 지정하면 안 된다. 현재 `assets/film-opening-v1.mp4`, `assets/film-ending-v1.mp4`는 480p 검토본이다. 최종 교체 파일은 영상 담당 ASTRA-MVP와 맞춰야 한다.

## 4. 이어서 할 순서

내가 계속했다면 먼저 표지 구현과 기존 덱 조작 코드를 통합하되, 오래된 본문 33장을 그대로 붙이지 않았을 것이다. 이어 표지 → 오프닝 재생 자리 → 승인된 밝은 험지 이미지와 질문 화면까지 실제로 연결하고 메모·뒤로 이동·영상 정지를 확인했을 것이다. 이후 새 서사의 본문을 순서대로 제작하면서 Go2 제원 구간의 USD 자산 확보를 별도로 진행했을 것이다. 이는 실행 전의 제안이며 추가 승인된 일정은 아니다.

## 5. 건드릴 때 주의할 실제 의존 관계

- `build_cover.py` → 표지 HTML, `build_design_preview.py` → 디자인 견본 HTML, `build_layout.py` → 34장 초안 HTML. 모두 출력 파일을 덮어쓴다. 출력 HTML만 수정한 뒤 생성기를 실행하면 수정이 사라진다.
- 표지·견본은 `design/presentation.css`를 **생성 시 HTML 안에 복사**한다. CSS 파일만 수정해도 기존 출력은 바뀌지 않는다. 반면 34장 생성기는 자체 CSS를 쓰므로 공통 CSS 변경이 전달되지 않는다.
- 세 생성기 모두 저장소 루트의 `deliverables/plan/proposal-deck-presented.html`에서 첫 `@font-face`를 정규식으로 추출한다. 파일 이동·글꼴 선언 형식 변경 시 생성이 깨질 수 있다. 표지 생성기는 `assets/cover-go2-terrain-v1.png`, `assets/foothold-lockup-compact-dark.svg`와 루트 `web/assets/brand/`의 SVG 두 파일도 읽는다.
- `build_layout.py`는 `STORYBOARD.md` 표의 숫자 행이 **정확히 34개**인지 assert한다. 내용 배치도 `content[번호]`로 고정되어 있다. 문서에서 행만 추가·이동하면 생성 실패 또는 제목·본문 대응 오류가 생긴다.
- 별도 발표자 창은 표지의 `#notesContent`를 복사하고 MutationObserver로 동기화하는 수준이다. 전체 덱의 슬라이드 상태 공유나 별도 창에서 다음 장으로 넘기는 기능은 구현하지 않았다. 표지 생성기를 그대로 쓰면 방향키·Space 진행도 생기지 않는다.
- 표지 메모에는 아직 ‘Go2 등장 후 첫 디딤’이라는 초기 영상 연결 설명이 남아 있다. 최신 영상의 컷 순서와 일치한다고 간주하지 말고, 통합 때 영상 담당과 맞춘다.
- `output/FOOTHOLD-film-storyboard.html`과 영상 제작 스크립트는 발표 덱 생성기와 독립이다. 이번 역할 분담에 따라 ASTRA-MVP가 계속 담당한다. PPT 생성 과정에서 이를 덮어쓰지 않는다.

## 6. 산출 형식

**2026-10-01 팀장 추가 확정:** 기존 `output/FOOTHOLD-MVP-cover.html`의 승인된 표지 뒤에 발표 내용과 시각 자료를 추가해 **HTML 발표 슬라이드**를 완성하고, 이후 **PDF로 출력**한다. 팀장 원문: “PPT 이전 처럼 html 로 만들고 나중에 pdf로 구울꺼야. … 여기에 추가로 뒤에 발표내용에 맞춰서 안만들어주나?”

`확인됨`: 추가 지시 시점에 해당 HTML은 여전히 표지 한 장이다. 별도의 `inbox/jay/20260929-mvp-submission/output/FOOTHOLD-MVP.html`은 종합보고서이며 이 발표 덱의 본문 완성을 뜻하지 않는다. PPT 담당은 앞서 지정한 lead, 영상·사운드 담당은 ASTRA-MVP다. `.pptx` 제작 지시는 없고 미디어 내장·동반 배포 방식은 미정이다.
