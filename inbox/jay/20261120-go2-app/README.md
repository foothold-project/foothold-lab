# Unitree Go 1.12.10 분석과 2.0.0 비교 실행 기록

> 분류: 가이드
> 작성: 오흥재 · 2026-11-20
> 근거: 이슈 #923 · ai-lx01의 실제 설치·분석 영수증
> 요지: APK 바이트와 분석 도구를 고정해 확인된 결과를 다시 계산한다.
> 상태: 실행 확인됨 · 원본 APK와 큰 자료는 로컬 data에 보관
> 판: v1.1

실행 담당: analyst-lx. 아래 도구 연결·원자료 대조는 `확인됨`이다.

[분석 보고서](REPORT-UNITREE-1.12.10.md)를 먼저 읽는다. 이전 2.0.0 분석은 [10/13 보고서](../20261013-go2-app-study/REPORT-astra-10.md)다.

21:40 추가 의뢰의 공식 국제판 재확인과 버전 차이는 [2.0.0 비교 보고서](REPORT-2.0.0-DIFF.md)에 있다.

## 설치 위치

| 대상 | 설치 또는 보관 위치 |
|---|---|
| REA npm 6.10.1 | `/home/jay/.local/share/rea-mcp/node_modules/rea-agents/scripts/rea.mjs` |
| Codex MCP 등록 | `/home/jay/.codex/config.toml`의 `mcp_servers.rea`와 `mcp_servers.rea.env` |
| Java 21.0.13.1+2 | `/home/jay/data/tools/jdk/jdk-21.0.13.1+2` |
| JADX provider 0.7.1 | `/home/jay/data/tools/dl/jadx-headless-mcp-0.7.1-all.jar` |
| apktool | `/home/jay/data/tools/rea/apktool` |
| craft-anything 소스 | `/home/jay/mai/projects/craft-anything`, HEAD `73771bfacf520a159764ea9f8dd85d9bdf09c86b` |
| Rust CLI | `/home/jay/.local/bin/craft-anything` |
| 빌드 실체 | `/home/jay/data/go2-app-study-20261120/craft-target/release/craft-anything-cli` |
| APK | `/home/jay/mai/projects/tutorial-go2/UnitreeGo_1.12.10.apk` |
| 새 분석 원자료 | `/home/jay/data/go2-app-study-20261120/` |

이 설치는 현재 기기의 절대경로를 사용한다. 다른 기기에서는 경로를 맞추고 원본 APK 해시부터 대조해야 한다. 동료의 `/home/jay/data/app-design-1119/apk/work/`는 이 작업이 수정하지 않는다.

REA의 설치·등록에 사용한 명령은 다음과 같다. 이미 설치되어 있으므로 분석을 반복할 때 재설치할 필요는 없다.

```bash
npm install --prefix /home/jay/.local/share/rea-mcp rea-agents@6.10.1
node /home/jay/.local/share/rea-mcp/node_modules/rea-agents/scripts/rea.mjs setup --client codex --yes --json
```

등록한 MCP는 `/usr/bin/node`로 위 entry의 `mcp` 명령을 실행한다. provider 환경은 `JAVA_HOME`, `REA_JADX_MCP_JAR`, `REA_APKTOOL_COMMAND`, `REA_JADX_HEAP_MIB=4096`, 분석 data 아래의 `TMPDIR`다. 관련 없는 설정의 전후 구조가 동일함을 검증했다. 세션은 재시작하지 않았다. 현재 세션에서 실제 MCP 분석은 `mcp_probe.py`를 통한 stdio 연결로 검증했다.

Rust 빌드 명령과 원본 commit·실행 파일 SHA는 [installation.json](evidence/installation.json)에 있다.

```bash
CARGO_TARGET_DIR=/home/jay/data/go2-app-study-20261120/craft-target CARGO_BUILD_JOBS=4 \
  /home/jay/.cargo/bin/cargo build --locked --release -p craft-anything-cli \
  --manifest-path /home/jay/mai/projects/craft-anything/Cargo.toml
```

## 실제 MCP와 craft 호출

아래는 이 worktree를 cwd로 한 명령이다. args 파일에는 원본 APK 경로·조회 범위만 있으며 자격 증명은 없다. 모든 응답 원문은 data 아래에 저장한다.

