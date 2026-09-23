# 에이전트 코딩의 컨텍스트 관리: 긴 세션을 나누고 이어가는 방법

> 분류: 리서치
> 작성: jay · 2026-09-23 18:05
> 근거: Anthropic·OpenAI 공식 문서, 공개 저장소, 개발자 공개 사례
> 요지: 긴 대화 전체를 기억시키기보다 현재 작업에 필요한 정보만 선택하고, 검증 가능한 상태를 파일로 남겨 새 컨텍스트에서 다시 읽게 하는 편이 안정적이다.
> 상태: 조사 초안
> 판: v1.0

## 요약

**확인됨.** 컨텍스트 관리는 한 번의 긴 프롬프트를 잘 쓰는 문제가 아니라, 모델 입력에 무엇을 언제 포함하고 오래된 정보를 어떻게 정리하며 세션 사이에 어떤 상태를 보존할지 설계하는 문제다. Anthropic은 이를 `context engineering`이라 부르고, 대표 접근으로 `compaction`, 외부 노트에 쓰는 `agentic memory`, `sub-agent` 분리를 설명한다. OpenAI의 Codex 엔지니어링 글은 지침 한 파일을 백과사전처럼 키우기보다 짧은 `AGENTS.md`를 지도처럼 쓰고, 근거가 되는 지식은 구조화된 문서에 두라고 보고한다.

**실무 판단.** 자동 `compact`를 금지하는 것보다, 작업 경계에서 상태를 파일로 저장하고 그 파일을 기준으로 새 세션을 여는 절차를 기본값으로 삼는 편이 사용자의 요구에 잘 맞는다. 세션 안에서 압축이 필요하면 목적, 결정, 현재 상태, 미해결 문제, 다음 행동을 보존하라고 지정한 뒤, 압축 뒤 파일과 실제 저장소 상태를 대조한다. `compact`는 요약이고 체크포인트 파일은 검증 가능한 작업 기록이라는 역할 구분이 핵심이다.

## 컨텍스트 관리 기법

| 기법 | 해결하는 문제 | 남는 한계 |
|---|---|---|
| `Context engineering` | 시스템 지침, 대화, 도구 설명, 외부 자료 중 이번 추론에 들어갈 구성을 관리한다. | 기법 하나의 이름이라기보다 설계 관점이다. 무엇이 관련 있는지는 작업에 맞춰 골라야 한다. 컨텍스트가 커져도 성능이 계속 선형으로 유지된다고 보장하지 않는다. |
| `Compaction` / 요약 압축 | 대화가 한도에 닿기 전에 이전 이력을 짧은 표현으로 바꾸어 같은 작업을 이어가게 한다. | 요약 과정에서 정확한 수치, 예외, 실패 이유, 제약이 빠질 수 있다. 압축 직전의 원문이 꼭 필요한 작업이면 원문을 별도 보존해야 한다. |
| 도구 결과 정리 | 이미 확인한 대형 로그나 파일 전문처럼 다시 보낼 필요가 적은 입력을 제거하거나 외부 참조로 바꿔 토큰을 회수한다. | 재확인이 필요할 때 결과를 다시 찾아야 한다. 어떤 데이터가 정리되는지는 에이전트 런타임마다 다르다. Anthropic은 이를 compaction의 가벼운 방법으로 설명한다. |
| 구조화 노트 / `agentic memory` | 진행 상태, 결정과 근거, 다음 단계를 파일이나 메모리 저장소에 적어 컨텍스트 초기화 뒤 이어간다. | 노트가 오래되거나 여러 파일에 중복되면 상충하는 상태가 만들어진다. 기록만 하고 재독·대조하지 않으면 잘못된 기억이 된다. |
| `CLAUDE.md` / `AGENTS.md` | 저장소 규칙, 자주 반복하는 명령, 아키텍처 경로 등 세션마다 필요한 지속 지침을 주입한다. | 매 세션 주입되는 파일이 길어질수록 실제 작업에 쓸 공간이 줄고, 내용이 낡으면 잘못된 행동을 유도한다. 지침 파일은 실행 강제 장치가 아니다. |
| `Sub-agent offloading` | 검색, 로그 읽기, 독립 조사처럼 결과만 필요하고 원문은 본 대화에 필요 없는 일을 별도 컨텍스트에 맡긴다. | 조사 결과의 선별과 전달 과정에서 누락이 생길 수 있고, 태스크 분해와 검토에 추가 비용이 든다. 공유 상태를 함께 편집하는 일에는 부적절할 수 있다. |
| 세션 분할과 handoff | 한 세션을 논리적 작업 단위로 제한하고 새 세션이 상태 파일부터 읽도록 해 누적된 잡음을 줄인다. | 새 세션의 초기화 비용이 든다. handoff가 불완전하면 사람이 다시 설명하거나 탐색해야 한다. |
| `RAG over transcript` / 대화 검색 | 전체 과거 대화를 항상 싣지 않고, 검색 질의와 관련된 과거 메시지나 요약만 가져온다. | 일반적인 단일 제품 표준이라기보다 검색 설계 패턴이다. 검색이 누락하거나 무관한 항목을 가져올 수 있고, 원문·요약·현재 코드가 서로 어긋날 수 있다. 출처 메시지와 시점 확인이 필요하다. |

