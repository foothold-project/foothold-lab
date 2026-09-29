# GitHub Star 저장소 용도와 발표 시각화 후보

> 분류: 리서치
> 작성: Codex · 2026-09-29 20:05
> 근거: GitHub 공식 저장소 설명과 일부 README
> 요지: vfxpedia 계정 Star 197개를 목록화하고 발표용 애니메이션·시각화 후보를 추렸다
> 상태: 조사 초안
> 판: v0.1

이슈: [#503](https://github.com/foothold-project/foothold-lab/issues/503)

## 조사 범위

- 계정: `vfxpedia` · 확인 시각: 2026-09-29 20:05 KST · Star 목록 197개. GitHub Star API 응답을 기준으로 저장소 이름과 설명을 확인했다.
- 아래 전체 목록은 저장소 메타데이터 설명을 바탕으로 쓴 한 줄 요약이다. README를 추가로 읽은 항목은 별도 표시했다. 코드 실행이나 기능 검증은 하지 않았다.
- 원 설명만으로 구체 용도를 분명히 알 수 없는 항목은 `세부 용도 미확인`으로 남겼다.

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
| [K-Dense-AI/scientific-agent-skills](https://github.com/K-Dense-AI/scientific-agent-skills) | AI 에이전트용 스킬·작업 지침 모음 | GitHub 설명만 확인 |
| [ai-boost/awesome-harness-engineering](https://github.com/ai-boost/awesome-harness-engineering) | AI 에이전트 실행·개발 도구 | GitHub 설명만 확인 |
| [volcengine/OpenViking](https://github.com/volcengine/OpenViking) | AI 에이전트용 스킬·작업 지침 모음 | GitHub 설명만 확인 |
| [rohitg00/agentmemory](https://github.com/rohitg00/agentmemory) | AI 에이전트 실행·개발 도구 | GitHub 설명만 확인 |
| [headroomlabs-ai/headroom](https://github.com/headroomlabs-ai/headroom) | AI 에이전트 실행·개발 도구 | GitHub 설명만 확인 |
| [diegosouzapw/OmniRoute](https://github.com/diegosouzapw/OmniRoute) | 언어 모델 실행·학습·활용 도구 | GitHub 설명만 확인 |
| [Graphify-Labs/graphify](https://github.com/Graphify-Labs/graphify) | AI 에이전트용 스킬·작업 지침 모음 | GitHub 설명만 확인 |
| [JustVugg/colibri](https://github.com/JustVugg/colibri) | 언어 모델 실행·학습·활용 도구 | GitHub 설명만 확인 |
| [browser-use/jev-ultrafast](https://github.com/browser-use/jev-ultrafast) | AI 에이전트 실행·개발 도구 | GitHub 설명만 확인 |
| [pacifio/atlas](https://github.com/pacifio/atlas) | AI 에이전트 실행·개발 도구 | GitHub 설명만 확인 |
| [THU-MAIC/OpenMAIC](https://github.com/THU-MAIC/OpenMAIC) | AI 에이전트 실행·개발 도구 | GitHub 설명만 확인 |
| [cobanov/awesome-fly](https://github.com/cobanov/awesome-fly) | 언어 모델 실행·학습·활용 도구 | GitHub 설명만 확인 |
| [trailhq/Graft](https://github.com/trailhq/Graft) | AI 에이전트 실행·개발 도구 | GitHub 설명만 확인 |
| [graykode/abtop](https://github.com/graykode/abtop) | AI 에이전트 실행·개발 도구 | GitHub 설명만 확인 |
| [tt-a1i/archify](https://github.com/tt-a1i/archify) | 움직임과 내보내기를 지원하는 HTML/SVG 아키텍처·흐름도 제작 스킬 | README 추가 확인 |
| [trycompai/crm](https://github.com/trycompai/crm) | AI 에이전트 실행·개발 도구 | GitHub 설명만 확인 |
| [macro-inc/macro](https://github.com/macro-inc/macro) | AI 에이전트 실행·개발 도구 | GitHub 설명만 확인 |
| [unslothai/unsloth](https://github.com/unslothai/unsloth) | 언어 모델 실행·학습·활용 도구 | GitHub 설명만 확인 |
| [lightningpixel/modly](https://github.com/lightningpixel/modly) | 언어 모델 실행·학습·활용 도구 | GitHub 설명만 확인 |
| [openai/codex](https://github.com/openai/codex) | AI 에이전트 실행·개발 도구 | GitHub 설명만 확인 |
| [earendil-works/pi](https://github.com/earendil-works/pi) | AI 에이전트 실행·개발 도구 | GitHub 설명만 확인 |
| [openinterpreter/openinterpreter](https://github.com/openinterpreter/openinterpreter) | AI 에이전트 실행·개발 도구 | GitHub 설명만 확인 |
| [HKUDS/Vibe-Trading](https://github.com/HKUDS/Vibe-Trading) | AI 에이전트 실행·개발 도구 | GitHub 설명만 확인 |
| [citrolabs/ego-lite](https://github.com/citrolabs/ego-lite) | AI 에이전트 실행·개발 도구 | GitHub 설명만 확인 |
| [mem0ai/mem0](https://github.com/mem0ai/mem0) | AI 에이전트 실행·개발 도구 | GitHub 설명만 확인 |
| [Yeachan-Heo/oh-my-claudecode](https://github.com/Yeachan-Heo/oh-my-claudecode) | AI 에이전트 실행·개발 도구 | GitHub 설명만 확인 |
| [lidge-jun/opencodex](https://github.com/lidge-jun/opencodex) | 언어 모델 실행·학습·활용 도구 | GitHub 설명만 확인 |
| [paperclipai/paperclip](https://github.com/paperclipai/paperclip) | AI 에이전트 실행·개발 도구 | GitHub 설명만 확인 |
| [Nutlope/hallmark](https://github.com/Nutlope/hallmark) | AI 에이전트용 스킬·작업 지침 모음 | GitHub 설명만 확인 |
| [TencentCloud/CubeSandbox](https://github.com/TencentCloud/CubeSandbox) | AI 에이전트 실행·개발 도구 | GitHub 설명만 확인 |
| [chatchat-space/Langchain-Chatchat](https://github.com/chatchat-space/Langchain-Chatchat) | AI 에이전트 실행·개발 도구 | GitHub 설명만 확인 |
| [pollen-robotics/AmazingHand](https://github.com/pollen-robotics/AmazingHand) | 언어 모델 실행·학습·활용 도구 | GitHub 설명만 확인 |
| [Panniantong/Agent-Reach](https://github.com/Panniantong/Agent-Reach) | AI 에이전트 실행·개발 도구 | GitHub 설명만 확인 |
| [google-research/timesfm](https://github.com/google-research/timesfm) | 언어 모델 실행·학습·활용 도구 | GitHub 설명만 확인 |
| [NVIDIA/SkillSpector](https://github.com/NVIDIA/SkillSpector) | AI 에이전트용 스킬·작업 지침 모음 | GitHub 설명만 확인 |
| [withastro/flue](https://github.com/withastro/flue) | AI 에이전트 실행·개발 도구 | GitHub 설명만 확인 |
| [stablyai/orca](https://github.com/stablyai/orca) | AI 에이전트 실행·개발 도구 | GitHub 설명만 확인 |
| [MengTo/Skills](https://github.com/MengTo/Skills) | AI 에이전트용 스킬·작업 지침 모음 | GitHub 설명만 확인 |
| [agentskills/agentskills](https://github.com/agentskills/agentskills) | AI 에이전트용 스킬·작업 지침 모음 | GitHub 설명만 확인 |
| [alirezarezvani/claude-skills](https://github.com/alirezarezvani/claude-skills) | AI 에이전트용 스킬·작업 지침 모음 | GitHub 설명만 확인 |
| [browser-use/browser-use](https://github.com/browser-use/browser-use) | AI 에이전트 실행·개발 도구 | GitHub 설명만 확인 |
| [lsdefine/GenericAgent](https://github.com/lsdefine/GenericAgent) | AI 에이전트 실행·개발 도구 | GitHub 설명만 확인 |
| [JCodesMore/ai-website-cloner-template](https://github.com/JCodesMore/ai-website-cloner-template) | AI 에이전트 실행·개발 도구 | GitHub 설명만 확인 |
| [xbtlin/ai-berkshire](https://github.com/xbtlin/ai-berkshire) | AI 에이전트 실행·개발 도구 | GitHub 설명만 확인 |
| [google-labs-code/stitch-skills](https://github.com/google-labs-code/stitch-skills) | AI 에이전트용 스킬·작업 지침 모음 | GitHub 설명만 확인 |
| [revfactory/harness](https://github.com/revfactory/harness) | AI 에이전트용 스킬·작업 지침 모음 | GitHub 설명만 확인 |
| [mukul975/Anthropic-Cybersecurity-Skills](https://github.com/mukul975/Anthropic-Cybersecurity-Skills) | AI 에이전트용 스킬·작업 지침 모음 | GitHub 설명만 확인 |
| [DietrichGebert/ponytail](https://github.com/DietrichGebert/ponytail) | AI 에이전트 실행·개발 도구 | GitHub 설명만 확인 |
| [JuliusBrussee/caveman](https://github.com/JuliusBrussee/caveman) | AI 에이전트 실행·개발 도구 | GitHub 설명만 확인 |
| [blader/humanizer](https://github.com/blader/humanizer) | AI 에이전트용 스킬·작업 지침 모음 | GitHub 설명만 확인 |
| [tesseract-ocr/tessdata](https://github.com/tesseract-ocr/tessdata) | 언어 모델 실행·학습·활용 도구 | GitHub 설명만 확인 |
| [microsoft/SkillOpt](https://github.com/microsoft/SkillOpt) | AI 에이전트용 스킬·작업 지침 모음 | GitHub 설명만 확인 |
| [nesquena/hermes-webui](https://github.com/nesquena/hermes-webui) | AI 에이전트 실행·개발 도구 | GitHub 설명만 확인 |
| [underlines/awesome-ml](https://github.com/underlines/awesome-ml) | 언어 모델 실행·학습·활용 도구 | GitHub 설명만 확인 |
| [mattpocock/skills](https://github.com/mattpocock/skills) | AI 에이전트용 스킬·작업 지침 모음 | GitHub 설명만 확인 |
| [eugeniughelbur/obsidian-second-brain](https://github.com/eugeniughelbur/obsidian-second-brain) | AI 에이전트 실행·개발 도구 | GitHub 설명만 확인 |
| [kepano/obsidian-skills](https://github.com/kepano/obsidian-skills) | AI 에이전트용 스킬·작업 지침 모음 | GitHub 설명만 확인 |
| [breferrari/obsidian-mind](https://github.com/breferrari/obsidian-mind) | AI 에이전트 실행·개발 도구 | GitHub 설명만 확인 |
| [VoltAgent/awesome-design-md](https://github.com/VoltAgent/awesome-design-md) | AI 에이전트 실행·개발 도구 | GitHub 설명만 확인 |
| [obra/superpowers](https://github.com/obra/superpowers) | AI 에이전트용 스킬·작업 지침 모음 | GitHub 설명만 확인 |
| [sykim52/colgraphrag](https://github.com/sykim52/colgraphrag) | 언어 모델 실행·학습·활용 도구 | GitHub 설명만 확인 |
| [Q00/ouroboros](https://github.com/Q00/ouroboros) | AI 에이전트 실행·개발 도구 | GitHub 설명만 확인 |
| [Yeachan-Heo/oh-my-codex](https://github.com/Yeachan-Heo/oh-my-codex) | AI 에이전트 실행·개발 도구 | GitHub 설명만 확인 |
| [msitarzewski/agency-agents](https://github.com/msitarzewski/agency-agents) | AI 에이전트 실행·개발 도구 | GitHub 설명만 확인 |
| [microsoft/ai-agents-for-beginners](https://github.com/microsoft/ai-agents-for-beginners) | AI 에이전트 실행·개발 도구 | GitHub 설명만 확인 |
| [NousResearch/hermes-agent](https://github.com/NousResearch/hermes-agent) | AI 에이전트 실행·개발 도구 | GitHub 설명만 확인 |
| [humantonylee/free-router](https://github.com/humantonylee/free-router) | 언어 모델 실행·학습·활용 도구 | GitHub 설명만 확인 |
| [affaan-m/ECC](https://github.com/affaan-m/ECC) | AI 에이전트용 스킬·작업 지침 모음 | GitHub 설명만 확인 |
| [ultraworkers/claw-code](https://github.com/ultraworkers/claw-code) | AI 에이전트 실행·개발 도구 | GitHub 설명만 확인 |
| [bytedance/deer-flow](https://github.com/bytedance/deer-flow) | AI 에이전트 실행·개발 도구 | GitHub 설명만 확인 |
| [AlexsJones/llmfit](https://github.com/AlexsJones/llmfit) | 언어 모델 실행·학습·활용 도구 | GitHub 설명만 확인 |
| [SillyTavern/SillyTavern](https://github.com/SillyTavern/SillyTavern) | 언어 모델 실행·학습·활용 도구 | GitHub 설명만 확인 |

### 로봇·3D·연구

| 저장소 | 한 줄 용도 | 근거 범위 |
|---|---|---|
| [amap-cvlab/ABot-Recon](https://github.com/amap-cvlab/ABot-Recon) | 영상에서 3D 장면을 복원하는 연구 코드 | GitHub 설명만 확인 |
| [AprilRobotics/apriltag](https://github.com/AprilRobotics/apriltag) | 로봇 학습·시뮬레이션·제어 관련 코드 | GitHub 설명만 확인 |
| [cactus-compute/needle](https://github.com/cactus-compute/needle) | 로봇 학습·시뮬레이션·제어 관련 코드 | GitHub 설명만 확인 |
| [hms-gymnopedie/IsaacSim_Setting](https://github.com/hms-gymnopedie/IsaacSim_Setting) | 로봇 학습·시뮬레이션·제어 관련 코드 | GitHub 설명만 확인 |
| [Zhefan-Xu/isaac-go2-ros2](https://github.com/Zhefan-Xu/isaac-go2-ros2) | 로봇 학습·시뮬레이션·제어 관련 코드 | GitHub 설명만 확인 |
| [unitreerobotics/unitree_rl_lab](https://github.com/unitreerobotics/unitree_rl_lab) | 로봇 학습·시뮬레이션·제어 관련 코드 | GitHub 설명만 확인 |
| [isaac-sim/IsaacSim](https://github.com/isaac-sim/IsaacSim) | 로봇 학습·시뮬레이션·제어 관련 코드 | GitHub 설명만 확인 |
| [isaac-sim/IsaacLab](https://github.com/isaac-sim/IsaacLab) | 로봇 학습·시뮬레이션·제어 관련 코드 | GitHub 설명만 확인 |
| [Robbyant/lingbot-map](https://github.com/Robbyant/lingbot-map) | 영상에서 3D 장면을 복원하는 연구 코드 | GitHub 설명만 확인 |
| [huggingface/lerobot](https://github.com/huggingface/lerobot) | 로봇 학습·시뮬레이션·제어 관련 코드 | GitHub 설명만 확인 |

### 개발 도구·기타

| 저장소 | 한 줄 용도 | 근거 범위 |
|---|---|---|
| [Maelic/RelateAnything](https://github.com/Maelic/RelateAnything) | 프로젝트 설명에 적힌 도구 또는 연구 구현물 (기능 세부는 README 확인 필요) | GitHub 설명만 확인 |
| [robbietilton/Compositor](https://github.com/robbietilton/Compositor) | 프로젝트 설명에 적힌 도구 또는 연구 구현물 (기능 세부는 README 확인 필요) | GitHub 설명만 확인 |
| [github/spec-kit](https://github.com/github/spec-kit) | 프로젝트 설명에 적힌 도구 또는 연구 구현물 (기능 세부는 README 확인 필요) | GitHub 설명만 확인 |
| [davila7/claude-code-templates](https://github.com/davila7/claude-code-templates) | 프로젝트 설명에 적힌 도구 또는 연구 구현물 (기능 세부는 README 확인 필요) | GitHub 설명만 확인 |
| [dreamurl/GPT-Bridge](https://github.com/dreamurl/GPT-Bridge) | 저장소 설명이 없어 세부 용도 미확인 · 세부 용도 미확인 | GitHub 설명만 확인 |
| [uppinote20/claude-dashboard](https://github.com/uppinote20/claude-dashboard) | 프로젝트 설명에 적힌 도구 또는 연구 구현물 (기능 세부는 README 확인 필요) | GitHub 설명만 확인 |
| [trycua/cua](https://github.com/trycua/cua) | 기기 조작·자동화 도구 | GitHub 설명만 확인 |
| [arclab-hku/Risky_gym](https://github.com/arclab-hku/Risky_gym) | 저장소 설명이 없어 세부 용도 미확인 · 세부 용도 미확인 | GitHub 설명만 확인 |
| [odoo/odoo](https://github.com/odoo/odoo) | 프로젝트 설명에 적힌 도구 또는 연구 구현물 (기능 세부는 README 확인 필요) | GitHub 설명만 확인 |
| [tamaratran/fast-jev-compaction](https://github.com/tamaratran/fast-jev-compaction) | 프로젝트 설명에 적힌 도구 또는 연구 구현물 (기능 세부는 README 확인 필요) | GitHub 설명만 확인 |
| [nv-tlabs/3dgrut](https://github.com/nv-tlabs/3dgrut) | 3D Gaussian 표현·렌더링 도구 | GitHub 설명만 확인 |
| [jgraph/drawio-desktop](https://github.com/jgraph/drawio-desktop) | draw.io 데스크톱 앱 | README 추가 확인 |
| [D4Vinci/Scrapling](https://github.com/D4Vinci/Scrapling) | 웹 브라우저 자동화·수집 도구 | GitHub 설명만 확인 |
| [dgtlmoon/changedetection.io](https://github.com/dgtlmoon/changedetection.io) | 프로젝트 설명에 적힌 도구 또는 연구 구현물 (기능 세부는 README 확인 필요) | GitHub 설명만 확인 |
| [every-app/open-seo](https://github.com/every-app/open-seo) | 프로젝트 설명에 적힌 도구 또는 연구 구현물 (기능 세부는 README 확인 필요) | GitHub 설명만 확인 |
| [abi/screenshot-to-code](https://github.com/abi/screenshot-to-code) | 프로젝트 설명에 적힌 도구 또는 연구 구현물 (기능 세부는 README 확인 필요) | GitHub 설명만 확인 |
| [pixel-agents-hq/pixel-agents](https://github.com/pixel-agents-hq/pixel-agents) | 프로젝트 설명에 적힌 도구 또는 연구 구현물 (기능 세부는 README 확인 필요) | GitHub 설명만 확인 |
| [semantica-agi/semantica](https://github.com/semantica-agi/semantica) | 프로젝트 설명에 적힌 도구 또는 연구 구현물 (기능 세부는 README 확인 필요) | GitHub 설명만 확인 |
| [megadose/holehe](https://github.com/megadose/holehe) | 프로젝트 설명에 적힌 도구 또는 연구 구현물 (기능 세부는 README 확인 필요) | GitHub 설명만 확인 |
| [omacom/omarchy](https://github.com/omacom/omarchy) | 프로젝트 설명에 적힌 도구 또는 연구 구현물 (기능 세부는 README 확인 필요) | GitHub 설명만 확인 |
| [public-apis/public-apis](https://github.com/public-apis/public-apis) | 프로젝트 설명에 적힌 도구 또는 연구 구현물 (기능 세부는 README 확인 필요) | GitHub 설명만 확인 |
| [NVIDIA-Omniverse/omniverse-labs](https://github.com/NVIDIA-Omniverse/omniverse-labs) | 프로젝트 설명에 적힌 도구 또는 연구 구현물 (기능 세부는 README 확인 필요) | GitHub 설명만 확인 |
| [nyrahealth/CrisperWhisper](https://github.com/nyrahealth/CrisperWhisper) | 음성 생성 또는 전사 도구 | GitHub 설명만 확인 |
| [supabase/supabase](https://github.com/supabase/supabase) | 데이터베이스·백엔드 개발 플랫폼 | GitHub 설명만 확인 |
| [OpenCut-app/OpenCut](https://github.com/OpenCut-app/OpenCut) | 프로젝트 설명에 적힌 도구 또는 연구 구현물 (기능 세부는 README 확인 필요) | GitHub 설명만 확인 |
| [HKUDS/DeepTutor](https://github.com/HKUDS/DeepTutor) | 프로젝트 설명에 적힌 도구 또는 연구 구현물 (기능 세부는 README 확인 필요) | GitHub 설명만 확인 |
| [vinta/awesome-python](https://github.com/vinta/awesome-python) | 프로젝트 설명에 적힌 도구 또는 연구 구현물 (기능 세부는 README 확인 필요) | GitHub 설명만 확인 |
| [star-history/star-history](https://github.com/star-history/star-history) | GitHub 저장소의 Star 추이를 그래프로 보여주는 도구 | README 추가 확인 |
| [microsoft/vscode](https://github.com/microsoft/vscode) | 프로젝트 설명에 적힌 도구 또는 연구 구현물 (기능 세부는 README 확인 필요) | GitHub 설명만 확인 |
| [microsoft/playwright-cli](https://github.com/microsoft/playwright-cli) | 프로젝트 설명에 적힌 도구 또는 연구 구현물 (기능 세부는 README 확인 필요) | GitHub 설명만 확인 |
| [microsoft/playwright-python](https://github.com/microsoft/playwright-python) | 프로젝트 설명에 적힌 도구 또는 연구 구현물 (기능 세부는 README 확인 필요) | GitHub 설명만 확인 |
| [microsoft/playwright-mcp](https://github.com/microsoft/playwright-mcp) | 프로젝트 설명에 적힌 도구 또는 연구 구현물 (기능 세부는 README 확인 필요) | GitHub 설명만 확인 |
| [microsoft/playwright](https://github.com/microsoft/playwright) | 프로젝트 설명에 적힌 도구 또는 연구 구현물 (기능 세부는 README 확인 필요) | GitHub 설명만 확인 |
| [Julian-adv/OpenMMO](https://github.com/Julian-adv/OpenMMO) | 저장소 설명이 없어 세부 용도 미확인 · 세부 용도 미확인 | GitHub 설명만 확인 |
| [tmux/tmux](https://github.com/tmux/tmux) | 프로젝트 설명에 적힌 도구 또는 연구 구현물 (기능 세부는 README 확인 필요) | GitHub 설명만 확인 |
| [techwithanant/saras_ai_robot_v2](https://github.com/techwithanant/saras_ai_robot_v2) | 저장소 설명이 없어 세부 용도 미확인 · 세부 용도 미확인 | GitHub 설명만 확인 |
| [Saqoosha/ccusage-menubar](https://github.com/Saqoosha/ccusage-menubar) | 저장소 설명이 없어 세부 용도 미확인 · 세부 용도 미확인 | GitHub 설명만 확인 |
| [edwardkim/rhwp](https://github.com/edwardkim/rhwp) | 개발 환경·코딩 도구 | GitHub 설명만 확인 |
| [Leonxlnx/taste-skill](https://github.com/Leonxlnx/taste-skill) | 프로젝트 설명에 적힌 도구 또는 연구 구현물 (기능 세부는 README 확인 필요) | GitHub 설명만 확인 |
| [elder-plinius/G0DM0D3](https://github.com/elder-plinius/G0DM0D3) | 프로젝트 설명에 적힌 도구 또는 연구 구현물 (기능 세부는 README 확인 필요) | GitHub 설명만 확인 |
| [elder-plinius/L1B3RT4S](https://github.com/elder-plinius/L1B3RT4S) | 프로젝트 설명에 적힌 도구 또는 연구 구현물 (기능 세부는 README 확인 필요) | GitHub 설명만 확인 |
| [elder-plinius/CL4R1T4S](https://github.com/elder-plinius/CL4R1T4S) | 프로젝트 설명에 적힌 도구 또는 연구 구현물 (기능 세부는 README 확인 필요) | GitHub 설명만 확인 |
| [Zackriya-Solutions/meetily](https://github.com/Zackriya-Solutions/meetily) | 음성 생성 또는 전사 도구 | GitHub 설명만 확인 |
| [gronxb/codex-relay](https://github.com/gronxb/codex-relay) | 프로젝트 설명에 적힌 도구 또는 연구 구현물 (기능 세부는 README 확인 필요) | GitHub 설명만 확인 |
| [fivetaku/insane-search](https://github.com/fivetaku/insane-search) | 프로젝트 설명에 적힌 도구 또는 연구 구현물 (기능 세부는 README 확인 필요) | GitHub 설명만 확인 |
| [usestrix/strix](https://github.com/usestrix/strix) | 보안 점검·취약점 분석 도구 | GitHub 설명만 확인 |
| [openai/codex-plugin-cc](https://github.com/openai/codex-plugin-cc) | 프로젝트 설명에 적힌 도구 또는 연구 구현물 (기능 세부는 README 확인 필요) | GitHub 설명만 확인 |
| [MarcSkovMadsen/awesome-streamlit](https://github.com/MarcSkovMadsen/awesome-streamlit) | 프로젝트 설명에 적힌 도구 또는 연구 구현물 (기능 세부는 README 확인 필요) | GitHub 설명만 확인 |
| [Adam-CAD/CADAM](https://github.com/Adam-CAD/CADAM) | 프로젝트 설명에 적힌 도구 또는 연구 구현물 (기능 세부는 README 확인 필요) | GitHub 설명만 확인 |
| [helloianneo/ian-xiaohei-illustrations](https://github.com/helloianneo/ian-xiaohei-illustrations) | 프로젝트 설명에 적힌 도구 또는 연구 구현물 (기능 세부는 README 확인 필요) | GitHub 설명만 확인 |
| [jamiepine/voicebox](https://github.com/jamiepine/voicebox) | 음성 생성 또는 전사 도구 | GitHub 설명만 확인 |
| [mgth/LittleBigMouse](https://github.com/mgth/LittleBigMouse) | 프로젝트 설명에 적힌 도구 또는 연구 구현물 (기능 세부는 README 확인 필요) | GitHub 설명만 확인 |
| [nikopueringer/CorridorKey](https://github.com/nikopueringer/CorridorKey) | 프로젝트 설명에 적힌 도구 또는 연구 구현물 (기능 세부는 README 확인 필요) | GitHub 설명만 확인 |
| [epoko77-ai/im-not-ai](https://github.com/epoko77-ai/im-not-ai) | 프로젝트 설명에 적힌 도구 또는 연구 구현물 (기능 세부는 README 확인 필요) | GitHub 설명만 확인 |
| [SOMJANG/Mecab-ko-for-Google-Colab](https://github.com/SOMJANG/Mecab-ko-for-Google-Colab) | 프로젝트 설명에 적힌 도구 또는 연구 구현물 (기능 세부는 README 확인 필요) | GitHub 설명만 확인 |
| [smilegate-ai/korean_unsmile_dataset](https://github.com/smilegate-ai/korean_unsmile_dataset) | 저장소 설명이 없어 세부 용도 미확인 · 세부 용도 미확인 | GitHub 설명만 확인 |
| [ahastudio/til](https://github.com/ahastudio/til) | 프로젝트 설명에 적힌 도구 또는 연구 구현물 (기능 세부는 README 확인 필요) | GitHub 설명만 확인 |
| [VAST-AI-Research/TripoSplat](https://github.com/VAST-AI-Research/TripoSplat) | 3D Gaussian 표현·렌더링 도구 | GitHub 설명만 확인 |
| [EveryInc/compound-engineering-plugin](https://github.com/EveryInc/compound-engineering-plugin) | 프로젝트 설명에 적힌 도구 또는 연구 구현물 (기능 세부는 README 확인 필요) | GitHub 설명만 확인 |
| [ZhengPeng7/BiRefNet](https://github.com/ZhengPeng7/BiRefNet) | 프로젝트 설명에 적힌 도구 또는 연구 구현물 (기능 세부는 README 확인 필요) | GitHub 설명만 확인 |
| [QwenLM/Qwen3-TTS](https://github.com/QwenLM/Qwen3-TTS) | 음성 생성 또는 전사 도구 | GitHub 설명만 확인 |
| [microsoft/PowerToys](https://github.com/microsoft/PowerToys) | 주제별 도구·자료 큐레이션 목록 | GitHub 설명만 확인 |
| [Netflix/void-model](https://github.com/Netflix/void-model) | 저장소 설명이 없어 세부 용도 미확인 · 세부 용도 미확인 | GitHub 설명만 확인 |
| [slopus/happy](https://github.com/slopus/happy) | 음성 생성 또는 전사 도구 | GitHub 설명만 확인 |
| [fivetaku/cc101](https://github.com/fivetaku/cc101) | 프로젝트 설명에 적힌 도구 또는 연구 구현물 (기능 세부는 README 확인 필요) | GitHub 설명만 확인 |
| [NomaDamas/k-skill](https://github.com/NomaDamas/k-skill) | 프로젝트 설명에 적힌 도구 또는 연구 구현물 (기능 세부는 README 확인 필요) | GitHub 설명만 확인 |
| [microsoft/VibeVoice](https://github.com/microsoft/VibeVoice) | 음성 생성 또는 전사 도구 | GitHub 설명만 확인 |
| [supertone-oss-archive/supertonic](https://github.com/supertone-oss-archive/supertonic) | 음성 생성 또는 전사 도구 | GitHub 설명만 확인 |
| [openclaw/openclaw](https://github.com/openclaw/openclaw) | 프로젝트 설명에 적힌 도구 또는 연구 구현물 (기능 세부는 README 확인 필요) | GitHub 설명만 확인 |
| [code-yeongyu/oh-my-openagent](https://github.com/code-yeongyu/oh-my-openagent) | 프로젝트 설명에 적힌 도구 또는 연구 구현물 (기능 세부는 README 확인 필요) | GitHub 설명만 확인 |
| [codecrafters-io/build-your-own-x](https://github.com/codecrafters-io/build-your-own-x) | 프로젝트 설명에 적힌 도구 또는 연구 구현물 (기능 세부는 README 확인 필요) | GitHub 설명만 확인 |
| [ultralytics/ultralytics](https://github.com/ultralytics/ultralytics) | 프로젝트 설명에 적힌 도구 또는 연구 구현물 (기능 세부는 README 확인 필요) | GitHub 설명만 확인 |
| [SKN19-3rd-4team/zip-fit](https://github.com/SKN19-3rd-4team/zip-fit) | 프로젝트 설명에 적힌 도구 또는 연구 구현물 (기능 세부는 README 확인 필요) | GitHub 설명만 확인 |
| [SKNetworks-AI19-250818/.github](https://github.com/SKNetworks-AI19-250818/.github) | 저장소 설명이 없어 세부 용도 미확인 · 세부 용도 미확인 | GitHub 설명만 확인 |
| [nari-labs/dia](https://github.com/nari-labs/dia) | 음성 생성 또는 전사 도구 | GitHub 설명만 확인 |

### 문서·검색·데이터

| 저장소 | 한 줄 용도 | 근거 범위 |
|---|---|---|
| [StarTrail-org/LEANN](https://github.com/StarTrail-org/LEANN) | 문서 검색과 생성(RAG) 도구 | GitHub 설명만 확인 |
| [docling-project/docling](https://github.com/docling-project/docling) | 문서 변환·처리 도구 | GitHub 설명만 확인 |
| [HKUDS/LightRAG](https://github.com/HKUDS/LightRAG) | 문서 검색과 생성(RAG) 도구 | GitHub 설명만 확인 |
| [asgeirtj/system_prompts_leaks](https://github.com/asgeirtj/system_prompts_leaks) | 문서 변환·처리 도구 | GitHub 설명만 확인 |
| [microsoft/markitdown](https://github.com/microsoft/markitdown) | 문서 변환·처리 도구 | GitHub 설명만 확인 |
| [ekimetrics/adaptive-chunking](https://github.com/ekimetrics/adaptive-chunking) | 문서 검색과 생성(RAG) 도구 | GitHub 설명만 확인 |
| [DeusData/codebase-memory-mcp](https://github.com/DeusData/codebase-memory-mcp) | 문서 검색과 생성(RAG) 도구 | GitHub 설명만 확인 |
| [opendataloader-project/opendataloader-pdf](https://github.com/opendataloader-project/opendataloader-pdf) | 문서 변환·처리 도구 | GitHub 설명만 확인 |

### 발표·시각화·미디어

| 저장소 | 한 줄 용도 | 근거 범위 |
|---|---|---|
| [google/artemis](https://github.com/google/artemis) | 다이어그램·아키텍처 시각화 도구 | GitHub 설명만 확인 |
| [jgraph/drawio](https://github.com/jgraph/drawio) | 브라우저에서 다이어그램을 그리는 편집기 | README 추가 확인 |
| [huawei-bayerlab/marigold-v2](https://github.com/huawei-bayerlab/marigold-v2) | 단일 이미지의 깊이 추정 모델 | GitHub 설명만 확인 |
| [prs-eth/Marigold](https://github.com/prs-eth/Marigold) | 단일 이미지의 깊이 추정 모델 | GitHub 설명만 확인 |
| [PaddlePaddle/PaddleOCR](https://github.com/PaddlePaddle/PaddleOCR) | 이미지·문서 문자 인식 도구 | GitHub 설명만 확인 |
| [hugohe3/ppt-master](https://github.com/hugohe3/ppt-master) | 문서나 주제에서 애니메이션·차트 포함 PowerPoint를 만드는 도구 | README 추가 확인 |
| [fabio-sim/Depth-Anything-ONNX](https://github.com/fabio-sim/Depth-Anything-ONNX) | 단일 이미지의 깊이 추정 모델 | GitHub 설명만 확인 |
| [DepthAnything/Depth-Anything-V2](https://github.com/DepthAnything/Depth-Anything-V2) | 단일 이미지의 깊이 추정 모델 | GitHub 설명만 확인 |
| [larashero3-dotcom/lieflat-charts](https://github.com/larashero3-dotcom/lieflat-charts) | 데이터를 대화형 HTML 차트로 바꾸는 에이전트용 시각화 스킬 | README 추가 확인 |
| [ant-research/4DAnyone](https://github.com/ant-research/4DAnyone) | 영상 제작·편집 도구 | GitHub 설명만 확인 |
| [3b1b/manim](https://github.com/3b1b/manim) | 수학 설명 영상을 위한 코드 기반 애니메이션 엔진 | README 추가 확인 |
| [cathrynlavery/diagram-design](https://github.com/cathrynlavery/diagram-design) | HTML/SVG 편집형 다이어그램 디자인 스킬 | README 추가 확인 |
| [PrimeIntellect-ai/prime-agent](https://github.com/PrimeIntellect-ai/prime-agent) | 다이어그램·아키텍처 시각화 도구 | GitHub 설명만 확인 |
| [tensorflow/tensorboard](https://github.com/tensorflow/tensorboard) | 데이터 시각화·대시보드 도구 | GitHub 설명만 확인 |
| [GuanYixuan/pyCapCut](https://github.com/GuanYixuan/pyCapCut) | 영상 제작·편집 도구 | GitHub 설명만 확인 |
| [HKUDS/nanobot](https://github.com/HKUDS/nanobot) | 다이어그램·아키텍처 시각화 도구 | GitHub 설명만 확인 |
| [heygen-com/hyperframes](https://github.com/heygen-com/hyperframes) | HTML/CSS와 프레임 단위 애니메이션을 탐색형 슬라이드 또는 결정적 MP4로 만드는 프레임워크 | README 추가 확인 |
| [poloclub/transformer-explainer](https://github.com/poloclub/transformer-explainer) | 데이터 시각화·대시보드 도구 | GitHub 설명만 확인 |
| [bradautomates/claude-video](https://github.com/bradautomates/claude-video) | 영상 제작·편집 도구 | GitHub 설명만 확인 |
| [koala73/worldmonitor](https://github.com/koala73/worldmonitor) | 데이터 시각화·대시보드 도구 | GitHub 설명만 확인 |
| [MengTo/Spring](https://github.com/MengTo/Spring) | 애니메이션 제작 도구 | GitHub 설명만 확인 |
| [n8n-io/n8n](https://github.com/n8n-io/n8n) | 다이어그램·아키텍처 시각화 도구 | GitHub 설명만 확인 |
| [browser-use/video-use](https://github.com/browser-use/video-use) | 영상 제작·편집 도구 | GitHub 설명만 확인 |
| [NatronGitHub/Natron](https://github.com/NatronGitHub/Natron) | 영상 제작·편집 도구 | GitHub 설명만 확인 |
| [calesthio/OpenMontage](https://github.com/calesthio/OpenMontage) | 영상 제작·편집 도구 | GitHub 설명만 확인 |
| [palmier-io/palmier-pro](https://github.com/palmier-io/palmier-pro) | 영상 제작·편집 도구 | GitHub 설명만 확인 |
| [penpot/penpot](https://github.com/penpot/penpot) | 디자인·이미지 제작 도구 | GitHub 설명만 확인 |
| [theamusing/perfectPixel](https://github.com/theamusing/perfectPixel) | 디자인·이미지 제작 도구 | GitHub 설명만 확인 |
| [aldegad/sprite-gen](https://github.com/aldegad/sprite-gen) | 애니메이션 제작 도구 | GitHub 설명만 확인 |
| [UB-Mannheim/tesseract](https://github.com/UB-Mannheim/tesseract) | 이미지·문서 문자 인식 도구 | GitHub 설명만 확인 |
| [Anil-matcha/Open-Generative-AI](https://github.com/Anil-matcha/Open-Generative-AI) | 영상 제작·편집 도구 | GitHub 설명만 확인 |
| [garrytan/gstack](https://github.com/garrytan/gstack) | 디자인·이미지 제작 도구 | GitHub 설명만 확인 |

## 출처

- [GitHub Star API: 사용자 Star 저장소](https://api.github.com/user/starred)
- 각 행의 저장소 링크에 있는 GitHub description. README 추가 확인 표시는 해당 저장소 README 기준.

## 판 이력

| 판 | 언제 | 무엇이 바뀌었나 | 근거 |
|---|---|---|---|
| v0.1 | 2026-09-29 | Star 저장소 197개 목록과 발표 후보 조사 초안 작성 | 이슈 #503 |