```bash
python3 inbox/jay/20261120-go2-app/mcp_probe.py \
  --tool inspect_android_package \
  --args /home/jay/data/go2-app-study-20261120/evidence/args-apk.json \
  --output /home/jay/data/go2-app-study-20261120/evidence/rea-package.json

/home/jay/.local/bin/craft-anything --deep \
  --project /home/jay/data/go2-app-study-20261120/craft-project --format json \
  android-package-show --path /home/jay/mai/projects/tutorial-go2/UnitreeGo_1.12.10.apk
```

`--deep`은 파일 내부의 정적 검사를 허용하는 craft 옵션이다. 보호 코드 해독이나 앱 실행을 뜻하지 않는다. **craft는 종료 코드 0이어도 JSON에 `error`가 있으면 실패로 취급한다.** 도구 결과의 authority·limitations도 함께 읽는다.

이번에 실제 호출한 REA 도구는 `analyze_javascript_application`(답을 아는 fixture), `inspect_android_package`, `search_android_classes`, `decode_android_resources`, `inspect_apk_signature`다. craft는 `core-archive-show`(알려진 ZIP), `android-package-show`, `android-classes-find`, `android-app-graph-build`, `formats-wasm-module-show`를 사용했다. 하나가 된다고 다른 도구까지 모두 검증되었다고 쓰지 않는다.

## 같은 원자료에서 표와 수치를 다시 계산

```bash
python3 inbox/jay/20261120-go2-app/summarize.py \
  --apk /home/jay/mai/projects/tutorial-go2/UnitreeGo_1.12.10.apk \
  --data /home/jay/data/go2-app-study-20261120 \
  --output /home/jay/data/go2-app-study-20261120/recomputed
```

이 명령은 APK 전체 SHA·CRC, 두 도구의 manifest identity, DEX class 수, 알려진 IPC와 ZIP 입력, WASM SHA·시험 결과를 대조한다. 출력에는 허용 목록의 UI 문자열만 포함한다. 원본의 임의 문자열·계정 정보·키를 덤프하지 않는다.

TSV의 `null`은 원 도구가 값을 지정하지 않았다는 뜻이며 `false`가 아니다. 줄끝은 LF다.

## 원 WASM의 답을 아는 입력

10/13 스크립트를 byte 그대로 `data/wasm-fixtures/fixtures.cjs`에 복사했다. 상대경로가 가리키는 `data/extracted/assets/dist/assets/`의 파일은 이번 APK에서 추출한 것이다. 스크립트에 입력 WASM SHA 단언이 들어 있다.

```bash
node --max-old-space-size=128 --wasm-max-mem-pages=1536 \
  /home/jay/data/go2-app-study-20261120/wasm-fixtures/fixtures.cjs points
node --max-old-space-size=128 --wasm-max-mem-pages=1536 \
  /home/jay/data/go2-app-study-20261120/wasm-fixtures/fixtures.cjs mesh
```

15+13건 통과. WASM에 네트워크·파일·프로세스 API를 연결하지 않았고, 함수 호출마다 2초 timeout을 둔다. Node old-space 한도는 전체 프로세스 RSS 한도와 다르다. 실기 입력이나 앱 화면 실행 시험은 아니다.

## 기록과 인계

- 이슈: [#923](https://github.com/foothold-project/foothold-lab/issues/923). 연속 작업 인계 #555에 연결.
- app-design-lx에게 보고서·해시·제한을 orchestration으로 전달한다. 상대의 독립 분석 파일은 덮지 않는다.
- 큰 APK·GLB·WASM·원 라이브러리는 git에 넣지 않는다. [자료 해시 목록](evidence/RAW-EVIDENCE-SHA256SUMS)으로 원본을 대조한다.
- 원자료를 다시 실행해 덮어쓰면 evidence ID나 환경 필드가 바뀔 수 있다. 당시 원본 검증에는 당시 해시 목록을 사용하고, 새 실행 결과는 새 경로에 보관한다.

## 변경 이력

| 판 | 날짜 | 내용 |
|---|---|---|
| v1.0 | 2026-11-20 | 설치 위치·실제 MCP 호출·분석 재계산·WASM 재현 명령 |
| v1.1 | 2026-11-20 | 공식 국제판 2.0.0 직접 해시 대조와 버전 비교 보고서 연결 |