Anthropic은 컨텍스트가 커지면 `context rot`, 곧 입력이 길수록 필요한 정보를 안정적으로 집어내기 어려워지는 문제를 설명한다. 이 표현은 모든 모델·작업에서 같은 임계값이 입증됐다는 뜻이 아니다. 메시지는 컨텍스트를 무한한 저장소로 취급하지 말고 관련 정보만 남기라는 설계 원칙으로 읽는 것이 타당하다. [Anthropic, Effective context engineering for AI agents](https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents)

## 공식 문서가 권하는 운영 방식

### Anthropic

- `CLAUDE.md`에는 프로젝트 표준, 공통 명령, 아키텍처 같이 매 세션 알아야 할 지침을 둔다. 사용자 선호와 프로젝트 메모리, 자동 메모리는 용도를 나눈다. 큰 저장소는 주제·경로별로 규칙을 쪼개 필요한 부분만 불러온다. 최신 공식 설명은 자동 메모리의 세션 주입량도 제한한다고 명시한다. [Claude Code memory](https://code.claude.com/docs/en/memory)
- 일의 상태를 넘길 때는 압축만 믿지 말고 분명한 파일 아티팩트를 남긴다. Anthropic의 장기 실행 에이전트 사례는 첫 세션에서 환경을 초기화하고, 후속 세션은 작은 단위로 진행하며 다음 세션을 위한 명료한 아티팩트를 남기는 방식을 쓴다. 글도 compaction만으로는 긴 프로젝트를 잘 완성하기 어렵다고 지적한다. [Effective harnesses for long-running agents](https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents)
- `sub-agent`는 검색 결과·로그처럼 본 대화에 원문이 들어오면 부풀어 오를 부수 작업에 쓰고 요약만 돌려받는다. 각 에이전트는 별도 컨텍스트를 사용한다. [Claude Code subagents](https://code.claude.com/docs/en/sub-agents)
- 최신 prompting guidance는 컨텍스트를 비운 뒤 상태를 로컬 파일에서 다시 찾을 수 있다면, compaction 대신 새 컨텍스트에서 시작하는 것도 고려하라고 한다. 긴 작업의 첫 창에서 반복 가능한 프레임워크를 세우고, 후속 창은 할 일 목록을 따라가는 방식도 제안한다. 이는 모든 경우에 세션 초기화가 더 낫다는 뜻은 아니다. [Prompting best practices](https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/claude-prompting-best-practices)
- `CLAUDE.md` 지침을 보안 경계로 오해하면 안 된다. 공식 문서는 지침 파일이 행동을 이끌 뿐 클라이언트 설정처럼 강제되는 차단 장치는 아니라고 구분한다. [Claude Code memory](https://code.claude.com/docs/en/memory)

### OpenAI

- Codex의 `AGENTS.md`는 프로젝트 지침을 세션에 공급한다. Codex 모델 가이드는 상위 폴더부터 현재 작업 디렉터리까지 지침 파일을 읽어 대화에 포함한다고 설명한다. 큰 지침을 여러 단계로 적용하는 저장소라면 실제 실행 위치에서 어떤 파일이 적용되는지 확인해야 한다. [OpenAI model guidance: AGENTS.md and compaction](https://developers.openai.com/api/docs/guides/latest-model)
- API의 `/responses/compact`는 입력 이력을 압축한 뒤 후속 요청에 compaction 항목을 포함해 이어가는 기능이다. 이는 대화를 정리하는 기능이지 외부의 실험 원자료를 대체하는 버전 관리·기록 시스템은 아니다. [OpenAI Responses compaction](https://developers.openai.com/api/docs/guides/compaction)
- OpenAI의 Codex 엔지니어링 글은 긴 단일 지침 파일을 실제로 시도한 뒤 한계를 보고했다. 짧은 `AGENTS.md`를 목차처럼 유지하고, 구조화한 문서를 저장소의 지식 원본으로 삼으며, 문서 상태와 소유권을 기계적으로 확인하는 접근을 설명한다. [Harness engineering: leveraging Codex in an agent-first world](https://openai.com/index/harness-engineering/)

## 개발자들이 쓰는 습관: 사례와 근거 수준

아래는 개발자 커뮤니티 글의 공개 사례다. 설문이나 통제된 비교 실험이 아니므로 빈도·효과를 일반화하지 않는다.

- **작업이 논리적으로 끝났을 때 새 세션을 시작한다.** 새 주제로 전환하거나 구현에서 검토로 넘어갈 때 `/clear` 또는 새 대화를 쓰고, 필요한 요약을 다시 읽힌다는 사례가 반복된다. 이 습관은 오래된 대화를 유지할 필요가 없는 작업에서 특히 단순하다. [ClaudeCode 사용자 사례, 2026-08](https://www.reddit.com/r/ClaudeCode/comments/1vf4kpa/what_do_you_do_when_you_have_high_context/), [Claude Code compaction 전략 사례](https://www.reddit.com/r/ClaudeCode/comments/1trpxbb/what_is_your_compacting_strategy/)
- **수동 `/compact` 전 요약 지시를 구체화한다.** 목표, 바뀐 파일, 결정과 이유, 실패한 시도, 다음 세 가지 행동, 반복하지 말아야 할 시도를 남기도록 요청한다는 개발자 사례가 있다. 일부 사용자는 특정 컨텍스트 비율을 기준으로 삼지만, 50%, 60%, 70% 같은 수치는 경험적 개인 규칙이지 공식 최적점이나 보편 기준이 아니다. [사용자 사례](https://www.reddit.com/r/ClaudeCode/comments/1vf4kpa/what_do_you_do_when_you_have_high_context/), [compaction 전략 토론](https://www.reddit.com/r/ClaudeCode/comments/1trpxbb/what_is_your_compacting_strategy/)
- **조사나 로그 분석을 서브에이전트에 맡기고 요약만 가져온다.** 이는 공식 sub-agent 설명과도 맞닿는다. 검색어, 조사 범위, 근거 링크, 불확실성을 결과 형식에 넣으면 메인 작업과 조사 내용을 연결하기 쉽다. [Claude Code subagents](https://code.claude.com/docs/en/sub-agents)
- **컨텍스트 사용량을 관찰하고 대형 파일 전체를 넣지 않는다.** 커뮤니티 글에는 `/context` 또는 상태 표시줄을 확인하고, 전체 파일 대신 검색 결과나 필요한 줄 범위를 요청한다는 사례가 보인다. 이는 유용한 절약 습관이지만, 특정 임계값을 넘으면 품질이 반드시 떨어진다는 독립 검증은 여기서 확인하지 못했다. [공개 사례](https://www.reddit.com/r/ClaudeAI/comments/1wdwgor/claude_code_microcompact/)
- **수동 압축이 자동 압축보다 항상 경제적이라는 보장은 없다.** 2026년 9월 공개 토론에는 자동 압축의 타이밍을 피하려 수동 압축·새 세션을 택한다는 경험과, 오래된 세션을 압축하며 사용량이 크게 증가했다는 보고가 함께 있다. 캐시·세션 나이·도구 구현에 따라 비용이 달라질 수 있으므로, 토큰 절약이 목적이면 실제 사용량 지표를 자기 환경에서 기록해야 한다. [비용 사용 경험 토론](https://www.reddit.com/r/ClaudeCode/comments/1w9wf7z/claude_just_compacted_my_session_and_took_me_from/)

## 도구와 외부화 방법

| 선택지 | 형태와 목적 | 주의점 |
|---|---|---|
| `CLAUDE.md`, `AGENTS.md`, 작업별 Markdown | 별도 의존성 없이 지침, 계획, 현재 상태, 근거 링크, handoff를 버전 관리한다. | 지침과 작업 상태를 한 파일에 몰아넣지 말고, 매번 전량 주입되는 파일은 짧게 유지한다. 상태 파일에는 갱신 시각과 근거 위치를 둔다. |
| Claude Code auto memory | Claude Code가 세션에서 얻은 교정·프로젝트 맥락을 저장하고 다음 세션에 일부 불러오는 내장 기능. | 자동 기록은 사람이 승인한 사실과 동일하지 않다. 저장된 내용과 적용 범위를 `/memory` 등으로 점검한다. 상세 동작은 버전에 따라 달라질 수 있다. [공식 문서](https://code.claude.com/docs/en/memory) |
| Anthropic Memory tool | API 에이전트가 파일 기반 외부 메모리를 읽고 쓰게 하는 도구. 프로젝트 상태·지식 베이스를 대화 컨텍스트 밖에 둔다. | 애플리케이션이 저장소 접근, 권한, 선택적 검색, 출처 관리를 설계해야 한다. 일반 Claude 대화의 자동 기능과 혼동하지 않는다. [Anthropic memory tool 설명](https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents) |
| `claude-mem` | 공개 플러그인 저장소는 Claude Code의 도구 사용 관찰을 저장하고 의미 요약을 다음 세션에 제공하는 지속 메모리를 표방한다. [저장소와 문서](https://github.com/thedotmack/claude-mem) | 프로젝트 설명은 자체 주장이다. 이 조사가 품질·보안·정확도나 현재 유지 상태를 독립 검증한 것은 아니다. 저장되는 세션 내용, 로컬 DB, 요약 오류, 민감 자료 취급을 검토하고 작은 비민감 작업에서 평가해야 한다. |
| 로컬 transcript 검색 / `RAG over transcript` | 세션 원문을 JSONL·Markdown 등으로 보관하고 키워드/전문 검색 또는 임베딩 검색으로 필요한 과거 조각만 되살린다. | 검색 결과는 사실의 정본이 아니다. 결과에 세션·시각·메시지 위치를 붙이고 현재 파일이나 실험 로그와 대조한다. 대화 원문에 비밀·개인 정보가 포함되면 보존 범위와 삭제 정책이 필요하다. |
| `PreCompact` hook 및 자동 handoff 스크립트 | 압축 직전 요약이나 체크포인트 작성을 자동으로 유도하거나 실행한다. | hook은 실행 타이밍과 실패 처리에 따라 오히려 손실을 만들 수 있다. 자동 파일 덮어쓰기보다 임시 파일 생성, diff 확인, 완료 시각 기록이 안전하다. Claude Code hooks는 버전별 공식 기능 설명을 확인한다. [Hooks 문서](https://code.claude.com/docs/en/hooks) |

이 중 본 실험 루프에 지금 추가할 도구는 없다. 이미 저장소 상태 파일이 있다면 먼저 그 형식을 강화하고, 원문 검색은 요약에서 누락된 특정 실험 근거를 되찾을 필요가 반복해서 확인될 때 작은 범위로 도입하는 편이 낫다.

## 피할 실패와 검증 방법

1. **거대한 메모리 파일을 계속 키우기.** 관련 없는 규칙·과거 상태가 매 작업의 컨텍스트를 차지하고, 무엇이 유효한지 모호해진다. 지속 지침은 짧은 색인으로, 세부 근거와 진행 상태는 별도 파일로 보낸다.
2. **요약을 원자료처럼 취급하기.** 요약에서 숫자·조건·예외가 탈락할 수 있다. 실험 결과, 실행 명령, 데이터 경로, 커밋 ID는 원래 로그나 저장소 위치와 함께 남긴다.
3. **현재 상태와 계획을 섞기.** `완료`, `시도했으나 실패`, `예정`, `검증되지 않음`을 분리한다. 실패한 시도는 원인과 재시도 조건을 적어 반복 비용을 줄인다.
4. **컨텍스트를 끝까지 채운 뒤 압축하기.** 중간에 압축되면 실험 실행이나 파일 변경의 안전한 경계가 아닐 수 있다. 재현 가능한 정지점에서 저장·커밋·로그 기록을 먼저 하고, 다음 행동을 적은 뒤 압축하거나 세션을 닫는다.
5. **서브에이전트의 결론만 받고 근거를 버리기.** 요약에 핵심 링크, 파일 경로, 표본 수·조건, 미해결 사항을 요구하고 본 세션에서 중요한 수치만 직접 확인한다.
6. **자동 메모리와 지침을 사실로 믿기.** 도구가 저장한 기억은 오래되거나 틀릴 수 있다. 작업 시작 때 현재 브랜치·상태 파일·실험 로그를 확인하고, 지침 파일의 주입 여부를 해당 도구의 `/context`나 로그로 확인한다.
7. **모든 변경마다 압축하기.** 압축 자체에도 읽기·요약 비용이 들며 새 요약의 품질을 매번 검증해야 한다. 압축은 창이 크다는 이유만이 아니라, 남은 대화의 재사용 가치와 현재 작업의 전환 가능성을 보고 결정한다.

Anthropic도 긴 작업에서 compaction이 만능은 아니며, 세션 간 진행 아티팩트가 필요하다고 명시한다. OpenAI는 긴 `AGENTS.md`가 작업 맥락을 밀어내고 낡은 규칙의 저장소가 될 수 있다고 보고한다. 서로 다른 제품 문서가 같은 실패 지점을 가리킨다. 원문·코드·실험 로그가 정본이고, 요약과 검색 메모는 그 정본을 찾는 색인으로 다뤄야 한다.

## 우리 상황: 며칠짜리 RL 실험 루프 적용안

### 기본 원칙

자동 압축을 끄거나 특정 토큰 비율을 보편 임계값으로 정하지 않는다. **실험의 재현 가능한 단위와 안전한 정지점에서 사람이 세션을 나눈다.** 세션 컨텍스트가 큰데도 현재 실험 단계가 미완료라 이어가야 할 때만 수동 압축을 보조 수단으로 쓴다.

### 세션 시작

1. `AGENTS.md`, 현재 실험 handoff, 실행 계획에서 이번 배치의 범위만 읽는다.
2. Git 브랜치·변경 파일·체크포인트 ID·설정 파일 해시·최근 결과 로그를 실제 파일에서 확인한다. 요약의 상태를 사실로 가정하지 않는다.
3. 목표, 고정 조건, 바꿀 변수, 성공·중단 기준을 이번 세션 프롬프트에 명시한다.
4. 과거 세션 검색은 구체적인 누락 근거를 찾을 때만 사용한다. 찾은 내용에는 원 로그 위치를 붙인다.

### 세션 중

- 원자료 로그와 체크포인트는 에이전트 대화에 붙여 넣기보다 파일로 보존하고, 필요한 구간·열·요약만 읽힌다.
- 독립적인 논문·코드 탐색, 로그 묶음의 패턴 찾기는 읽기 전용 조사로 분리하고, 결과에 URL 또는 경로, 확인한 조건, 미확인 항목을 요구한다.
- 정책, reward, 관측, 지형, seed 등 비교를 깨뜨릴 수 있는 조건은 handoff의 고정 조건 표에 기록한다. 실험 결과를 요약할 때 성공률만 단독 표기하지 말고 충돌·속도·낙상·완주 기준과 분모를 함께 적는다.
- 큰 컨텍스트를 만들기 전에 먼저 검색 범위를 좁힌다. 파일 전체 출력이나 반복된 로그를 남겨두지 않는다.

### 세션 종료 또는 수동 압축 직전

실험 단계가 끝나거나 다음 단계 전에 검토가 필요한 시점에 handoff를 갱신한다. 최소 필드는 다음과 같다.

```text
목표와 현재 단계
완료한 실행: 명령, 설정/코드 해시, seed와 환경
결과: 지표, 분모, 원자료 로그와 체크포인트 경로
결정과 근거: 고정 조건 및 변경 조건
실패한 시도: 원인, 다시 시도할 조건
미해결 질문과 위험
다음에 할 한 가지 행동
세션 및 Git 상태: 시각, 브랜치, 커밋 또는 미커밋 변경
```

파일을 저장한 뒤 새 세션에서 handoff만 읽고 현재 저장소·로그와 대조한다. 불일치는 진행 전에 바로잡는다. 압축을 택했다면 추가 지시로 **근거 위치와 실패한 시도를 보존하고, 이미 기록된 원문 로그는 요약에서 제외**하도록 한다. 그 후 압축 요약과 handoff를 대조한다. 둘이 다르면 원자료가 우선이다.

### 단계별 세션 분할 기준

- **환경·씬 준비 → 학습 실행 → 평가·분석**은 별도 세션 경계로 삼는다. 각 단계의 입력·출력이 파일과 로그로 명확하기 때문이다.
- 하나의 학습 실행이 장시간 걸리면 실행을 대화 안에서 계속 관찰하는 대신, 프로세스·로그·체크포인트를 저장하고 세션을 종료할 수 있게 운용한다. 다음 세션은 같은 실행을 이어받기 전에 실제 프로세스와 최신 로그를 확인한다.
- 설정이나 보상 함수를 바꾸는 결정은 평가 세션에서 분리해 기록한다. 변경 전후 비교가 필요하면 같은 기준선과 측정 조건을 보존한다.
- 세션을 나누는 기준은 임의의 컨텍스트 사용률이 아니라, 결과를 재현할 수 있는 경계와 다음 작업으로 넘어가는 순간이다. 컨텍스트 UI의 사용량은 보조 경고로만 관찰한다.

**추측·제안.** 이 절차는 도구의 기본값만 바꾸면 해결된다는 뜻이 아니라, 이미 시작한 저장소 상태 파일 방식을 실험 근거와 정지점까지 확장하는 제안이다. 2~3회의 실제 RL 배치에서 handoff 누락, 재탐색 시간, 잘못 이어간 설정 수를 기록해 불편한 필드를 줄이고 누락되는 필드를 보강한다. 효과 크기는 측정 전까지 미확인이다.

## 판 이력

| 판 | 언제 | 무엇이 바뀌었나 | 근거 |
|---|---|---|---|
| v1.0 | 2026-09-23 | 최초 조사본. 공식 권고, 개발자 사례, RL 루프 적용안을 정리 | 아래 출처 |

## 출처

### 공식 문서 및 엔지니어링 글

- Anthropic, [Effective context engineering for AI agents](https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents), 2025-09-29 게시.
- Anthropic, [Effective harnesses for long-running agents](https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents).
- Anthropic Claude Code, [Memory](https://code.claude.com/docs/en/memory).
- Anthropic Claude Code, [Subagents](https://code.claude.com/docs/en/sub-agents).
- Anthropic, [Prompting best practices](https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/claude-prompting-best-practices).
- Anthropic Claude Code, [Hooks](https://code.claude.com/docs/en/hooks).
- OpenAI, [Harness engineering: leveraging Codex in an agent-first world](https://openai.com/index/harness-engineering/).
- OpenAI Developers, [Model guidance: AGENTS.md and compaction](https://developers.openai.com/api/docs/guides/latest-model).
- OpenAI Developers, [Compaction](https://developers.openai.com/api/docs/guides/compaction).
- GitHub, [thedotmack/claude-mem](https://github.com/thedotmack/claude-mem), 프로젝트 자체 문서. 기능 주장은 독립 검증 아님.

### 개발자 공개 사례

- Reddit r/ClaudeCode, [What do you do when you have high Context?](https://www.reddit.com/r/ClaudeCode/comments/1vf4kpa/what_do_you_do_when_you_have_high_context/), 2026-08.
- Reddit r/ClaudeCode, [What is your Claude Code compacting strategy?](https://www.reddit.com/r/ClaudeCode/comments/1trpxbb/what_is_your_compacting_strategy/), 2026-05.
- Reddit r/ClaudeAI, [Claude Code micro-compact?](https://www.reddit.com/r/ClaudeAI/comments/1wdwgor/claude_code_microcompact/), 2026-09.
- Reddit r/ClaudeCode, [Claude just compacted my session and took me from 15% usage to 90%](https://www.reddit.com/r/ClaudeCode/comments/1w9wf7z/claude_just_compacted_my_session_and_took_me_from/), 2026-09.

