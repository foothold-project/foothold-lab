# GitHub Star 저장소 용도와 발표 시각화 후보

> 분류: 리서치
> 작성: Codex (GPT-6 Luna) · 2026-09-30 13:30
> 근거: GitHub 공식 저장소 설명과 일부 README
> 요지: vfxpedia 계정 Star 207개의 용도를 정리하고 발표용 애니메이션·시각화 후보와 연구 참고 자료를 추렸다
> 상태: 조사 초안
> 판: v0.2

이슈: [#503](https://github.com/foothold-project/foothold-lab/issues/503)

## 조사 범위

- 계정: `vfxpedia` · 확인 시각: 2026-09-30 13:30 KST · Star 목록 207개. `gh api users/vfxpedia/starred --paginate` 응답을 기준으로 2026-09-29 목록 197개와 대조했다. 새 저장소 10개, 제거 0개다.
- 저장소 설명을 바탕으로 한 줄 용도를 썼고, 설명이 없던 기존 저장소 8개와 새 저장소 10개는 README를 추가로 읽어 구체화했다. 연구 참고 자료의 논문 초록·프로젝트 링크도 확인했으나, 논문 전체 정독이나 코드 실행은 하지 않았다.
- README의 자기소개·성능 주장은 저장소가 내세운 내용으로 기록했다. 기능 실행, 결과 재현, 시스템 프롬프트 자료의 진위는 독립 검증하지 않았다.

## 발표 애니메이션·시각화 후보

| 후보 | 확인한 내용과 발표 적용 관점 | 확인 범위 |
|---|---|---|
| [heygen-com/hyperframes](https://github.com/heygen-com/hyperframes) | HTML/CSS와 seek 가능한 GSAP·CSS·Lottie 등 애니메이션을 브라우저에서 미리 보고, Puppeteer/FFmpeg로 프레임 단위 MP4 렌더링. README에는 `/slideshow` 워크플로가 있고, 조각 공개, 분기, 핫스팟 탐색, 발표자 모드를 지원한다고 적혀 있다. 기존 HTML 발표를 MP4로 뽑는 용도에는 맞을 수 있다. 다만 우리 발표의 키보드 탐색·전체화면 구조와 그대로 호환되는지는 미확인이다. 현재 선택을 확정할 근거는 아니며 서사 우선 원칙을 유지한다. | README 추가 확인 |
| [tt-a1i/archify](https://github.com/tt-a1i/archify) | 탐색형 HTML 다이어그램을 만들며, README에 `F` 프레젠테이션 스테이지, 키보드 조작, HTML·영상 내보내기가 확인된다. 발표 전체 대체보다는 실험 흐름 도해 후보. | README 추가 확인 |
| [larashero3-dotcom/lieflat-charts](https://github.com/larashero3-dotcom/lieflat-charts) | 대화형 HTML 차트와 편집형 보고서 템플릿을 제공한다. 실험 그래프 후보이며 청록 색상 체계 조정 여지가 있다. 저장소는 PolyForm Noncommercial License이므로 상업적 사용은 별도 확인이 필요하다. | README 추가 확인 |
| [hugohe3/ppt-master](https://github.com/hugohe3/ppt-master) | 문서에서 편집 가능한 네이티브 PPTX를 만들며 도형·전환·애니메이션·차트를 지원한다. HTML 발표의 직접 애니메이션 후보가 아니라 별도 PPTX 출력 경로. | README 추가 확인 |
| [3b1b/manim](https://github.com/3b1b/manim) | 정밀한 코드 애니메이션으로 설명 영상을 만든다. 개념 영상에는 참고 가능하지만 HTML 발표에 바로 넣는 구성 요소인지는 미확인. | README 추가 확인 |

**README 추가 확인:** [HyperFrames](https://github.com/heygen-com/hyperframes/blob/main/README.md)는 HTML 기반 프레임 단위 비디오 렌더와 `/slideshow` 워크플로를 설명한다. [Archify](https://github.com/tt-a1i/archify#readme)는 `F` 프레젠테이션 스테이지와 HTML·영상 출력, [Lieflat Charts](https://github.com/larashero3-dotcom/lieflat-charts#readme)는 HTML 차트 및 비상업 라이선스, [PPT Master](https://github.com/hugohe3/ppt-master#readme)는 편집 가능한 PPTX 생성을 설명한다. [Manim](https://github.com/3b1b/manim#readme)은 수학 설명 영상용 엔진이다. 문서 확인에 그쳤으며 우리 발표에서 설치·실행·호환성은 시험하지 않았다.

## Star 저장소 전체 목록

### AI·에이전트 개발

| 저장소 | 한 줄 용도 | 근거 범위 |
|---|---|---|
| [K-Dense-AI/scientific-agent-skills](https://github.com/K-Dense-AI/scientific-agent-skills) | 과학 연구 에이전트에 검증된 165개 스킬과 생명과학·의학 데이터베이스 연결을 제공한다. | GitHub 설명만 확인 |
| [ai-boost/awesome-harness-engineering](https://github.com/ai-boost/awesome-harness-engineering) | 에이전트 하니스의 도구·설계 패턴·평가·메모리·MCP 참고 자료를 모은 목록이다. | GitHub 설명만 확인 |
| [volcengine/OpenViking](https://github.com/volcengine/OpenViking) | 에이전트 메모리, RAG 지식, 스킬을 통합해 관리하는 컨텍스트 데이터베이스다. | GitHub 설명만 확인 |
| [rohitg00/agentmemory](https://github.com/rohitg00/agentmemory) | 실사용 평가를 바탕으로 코딩 에이전트의 기억을 세션 간 저장하는 시스템이다. | GitHub 설명만 확인 |
| [headroomlabs-ai/headroom](https://github.com/headroomlabs-ai/headroom) | 도구 출력·로그·파일·검색 조각을 LLM 입력 전에 압축하는 라이브러리와 프록시다. | GitHub 설명만 확인 |
| [diegosouzapw/OmniRoute](https://github.com/diegosouzapw/OmniRoute) | 여러 모델 공급자를 단일 API로 연결하고 한도 초과 시 대체 모델로 전환하는 게이트웨이다. | GitHub 설명만 확인 |
| [Graphify-Labs/graphify](https://github.com/Graphify-Labs/graphify) | 코드·문서·SQL·설정을 근거가 연결된 질의형 지식 그래프로 변환하는 스킬이다. | GitHub 설명만 확인 |
| [JustVugg/colibri](https://github.com/JustVugg/colibri) | 디스크에서 전문가 가중치를 불러와 일반 하드웨어에서 MoE 언어 모델을 실행하는 C 엔진이다. | GitHub 설명만 확인 |
| [browser-use/jev-ultrafast](https://github.com/browser-use/jev-ultrafast) | 웹사이트를 빠르고 저렴하게 조작하는 브라우저 에이전트다. | GitHub 설명만 확인 |
| [pacifio/atlas](https://github.com/pacifio/atlas) | 여러 코딩 에이전트의 변경을 추적하고 작업 간 질의를 지원하는 소스 관리 도구다. | GitHub 설명만 확인 |
| [THU-MAIC/OpenMAIC](https://github.com/THU-MAIC/OpenMAIC) | 여러 AI 에이전트가 함께 수업하는 대화형 온라인 교실이다. | GitHub 설명만 확인 |
| [cobanov/awesome-fly](https://github.com/cobanov/awesome-fly) | 초파리 신경망 connectome, 뇌 시뮬레이션과 관련 프로젝트를 모은 목록이다. | GitHub 설명만 확인 |
| [trailhq/Graft](https://github.com/trailhq/Graft) | 코드베이스 맥락을 코딩 에이전트에 제공해 작업 정확도를 높이는 도구다. | GitHub 설명만 확인 |
| [graykode/abtop](https://github.com/graykode/abtop) | Claude Code·Codex 세션, 토큰·문맥 한도와 사용량을 실시간 모니터링한다. | GitHub 설명만 확인 |
| [tt-a1i/archify](https://github.com/tt-a1i/archify) | 코드에서 상호작용 가능한 HTML 아키텍처·흐름도를 만들고 발표 모드와 영상 출력을 지원한다. | README 추가 확인 |
| [trycompai/crm](https://github.com/trycompai/crm) | AI 에이전트 중심으로 설계한 고객 관계 관리 앱이다. | GitHub 설명만 확인 |
| [macro-inc/macro](https://github.com/macro-inc/macro) | 메일·채팅·문서·업무·회의·CRM을 공유 AI 기억과 연결하는 팀 업무 공간이다. | GitHub 설명만 확인 |
| [unslothai/unsloth](https://github.com/unslothai/unsloth) | 언어 모델과 이미지 생성 모델을 로컬에서 실행하고 학습하는 UI·도구다. | GitHub 설명만 확인 |
| [lightningpixel/modly](https://github.com/lightningpixel/modly) | 이미지나 프롬프트에서 GPU 로컬 처리로 3D 모델을 만드는 데스크톱 앱이다. | GitHub 설명만 확인 |
| [openai/codex](https://github.com/openai/codex) | 터미널에서 코드 저장소를 읽고 수정하는 경량 코딩 에이전트다. | GitHub 설명만 확인 |
| [earendil-works/pi](https://github.com/earendil-works/pi) | LLM 연결, 에이전트 실행 루프, TUI와 코딩 CLI를 제공하는 개발 툴킷이다. | GitHub 설명만 확인 |
| [openinterpreter/openinterpreter](https://github.com/openinterpreter/openinterpreter) | 오픈 모델이 코드를 실행해 컴퓨터 작업을 수행하도록 하는 에이전트다. | GitHub 설명만 확인 |
| [HKUDS/Vibe-Trading](https://github.com/HKUDS/Vibe-Trading) | 개인 투자 판단을 돕는 트레이딩 에이전트다. | GitHub 설명만 확인 |
| [citrolabs/ego-lite](https://github.com/citrolabs/ego-lite) | 로그인된 브라우저를 공유해 사용자 세션을 유지하며 에이전트 자동화를 수행한다. | GitHub 설명만 확인 |
| [mem0ai/mem0](https://github.com/mem0ai/mem0) | AI 에이전트와 앱이 장기 사용자 기억을 저장하고 검색하도록 하는 인프라다. | GitHub 설명만 확인 |
| [Yeachan-Heo/oh-my-claudecode](https://github.com/Yeachan-Heo/oh-my-claudecode) | Claude Code에서 전문 에이전트 팀을 조율하는 오케스트레이션 도구다. | GitHub 설명만 확인 |
| [lidge-jun/opencodex](https://github.com/lidge-jun/opencodex) | Codex·Claude Code 요청을 여러 상용·로컬 모델로 중계하는 프록시다. | GitHub 설명만 확인 |
| [paperclipai/paperclip](https://github.com/paperclipai/paperclip) | 조직 내 AI 에이전트의 업무를 관리하는 오픈소스 앱이다. | GitHub 설명만 확인 |
| [Nutlope/hallmark](https://github.com/Nutlope/hallmark) | 에이전트가 상투적인 AI 스타일 대신 구체적인 디자인을 만들도록 돕는 스킬이다. | GitHub 설명만 확인 |
| [TencentCloud/CubeSandbox](https://github.com/TencentCloud/CubeSandbox) | 에이전트 작업을 격리 실행하는 빠르고 가벼운 동시성 샌드박스다. | GitHub 설명만 확인 |
| [chatchat-space/Langchain-Chatchat](https://github.com/chatchat-space/Langchain-Chatchat) | Qwen·Llama 등으로 로컬 문서 질의, RAG와 에이전트 기능을 제공한다. | GitHub 설명만 확인 |
| [pollen-robotics/AmazingHand](https://github.com/pollen-robotics/AmazingHand) | AmazingHand 로봇 손을 제어하는 코드와 모델이다. | GitHub 설명만 확인 |
| [Panniantong/Agent-Reach](https://github.com/Panniantong/Agent-Reach) | 여러 웹 서비스의 게시물·영상을 API 키 없이 검색하도록 에이전트를 연결한다. | GitHub 설명만 확인 |
| [google-research/timesfm](https://github.com/google-research/timesfm) | Google Research가 만든 사전 학습 시계열 예측 모델이다. | GitHub 설명만 확인 |
| [NVIDIA/SkillSpector](https://github.com/NVIDIA/SkillSpector) | 에이전트 스킬에서 악성 코드·프롬프트 인젝션·정보 유출 위험을 검사한다. | GitHub 설명만 확인 |
| [withastro/flue](https://github.com/withastro/flue) | AI 에이전트 작업을 격리하는 샌드박스 프레임워크다. | GitHub 설명만 확인 |
| [stablyai/orca](https://github.com/stablyai/orca) | 여러 코딩 에이전트를 병렬 실행하는 개발 환경이다. | GitHub 설명만 확인 |
| [MengTo/Skills](https://github.com/MengTo/Skills) | 디자이너와 개발자를 위한 Codex·Claude·Cursor 에이전트 스킬 모음이다. | GitHub 설명만 확인 |
| [agentskills/agentskills](https://github.com/agentskills/agentskills) | AI 코딩 에이전트 간 호환되는 스킬 형식의 표준과 문서다. | GitHub 설명만 확인 |
| [alirezarezvani/claude-skills](https://github.com/alirezarezvani/claude-skills) | 개발·마케팅·연구·운영 등 직무별 에이전트 스킬 모음이다. | GitHub 설명만 확인 |
| [browser-use/browser-use](https://github.com/browser-use/browser-use) | 웹페이지를 읽고 클릭·입력하는 브라우저 에이전트 라이브러리다. | GitHub 설명만 확인 |
| [lsdefine/GenericAgent](https://github.com/lsdefine/GenericAgent) | 경험으로 스킬을 쌓아 시스템 작업을 수행하는 자기 개선 에이전트다. | GitHub 설명만 확인 |
| [JCodesMore/ai-website-cloner-template](https://github.com/JCodesMore/ai-website-cloner-template) | AI 코딩 에이전트로 웹사이트 구조를 복제하는 템플릿이다. | GitHub 설명만 확인 |
| [xbtlin/ai-berkshire](https://github.com/xbtlin/ai-berkshire) | 가치투자 원칙으로 기업을 조사하는 Claude Code·Codex 연구 프레임워크다. | GitHub 설명만 확인 |
| [google-labs-code/stitch-skills](https://github.com/google-labs-code/stitch-skills) | Stitch MCP와 호환되는 UI 제작 에이전트 스킬 모음이다. | GitHub 설명만 확인 |
| [revfactory/harness](https://github.com/revfactory/harness) | 전문 에이전트 팀과 각 역할의 스킬을 설계·생성하는 메타 스킬이다. | GitHub 설명만 확인 |
| [mukul975/Anthropic-Cybersecurity-Skills](https://github.com/mukul975/Anthropic-Cybersecurity-Skills) | 보안 프레임워크에 연결된 사이버보안 업무 스킬 모음이다. | GitHub 설명만 확인 |
| [DietrichGebert/ponytail](https://github.com/DietrichGebert/ponytail) | 기존 코드를 우선 활용하도록 에이전트의 불필요한 코드 작성을 줄이는 스킬이다. | GitHub 설명만 확인 |
| [JuliusBrussee/caveman](https://github.com/JuliusBrussee/caveman) | 짧은 문장 압축으로 코딩 에이전트 토큰 사용량을 줄이는 프록시·스킬이다. | GitHub 설명만 확인 |
| [blader/humanizer](https://github.com/blader/humanizer) | AI 생성 문체 신호를 찾아 문장을 다시 쓰는 스킬이다. | GitHub 설명만 확인 |
| [tesseract-ocr/tessdata](https://github.com/tesseract-ocr/tessdata) | Tesseract OCR의 언어별 학습 데이터 파일 모음이다. | GitHub 설명만 확인 |
| [microsoft/SkillOpt](https://github.com/microsoft/SkillOpt) | 작업 궤적 평가로 에이전트용 자연어 스킬을 개선하고 검증한다. | GitHub 설명만 확인 |
| [nesquena/hermes-webui](https://github.com/nesquena/hermes-webui) | Hermes Agent를 웹과 휴대전화에서 쓰는 사용자 인터페이스다. | GitHub 설명만 확인 |
| [underlines/awesome-ml](https://github.com/underlines/awesome-ml) | LLM·분석·데이터과학 자료와 도구를 모은 목록이다. | GitHub 설명만 확인 |
| [mattpocock/skills](https://github.com/mattpocock/skills) | 실무 엔지니어링을 지원하는 에이전트 스킬 모음이다. | GitHub 설명만 확인 |
| [eugeniughelbur/obsidian-second-brain](https://github.com/eugeniughelbur/obsidian-second-brain) | Obsidian 노트에 기억을 저장하고 검색·정리·예약 실행하는 에이전트 플러그인이다. | GitHub 설명만 확인 |
| [kepano/obsidian-skills](https://github.com/kepano/obsidian-skills) | Obsidian CLI와 Markdown·Bases·Canvas 문서 처리를 위한 에이전트 스킬이다. | GitHub 설명만 확인 |
| [breferrari/obsidian-mind](https://github.com/breferrari/obsidian-mind) | Obsidian 노트를 코딩 에이전트의 지속 기억으로 관리한다. | GitHub 설명만 확인 |
| [VoltAgent/awesome-design-md](https://github.com/VoltAgent/awesome-design-md) | 유명 브랜드의 디자인 시스템 예시와 DESIGN.md 분석을 모은다. | GitHub 설명만 확인 |
| [obra/superpowers](https://github.com/obra/superpowers) | 코딩 에이전트가 계획·테스트·구현 절차를 따르게 하는 스킬 프레임워크다. | GitHub 설명만 확인 |
| [sykim52/colgraphrag](https://github.com/sykim52/colgraphrag) | 질문 맞춤 증거 그래프와 이미지 재정렬을 결합한 멀티모달 RAG 파이프라인이다. | GitHub 설명만 확인 |
| [Q00/ouroboros](https://github.com/Q00/ouroboros) | 단계별 평가를 통과한 변경만 적용해 에이전트 역량을 예산 내 개선한다. | GitHub 설명만 확인 |
| [Yeachan-Heo/oh-my-codex](https://github.com/Yeachan-Heo/oh-my-codex) | Codex에 훅·에이전트 팀·상태 표시 기능을 추가하는 확장 도구다. | GitHub 설명만 확인 |
| [msitarzewski/agency-agents](https://github.com/msitarzewski/agency-agents) | 개발·디자인·마케팅 등 역할별 에이전트 절차와 산출물 예시를 모았다. | GitHub 설명만 확인 |
| [microsoft/ai-agents-for-beginners](https://github.com/microsoft/ai-agents-for-beginners) | AI 에이전트 개발 기초를 18개 강의와 실습으로 가르친다. | GitHub 설명만 확인 |
| [NousResearch/hermes-agent](https://github.com/NousResearch/hermes-agent) | 도구를 사용해 대화·작업을 수행하는 오픈소스 개인 AI 에이전트다. | GitHub 설명만 확인 |
| [humantonylee/free-router](https://github.com/humantonylee/free-router) | AI 모델·제공자를 비교하고 요청 대상을 바꾸는 API 라우터다. | GitHub 설명만 확인 |
| [affaan-m/ECC](https://github.com/affaan-m/ECC) | 스킬·기억·보안과 연구 절차를 개선하는 코딩 에이전트 하니스다. | GitHub 설명만 확인 |
| [ultraworkers/claw-code](https://github.com/ultraworkers/claw-code) | 에이전트가 자율적으로 구축·운영하는 Rust 기반 디지털 전시 프로젝트다. | GitHub 설명만 확인 |
| [bytedance/deer-flow](https://github.com/bytedance/deer-flow) | 샌드박스·기억·도구·하위 에이전트를 이용해 장시간 조사와 코딩을 수행한다. | GitHub 설명만 확인 |
| [AlexsJones/llmfit](https://github.com/AlexsJones/llmfit) | 컴퓨터 사양에 맞는 실행 가능 LLM과 공급자를 찾아주는 CLI다. | GitHub 설명만 확인 |
| [SillyTavern/SillyTavern](https://github.com/SillyTavern/SillyTavern) | 여러 언어 모델과 캐릭터 대화를 구성하는 사용자용 LLM 프런트엔드다. | GitHub 설명만 확인 |

### 로봇·3D·연구

| 저장소 | 한 줄 용도 | 근거 범위 |
|---|---|---|
| [amap-cvlab/ABot-Recon](https://github.com/amap-cvlab/ABot-Recon) | 영상 입력을 받아 장시간에 걸쳐 3D 장면을 연속 복원하는 연구 구현이다. | GitHub 설명만 확인 |
| [AprilRobotics/apriltag](https://github.com/AprilRobotics/apriltag) | AprilTag 시각 기준 마커를 검출하는 로봇 연구용 비전 시스템이다. | GitHub 설명만 확인 |
| [cactus-compute/needle](https://github.com/cactus-compute/needle) | 휴대전화·로봇 등 작은 장치에서 도구 호출·추출·임베딩을 수행하는 초소형 자동화 모델이다. | GitHub 설명만 확인 |
| [hms-gymnopedie/IsaacSim_Setting](https://github.com/hms-gymnopedie/IsaacSim_Setting) | Isaac Sim 환경을 구성하는 Docker 설정이다. | GitHub 설명만 확인 |
| [Zhefan-Xu/isaac-go2-ros2](https://github.com/Zhefan-Xu/isaac-go2-ros2) | Isaac에서 Unitree Go2의 ROS2 항법·의사결정·자율 동작을 시험하는 시뮬레이터다. | GitHub 설명만 확인 |
| [unitreerobotics/unitree_rl_lab](https://github.com/unitreerobotics/unitree_rl_lab) | IsaacLab에서 Unitree 로봇 강화학습을 구현한 코드 모음이다. | GitHub 설명만 확인 |
| [isaac-sim/IsaacSim](https://github.com/isaac-sim/IsaacSim) | 현실적인 가상 환경에서 로봇 AI를 개발·시뮬레이션·시험하는 Omniverse 앱이다. | GitHub 설명만 확인 |
| [isaac-sim/IsaacLab](https://github.com/isaac-sim/IsaacLab) | 다중 물리·렌더러를 지원하는 로봇 학습 시뮬레이션 프레임워크다. | GitHub 설명만 확인 |
| [Robbyant/lingbot-map](https://github.com/Robbyant/lingbot-map) | 긴 영상에서 기하 정보를 이용해 3D 장면 지도를 순차 복원한다. | GitHub 설명만 확인 |
| [huggingface/lerobot](https://github.com/huggingface/lerobot) | 데이터셋·시뮬레이션·정책 학습을 묶은 오픈소스 로봇 학습 라이브러리다. | GitHub 설명만 확인 |

### 개발 도구·기타

| 저장소 | 한 줄 용도 | 근거 범위 |
|---|---|---|
| [Maelic/RelateAnything](https://github.com/Maelic/RelateAnything) | 다양한 입력에서 개방형 어휘로 객체 사이의 관계를 실시간 예측한다. | GitHub 설명만 확인 |
| [robbietilton/Compositor](https://github.com/robbietilton/Compositor) | Mac에서 레이어 기반 이미지 편집을 제공하는 Photoshop 대체 앱이다. | GitHub 설명만 확인 |
| [github/spec-kit](https://github.com/github/spec-kit) | 명세 주도 개발 흐름을 시작하기 위한 템플릿과 개발 도구 모음이다. | GitHub 설명만 확인 |
| [davila7/claude-code-templates](https://github.com/davila7/claude-code-templates) | Claude Code의 설정과 기능 템플릿을 구성하고 상태를 모니터링하는 CLI다. | GitHub 설명만 확인 |
| [dreamurl/GPT-Bridge](https://github.com/dreamurl/GPT-Bridge) | VS Code 작업 공간을 MCP 서버로 열어 ChatGPT가 코드를 읽고 편집하게 하며, 변경은 승인 뒤 편집기 버퍼에 반영한다. | README 추가 확인 |
| [uppinote20/claude-dashboard](https://github.com/uppinote20/claude-dashboard) | Claude Code의 문맥 사용량, API 한도와 비용을 상태 표시줄에 보여준다. | GitHub 설명만 확인 |
| [trycua/cua](https://github.com/trycua/cua) | 여러 운영체제의 컴퓨터 조작 에이전트를 위한 드라이버와 평가·학습 환경이다. | GitHub 설명만 확인 |
| [arclab-hku/Risky_gym](https://github.com/arclab-hku/Risky_gym) | MARG는 고도 지형 지도와 관절 감각을 결합해 사족 로봇이 위험한 틈 지형에서 안전한 발 디딤을 고르는 연구다. README상 코드 공개는 준비 중이다. | README 추가 확인 |
| [odoo/odoo](https://github.com/odoo/odoo) | CRM·회계·재고 등 기업 업무 앱을 제공하는 오픈소스 ERP다. | GitHub 설명만 확인 |
| [tamaratran/fast-jev-compaction](https://github.com/tamaratran/fast-jev-compaction) | 도구 호출 결과의 중요도를 판별해 낡은 내용을 압축하되 남기는 근거는 원문 그대로 보존한다. | GitHub 설명만 확인 |
| [nv-tlabs/3dgrut](https://github.com/nv-tlabs/3dgrut) | 3D Gaussian 입자를 광선 추적과 하이브리드 래스터화로 그리는 연구 코드다. | GitHub 설명만 확인 |
| [jgraph/drawio-desktop](https://github.com/jgraph/drawio-desktop) | draw.io의 공식 Electron 데스크톱 앱이다. | README 추가 확인 |
| [D4Vinci/Scrapling](https://github.com/D4Vinci/Scrapling) | 단일 페이지부터 대규모 크롤링까지 지원하는 적응형 웹 스크래핑 프레임워크다. | GitHub 설명만 확인 |
| [dgtlmoon/changedetection.io](https://github.com/dgtlmoon/changedetection.io) | 웹페이지 변경, 가격 하락, 재입고 등을 감지해 알림을 보낸다. | GitHub 설명만 확인 |
| [every-app/open-seo](https://github.com/every-app/open-seo) | Semrush·Ahrefs와 같은 SEO 분석 서비스를 제공하는 오픈소스 대안이다. | GitHub 설명만 확인 |
| [abi/screenshot-to-code](https://github.com/abi/screenshot-to-code) | 화면 캡처를 HTML·Tailwind·React·Vue 코드로 변환한다. | GitHub 설명만 확인 |
| [pixel-agents-hq/pixel-agents](https://github.com/pixel-agents-hq/pixel-agents) | 에이전트 활동을 픽셀 아트 사무실 화면으로 표현한다. | GitHub 설명만 확인 |
| [semantica-agi/semantica](https://github.com/semantica-agi/semantica) | 증거 추적을 지원하는 그래프 기반 AI 문맥·데이터 인프라다. | GitHub 설명만 확인 |
| [megadose/holehe](https://github.com/megadose/holehe) | 이메일 주소로 여러 사이트의 계정 등록 여부를 확인하는 OSINT 도구다. | GitHub 설명만 확인 |
| [omacom/omarchy](https://github.com/omacom/omarchy) | Arch Linux를 기본 설정과 시각적 구성을 갖춘 데스크톱 환경으로 제공한다. | GitHub 설명만 확인 |
| [public-apis/public-apis](https://github.com/public-apis/public-apis) | 무료로 이용 가능한 공개 API를 분야별로 모은 목록이다. | GitHub 설명만 확인 |
| [NVIDIA-Omniverse/omniverse-labs](https://github.com/NVIDIA-Omniverse/omniverse-labs) | NVIDIA Omniverse용 실험 샘플과 콘텐츠를 제공한다. | GitHub 설명만 확인 |
| [nyrahealth/CrisperWhisper](https://github.com/nyrahealth/CrisperWhisper) | 단어별 시각 정보를 보존하면서 말버릇을 그대로 남기거나 읽기 좋게 전사한다. | GitHub 설명만 확인 |
| [supabase/supabase](https://github.com/supabase/supabase) | Postgres 기반 데이터베이스·인증·스토리지 기능을 제공하는 앱 개발 플랫폼이다. | GitHub 설명만 확인 |
| [OpenCut-app/OpenCut](https://github.com/OpenCut-app/OpenCut) | CapCut 대체 오픈소스 영상 편집기다. | GitHub 설명만 확인 |
| [HKUDS/DeepTutor](https://github.com/HKUDS/DeepTutor) | 개인 학습 이력을 바탕으로 맞춤형 지도를 제공하는 튜터다. | GitHub 설명만 확인 |
| [vinta/awesome-python](https://github.com/vinta/awesome-python) | 용도별 Python 라이브러리와 도구를 모아둔 목록이다. | GitHub 설명만 확인 |
| [star-history/star-history](https://github.com/star-history/star-history) | GitHub 저장소의 시간별 Star 증가 추이를 그래프로 비교한다. | README 추가 확인 |
| [microsoft/vscode](https://github.com/microsoft/vscode) | 확장 기능을 지원하는 Visual Studio Code 코드 편집기다. | GitHub 설명만 확인 |
| [microsoft/playwright-cli](https://github.com/microsoft/playwright-cli) | 브라우저 조작을 CLI로 기록하고 Playwright 자동화 코드를 만드는 도구다. | GitHub 설명만 확인 |
| [microsoft/playwright-python](https://github.com/microsoft/playwright-python) | Python에서 Chromium·Firefox·WebKit을 자동화하는 Playwright 라이브러리다. | GitHub 설명만 확인 |
| [microsoft/playwright-mcp](https://github.com/microsoft/playwright-mcp) | MCP를 통해 Playwright 브라우저 자동화를 제공하는 서버다. | GitHub 설명만 확인 |
| [microsoft/playwright](https://github.com/microsoft/playwright) | Chromium·Firefox·WebKit을 대상으로 웹 테스트와 브라우저 자동화를 수행한다. | GitHub 설명만 확인 |
| [Julian-adv/OpenMMO](https://github.com/Julian-adv/OpenMMO) | 사람과 AI 에이전트가 같은 WebSocket 규약과 규칙으로 참여하는 실시간 3D MMORPG다. | README 추가 확인 |
| [tmux/tmux](https://github.com/tmux/tmux) | 터미널 세션을 분할·유지·재접속하는 터미널 멀티플렉서다. | GitHub 설명만 확인 |
| [techwithanant/saras_ai_robot_v2](https://github.com/techwithanant/saras_ai_robot_v2) | Raspberry Pi 로봇 자동차의 모터·카메라를 MCP 도구로 노출해 Claude Code가 이동·정지·센서 조회를 수행하게 하는 시작 프로젝트다. | README 추가 확인 |
| [Saqoosha/ccusage-menubar](https://github.com/Saqoosha/ccusage-menubar) | Claude Code의 로컬 사용 기록을 읽어 토큰과 일·월별 비용을 macOS 메뉴 막대에 실시간 표시한다. | README 추가 확인 |
| [edwardkim/rhwp](https://github.com/edwardkim/rhwp) | Rust·WebAssembly 기반 한글 HWP 뷰어·편집기다. | GitHub 설명만 확인 |
| [Leonxlnx/taste-skill](https://github.com/Leonxlnx/taste-skill) | AI가 흔한 기본형 UI를 만들지 않도록 디자인 판단 기준을 제공한다. | GitHub 설명만 확인 |
| [elder-plinius/G0DM0D3](https://github.com/elder-plinius/G0DM0D3) | 다중 공급자·로컬 모델 채팅, 여러 모델 병렬 비교와 프롬프트 변형 레드팀 도구를 한 UI에 묶은 프로젝트다. 기능·보안 주장은 README 기반으로 별도 검증하지 않았다. | README 추가 확인 |
| [elder-plinius/L1B3RT4S](https://github.com/elder-plinius/L1B3RT4S) | 여러 상용 AI 모델에서 거부를 우회하는 프롬프트를 모아 배포한다고 주장하는 저장소다. 수록 내용의 작동 여부는 검증하지 않았다. | README 추가 확인 |
| [elder-plinius/CL4R1T4S](https://github.com/elder-plinius/CL4R1T4S) | 여러 AI 제품의 시스템 프롬프트를 수집해 버전 정보를 붙여 공개한다고 주장하는 저장소다. 자료의 출처와 최신성은 독립 검증하지 않았다. | README 추가 확인 |
| [Zackriya-Solutions/meetily](https://github.com/Zackriya-Solutions/meetily) | 음성을 로컬 전사하고 화자 구분·요약을 제공하는 회의 기록 앱이다. | GitHub 설명만 확인 |
| [gronxb/codex-relay](https://github.com/gronxb/codex-relay) | 컴퓨터의 Codex 세션을 휴대전화에서 이어 쓰는 원격 연결 도구다. | GitHub 설명만 확인 |
| [fivetaku/insane-search](https://github.com/fivetaku/insane-search) | 차단된 웹사이트의 접속 경로를 단계별로 탐색하는 Claude 검색 플러그인이다. | GitHub 설명만 확인 |
| [usestrix/strix](https://github.com/usestrix/strix) | 웹 앱의 보안 취약점을 찾아 수정하는 AI 침투 테스트 도구다. | GitHub 설명만 확인 |
| [openai/codex-plugin-cc](https://github.com/openai/codex-plugin-cc) | Claude Code에서 Codex로 코드 리뷰를 맡기거나 작업을 위임하는 플러그인이다. | GitHub 설명만 확인 |
| [MarcSkovMadsen/awesome-streamlit](https://github.com/MarcSkovMadsen/awesome-streamlit) | Streamlit 사용 사례와 관련 자료를 공유하는 목록이다. | GitHub 설명만 확인 |
| [Adam-CAD/CADAM](https://github.com/Adam-CAD/CADAM) | 텍스트 지시를 CAD 모델로 바꾸는 오픈소스 웹 앱이다. | GitHub 설명만 확인 |
| [helloianneo/ian-xiaohei-illustrations](https://github.com/helloianneo/ian-xiaohei-illustrations) | 흰 배경 16:9 손그림 설명 삽화를 생성하는 Codex 스킬이다. | GitHub 설명만 확인 |
| [jamiepine/voicebox](https://github.com/jamiepine/voicebox) | 음성 복제·받아쓰기·콘텐츠 생성을 지원하는 오픈소스 음성 스튜디오다. | GitHub 설명만 확인 |
| [mgth/LittleBigMouse](https://github.com/mgth/LittleBigMouse) | DPI가 다른 여러 화면 사이의 마우스 이동을 보정하는 Windows 도구다. | GitHub 설명만 확인 |
| [nikopueringer/CorridorKey](https://github.com/nikopueringer/CorridorKey) | 녹색 배경을 제거해 피사체를 분리하는 크로마키 도구다. | GitHub 설명만 확인 |
| [epoko77-ai/im-not-ai](https://github.com/epoko77-ai/im-not-ai) | 한국어 AI 문장의 번역투·반복 표현을 찾아 자연스럽게 다듬는다. | GitHub 설명만 확인 |
| [SOMJANG/Mecab-ko-for-Google-Colab](https://github.com/SOMJANG/Mecab-ko-for-Google-Colab) | Google Colab에서 한국어 형태소 분석기 Mecab을 설치·사용하는 안내다. | GitHub 설명만 확인 |
| [smilegate-ai/korean_unsmile_dataset](https://github.com/smilegate-ai/korean_unsmile_dataset) | 혐오표현·악플/욕설·clean으로 분류하고 혐오 범주에 다중 레이블을 붙인 한국어 문장 데이터셋이다. | README 추가 확인 |
| [ahastudio/til](https://github.com/ahastudio/til) | 배운 내용을 날짜별로 기록하는 Today I Learned 자료 모음이다. | GitHub 설명만 확인 |
| [VAST-AI-Research/TripoSplat](https://github.com/VAST-AI-Research/TripoSplat) | 단일 이미지에서 가변 개수의 3D Gaussian을 생성하는 모델이다. | GitHub 설명만 확인 |
| [EveryInc/compound-engineering-plugin](https://github.com/EveryInc/compound-engineering-plugin) | 탐색·계획·구현·검토 개발 절차를 코딩 에이전트에 제공하는 플러그인이다. | GitHub 설명만 확인 |
| [ZhengPeng7/BiRefNet](https://github.com/ZhengPeng7/BiRefNet) | 고해상도 이미지에서 전경 객체를 분리하는 BiRefNet 모델이다. | GitHub 설명만 확인 |
| [QwenLM/Qwen3-TTS](https://github.com/QwenLM/Qwen3-TTS) | 자연스러운 음성 생성과 음색 설계·복제를 지원하는 Qwen TTS 모델이다. | GitHub 설명만 확인 |
| [microsoft/PowerToys](https://github.com/microsoft/PowerToys) | Windows 기능과 설정을 확장하는 Microsoft 유틸리티 모음이다. | GitHub 설명만 확인 |
| [Netflix/void-model](https://github.com/Netflix/void-model) | VOID는 영상에서 객체와 그 객체가 남긴 상호작용 흔적을 제거하는 비디오 편집 모델이다. | README 추가 확인 |
| [slopus/happy](https://github.com/slopus/happy) | 휴대전화와 웹에서 Codex·Claude Code 세션을 쓰는 음성 지원 클라이언트다. | GitHub 설명만 확인 |
| [fivetaku/cc101](https://github.com/fivetaku/cc101) | Claude Code를 처음 배우는 사용자를 위한 한국어 안내서다. | GitHub 설명만 확인 |
| [NomaDamas/k-skill](https://github.com/NomaDamas/k-skill) | 한국어 표현과 맥락을 에이전트 작업에 반영하는 스킬 모음이다. | GitHub 설명만 확인 |
| [microsoft/VibeVoice](https://github.com/microsoft/VibeVoice) | Microsoft의 오픈소스 음성 AI 모델 프로젝트다. | GitHub 설명만 확인 |
| [supertone-oss-archive/supertonic](https://github.com/supertone-oss-archive/supertonic) | ONNX로 로컬 기기에서 실행하는 빠른 다국어 음성 합성 모델이다. | GitHub 설명만 확인 |
| [openclaw/openclaw](https://github.com/openclaw/openclaw) | 여러 기기·플랫폼에서 도구를 사용해 작업하는 개인 AI 에이전트다. | GitHub 설명만 확인 |
| [code-yeongyu/oh-my-openagent](https://github.com/code-yeongyu/oh-my-openagent) | OpenCode에 그래프 기반 작업 조율과 병렬 에이전트 명령을 추가한다. | GitHub 설명만 확인 |
| [codecrafters-io/build-your-own-x](https://github.com/codecrafters-io/build-your-own-x) | 컴파일러·DB 같은 기술을 직접 만들어 배우는 튜토리얼 목록이다. | GitHub 설명만 확인 |
| [ultralytics/ultralytics](https://github.com/ultralytics/ultralytics) | YOLO 기반 객체 탐지·분할·분류·자세 추정·추적 도구다. | GitHub 설명만 확인 |
| [SKN19-3rd-4team/zip-fit](https://github.com/SKN19-3rd-4team/zip-fit) | 집을 검색하고 선택하는 데 도움을 주는 팀 프로젝트 서비스다. | GitHub 설명만 확인 |
| [SKNetworks-AI19-250818/.github](https://github.com/SKNetworks-AI19-250818/.github) | SK Networks Family AI 캠프 19기 수업용 Python·DB·크롤링·분석·ML·DL·NLP·LLM·웹·Django 저장소를 안내하는 조직 프로필이다. | README 추가 확인 |
| [nari-labs/dia](https://github.com/nari-labs/dia) | 한 번에 여러 화자의 자연스러운 대화 음성을 생성하는 TTS 모델이다. | GitHub 설명만 확인 |

### 문서·검색·데이터

| 저장소 | 한 줄 용도 | 근거 범위 |
|---|---|---|
| [StarTrail-org/LEANN](https://github.com/StarTrail-org/LEANN) | 개인 기기에서 검색 증강 생성을 실행하며 인덱스 저장 공간을 크게 줄이는 시스템이다. | GitHub 설명만 확인 |
| [docling-project/docling](https://github.com/docling-project/docling) | PDF와 문서를 AI 처리에 적합한 구조화 데이터로 변환한다. | GitHub 설명만 확인 |
| [HKUDS/LightRAG](https://github.com/HKUDS/LightRAG) | 그래프 검색을 이용해 문서 지식 질의를 처리하는 RAG 프레임워크다. | GitHub 설명만 확인 |
| [asgeirtj/system_prompts_leaks](https://github.com/asgeirtj/system_prompts_leaks) | 여러 AI 제품의 시스템 프롬프트 원문을 모아 날짜와 모델별 파일로 관리한다고 주장하는 저장소다. 자료의 진위는 독립 검증하지 않았다. | README 추가 확인 |
| [microsoft/markitdown](https://github.com/microsoft/markitdown) | PDF·Office 파일을 Markdown으로 변환하는 Python 도구다. | GitHub 설명만 확인 |
| [ekimetrics/adaptive-chunking](https://github.com/ekimetrics/adaptive-chunking) | 문서마다 적절한 RAG 텍스트 분할 방식을 자동 선택한다. | GitHub 설명만 확인 |
| [DeusData/codebase-memory-mcp](https://github.com/DeusData/codebase-memory-mcp) | 코드 저장소를 지식 그래프로 인덱싱하고 심볼 관계를 질의하는 MCP 서버다. | GitHub 설명만 확인 |
| [opendataloader-project/opendataloader-pdf](https://github.com/opendataloader-project/opendataloader-pdf) | PDF를 AI 처리용으로 파싱하고 접근성 개선을 자동화한다. | GitHub 설명만 확인 |

### 발표·시각화·미디어

| 저장소 | 한 줄 용도 | 근거 범위 |
|---|---|---|
| [google/artemis](https://github.com/google/artemis) | 자연어 지시로 Android 앱을 조작하고 실행 과정을 기록하는 자동화 시스템이다. | GitHub 설명만 확인 |
| [jgraph/drawio](https://github.com/jgraph/drawio) | 브라우저에서 순서도와 구조도 등 일반 다이어그램을 만들고 편집한다. | README 추가 확인 |
| [huawei-bayerlab/marigold-v2](https://github.com/huawei-bayerlab/marigold-v2) | 확산 Transformer를 이용한 단일 이미지 깊이 추정 연구다. | GitHub 설명만 확인 |
| [prs-eth/Marigold](https://github.com/prs-eth/Marigold) | 이미지 생성용 확산 모델을 단안 깊이 추정에 활용한 연구 구현이다. | GitHub 설명만 확인 |
| [PaddlePaddle/PaddleOCR](https://github.com/PaddlePaddle/PaddleOCR) | PDF와 이미지에서 100개 이상 언어의 글자를 인식해 구조화하는 OCR 툴킷이다. | GitHub 설명만 확인 |
| [hugohe3/ppt-master](https://github.com/hugohe3/ppt-master) | 문서나 주제에서 애니메이션과 데이터 차트를 포함한 편집형 PowerPoint를 생성한다. | README 추가 확인 |
| [fabio-sim/Depth-Anything-ONNX](https://github.com/fabio-sim/Depth-Anything-ONNX) | Depth Anything 깊이 추정 모델을 ONNX 실행 환경에서 쓸 수 있게 한 구현이다. | GitHub 설명만 확인 |
| [DepthAnything/Depth-Anything-V2](https://github.com/DepthAnything/Depth-Anything-V2) | 단일 이미지에서 깊이 맵을 추정하는 Depth Anything V2 모델이다. | GitHub 설명만 확인 |
| [larashero3-dotcom/lieflat-charts](https://github.com/larashero3-dotcom/lieflat-charts) | 데이터에서 편집형 대화형 HTML 차트와 보고서를 생성하는 스킬이다. | README 추가 확인 |
| [ant-research/4DAnyone](https://github.com/ant-research/4DAnyone) | 일반 단안 영상에서 사람의 시간 변화가 담긴 4D 표현을 복원한다. | GitHub 설명만 확인 |
| [3b1b/manim](https://github.com/3b1b/manim) | 수학 개념 설명 영상을 코드로 정밀하게 애니메이션화하는 엔진이다. | README 추가 확인 |
| [cathrynlavery/diagram-design](https://github.com/cathrynlavery/diagram-design) | AI 코딩 도구가 편집 가능한 HTML·SVG 다이어그램을 만들도록 디자인 규칙을 제공한다. | README 추가 확인 |
| [PrimeIntellect-ai/prime-agent](https://github.com/PrimeIntellect-ai/prime-agent) | 코딩 작업에서 자기 개선과 장시간 자율 실행을 목표로 하는 에이전트다. | GitHub 설명만 확인 |
| [tensorflow/tensorboard](https://github.com/tensorflow/tensorboard) | TensorFlow 학습 과정과 모델 지표를 시각화한다. | GitHub 설명만 확인 |
| [GuanYixuan/pyCapCut](https://github.com/GuanYixuan/pyCapCut) | Python으로 CapCut 편집 초안을 만들고 내보내 영상 편집을 자동화한다. | GitHub 설명만 확인 |
| [HKUDS/nanobot](https://github.com/HKUDS/nanobot) | Web UI·도구·기억·MCP·멀티에이전트를 갖춘 경량 개인 AI 에이전트다. | GitHub 설명만 확인 |
| [heygen-com/hyperframes](https://github.com/heygen-com/hyperframes) | HTML·CSS·미디어·시간 지정 애니메이션을 탐색형 슬라이드나 MP4로 렌더링한다. | README 추가 확인 |
| [poloclub/transformer-explainer](https://github.com/poloclub/transformer-explainer) | Transformer 작동 과정을 상호작용 시각화로 보여주는 학습 도구다. | GitHub 설명만 확인 |
| [bradautomates/claude-video](https://github.com/bradautomates/claude-video) | 영상 프레임과 음성을 추출해 Claude가 영상 내용을 분석하도록 돕는다. | GitHub 설명만 확인 |
| [koala73/worldmonitor](https://github.com/koala73/worldmonitor) | 뉴스와 지정학·인프라 정보를 모아 실시간 세계 상황을 보여준다. | GitHub 설명만 확인 |
| [MengTo/Spring](https://github.com/MengTo/Spring) | iOS 앱에서 스프링 애니메이션을 간단히 구현하는 Swift 라이브러리다. | GitHub 설명만 확인 |
| [n8n-io/n8n](https://github.com/n8n-io/n8n) | 시각 편집과 사용자 코드를 연결해 업무 자동화 흐름을 만드는 플랫폼이다. | GitHub 설명만 확인 |
| [browser-use/video-use](https://github.com/browser-use/video-use) | 코딩 에이전트로 영상 편집을 수행하는 도구다. | GitHub 설명만 확인 |
| [NatronGitHub/Natron](https://github.com/NatronGitHub/Natron) | 노드 기반으로 영상 합성과 시각 효과를 편집하는 프로그램이다. | GitHub 설명만 확인 |
| [calesthio/OpenMontage](https://github.com/calesthio/OpenMontage) | 영상 제작 파이프라인과 도구·기술 지식을 에이전트에 제공하는 시스템이다. | GitHub 설명만 확인 |
| [palmier-io/palmier-pro](https://github.com/palmier-io/palmier-pro) | AI 중심 제작 흐름을 갖춘 macOS 영상 편집기다. | GitHub 설명만 확인 |
| [penpot/penpot](https://github.com/penpot/penpot) | 팀 협업 기능을 갖춘 오픈소스 제품·UI 디자인 플랫폼이다. | GitHub 설명만 확인 |
| [theamusing/perfectPixel](https://github.com/theamusing/perfectPixel) | 흐트러진 AI 픽셀 아트를 정돈하고 팔레트를 제한해 픽셀화한다. | GitHub 설명만 확인 |
| [aldegad/sprite-gen](https://github.com/aldegad/sprite-gen) | 게임용 스프라이트·애니메이션 시트를 만들고 상태별 프레임을 정리한다. | GitHub 설명만 확인 |
| [UB-Mannheim/tesseract](https://github.com/UB-Mannheim/tesseract) | 이미지에서 문자를 추출하는 Tesseract OCR 엔진의 배포판이다. | GitHub 설명만 확인 |
| [Anil-matcha/Open-Generative-AI](https://github.com/Anil-matcha/Open-Generative-AI) | 여러 이미지·영상 생성 모델을 선택해 쓰는 자체 호스팅 미디어 생성 스튜디오다. | GitHub 설명만 확인 |
| [garrytan/gstack](https://github.com/garrytan/gstack) | CEO·디자이너·엔지니어링 관리자·QA 역할별 Claude Code 도구 묶음이다. | GitHub 설명만 확인 |


### 2026-09-30 Star 추가 10개

| 저장소 | 한 줄 용도 | 근거 범위 |
|---|---|---|
| [ASIG-X/JEPLO](https://github.com/ASIG-X/JEPLO) | Unitree Go2의 Mid-360 LiDAR 관측을 지도 없이 해석하는 JEPA 세계 모델과 teacher-student 학습 정책으로 지형 보행을 학습한다. | README 추가 확인 |
| [google-deepmind/mujoco](https://github.com/google-deepmind/mujoco) | 접촉하는 다관절 구조물의 물리를 빠르게 계산하고 C·Python API와 대화형 시각화기를 제공하는 물리 시뮬레이터다. | README 추가 확인 |
| [leggedrobotics/legged_gym](https://github.com/leggedrobotics/legged_gym) | Isaac Gym에서 ANYmal 등 사족 로봇을 거친 지형에 학습하며 actuator network와 마찰·질량 무작위화 등을 sim-to-real에 반영한 환경이다. | README 추가 확인 |
| [microsoft/onnxruntime](https://github.com/microsoft/onnxruntime) | PyTorch·TensorFlow 등에서 만든 모델의 추론과 학습을 여러 운영체제와 하드웨어 가속기에서 실행하는 런타임이다. | README 추가 확인 |
| [unitreerobotics/unitree_rl_gym](https://github.com/unitreerobotics/unitree_rl_gym) | Go2·H1·H1_2·G1 정책의 강화학습, MuJoCo sim-to-sim 및 실물 배포 흐름을 제공하는 Unitree 예제 저장소다. | README 추가 확인 |
| [unitreerobotics/unitree_sdk2](https://github.com/unitreerobotics/unitree_sdk2) | Unitree 로봇과 통신하고 제어하는 C++ SDK v2다. | README 추가 확인 |
| [unitreerobotics/unitree_sdk2_python](https://github.com/unitreerobotics/unitree_sdk2_python) | Unitree SDK v2 기능을 Python에서 사용해 DDS 토픽 발행·구독과 로봇 상태 조회·제어를 하는 인터페이스다. | README 추가 확인 |
| [wertyuilife2/go2_rl_robotlab](https://github.com/wertyuilife2/go2_rl_robotlab) | MoE-CTS Go2 정책을 IsaacLab/RobotLab에서 학습하고 MuJoCo sim-to-sim으로 검증한 뒤 실물에 배포하는 구현이다. | README 추가 확인 |
| [wty-yy/RoboGauge](https://github.com/wty-yy/RoboGauge) | MuJoCo에서 Go2 보행 정책의 추종·안전·안정성 지표를 여러 지형 난이도와 물성 무작위화 조건으로 평가한다. | README 추가 확인 |
| [wty-yy/go2_rl_gym](https://github.com/wty-yy/go2_rl_gym) | Isaac Gym에서 Go2용 CTS/MoE-CTS 정책을 학습하고 MuJoCo와 실물 Go2로 평가하는 RSS 2026 구현이다. | README 추가 확인 |

## 출처

- [GitHub Star API: vfxpedia Star 저장소](https://api.github.com/users/vfxpedia/starred)
- 각 행의 저장소 링크에 있는 GitHub description. `README 추가 확인` 표시는 저장소 README 또는 프로필 README를 읽은 항목이다. GIF와 영상은 README에 연결된 자료로만 확인했으며, 재생해 확인하지 않았다.

## 판 이력

| 판 | 언제 | 무엇이 바뀌었나 | 근거 |
|---|---|---|---|
| v0.2 | 2026-09-30 | 최신 Star 207개로 갱신하고 README 확인 범위와 연구 참고 문서를 추가 | 이슈 #503 |
| v0.1 | 2026-09-29 | Star 197개를 목록화하고 발표 후보를 조사 | 이슈 #503 |
