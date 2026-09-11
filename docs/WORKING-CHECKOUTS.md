> 분류: 운영
> 작성: 오흥재 · 2026-09-11 18:10
> 근거: 실측 (`git worktree list` · 각 자리의 branch·HEAD·upstream·생성 시각을 직접 읽음)
> 요지: 작업용 clone 을 `C:/work/` 에 따로 두던 것을 그만둔다. 본 clone 하나에서 worktree 로 간다
> 상태: 확정

# 작업용 체크아웃 규약

## 왜 이 문서가 있나

2026-09-11 에 팀장이 물었다. **「원본 파일 저장 경로가 왜 `C:/work/foothold-lab-easy5` 야? 누가 정한 거야?」**

**답을 찾지 못했다.** 폴더는 2026-09-10 22:41 에 생겼고, 저장소 문서에도 세션 기록에도
누가 왜 만들었는지가 없다. 규약이 **사람 머릿속에만 있었다.**

이어서 팀장이 정했다. **「따로 클론해서 관리해야 하는 거면 의미가 없다. 원래 git 이랑
연결돼 있는 경로에서 하는 게 맞다.」** 그 결정을 여기 적는다.

세션이 끝나면 사라지는 것은 규약이 아니다.

## 지금 이 기계에 있는 것 (2026-09-11 18:10 실측)

| 자리 | 무엇인가 | branch | HEAD |
|---|---|---|---|
| `인공지능사관학교/foothold-lab` | **본 clone.** 08-09 생성. 모든 worktree 가 여기 달려 있다 | `main` | `7e979e0` |
| `인공지능사관학교/_lab-main` | 위의 **worktree** 다. 별도 clone 이 아니다 | (detached) | `4686411` |
| `C:/work/foothold-lab-easy5` | 별도 clone. 09-10 22:41 생성 | `main` | `ef32208` |
| `C:/work/foothold-lab-sweep` | 별도 clone. 09-10 10:34 생성 | `feature/rough6-and-wall-20260910` | `ce0c787` |

그 밖에 scratchpad 와 orca workspace 에 worktree 17개가 더 달려 있다.
`git worktree list` 로 전부 보인다.

**앞선 판(2026-09-11 13:20)의 표는 틀렸다.** `_lab-main` 을 「공유 체크아웃」이라고
적었는데, 실제로는 `foothold-lab` 에 달린 worktree 이고 detached HEAD 다. 정정한다.

## 규약

**본 clone 은 `인공지능사관학교/foothold-lab` 하나다.** 여기서 일한다.

**일감마다 clone 을 새로 만들지 않는다.** worktree 를 쓴다.

```
git -C <본 clone> worktree add tmp/wt-<일감> -b <branch>
```

worktree 는 `.git` 을 공유하므로 디스크를 다시 안 먹고 원격도 한 벌만 본다.

`C:/work` 는 이 기계(AI-WS01)의 자리였다. 경로를 문서나 코드에 박지 않는다.

## 별도 clone 이 만든 문제 (이것 때문에 그만둔다)

2026-09-11 실측이다.

```
인공지능사관학교/foothold-lab   main  7e979e0   upstream 대비 0 / 0
C:/work/foothold-lab-easy5      main  ef32208   upstream 대비 0 / 0
원격 origin/main                      ef32208
```

**둘 다 「원격과 같다」고 말하는데 서로 다른 자리에 있다.** 앞의 것이 fetch 를
안 해서 자기 원격 추적 ref 가 낡았기 때문이다. `git status` 만 보면 둘 다
깨끗해 보이고, 어느 쪽이 최신인지 알 수 없다.

세어 보면 답이 나온다. `7e979e0..ef32208` 이 1 커밋이고 반대는 0 이다.
곧 **본 clone 이 한 커밋 뒤처져 있었다.**

worktree 였으면 이 상황 자체가 안 생긴다. `.git` 이 하나라 원격 추적 ref 도 하나다.

## 정리 절차

1. `easy5` 의 작업을 commit 하고 `origin/main` 에 push 한다.
2. 본 clone 에서 `git fetch` 하고 `git pull` 한다. fast-forward 다.
   본 clone 의 미커밋은 untracked 둘(`.claude/` · `deliverables/plan/proposal.hwp`)
   뿐이라 잃을 것이 없다.
3. 받은 것이 맞는지 확인한 뒤 `easy5` 와 `sweep` 를 지운다.
   `sweep` 의 branch 는 원격에 이미 올라가 있다(`0 / 0`).

**2번을 확인하기 전에 3번을 하지 않는다.** `easy5` 에만 있는 결과 폴더가
62 MB 있고, 그것이 push 에 실려 간 것을 눈으로 본 다음에 지운다.

## 결과 파일

**실행 산출물은 작업 자리 안에 쌓는다.**

```
sim/eval/results/<날짜>-<일감>/
```

옮기지 않는다. 실행 기록(`run_manifest.json`)이 그 자리를 가리키고 있다.

무엇을 넣고 무엇을 빼는지는 `.gitignore` 에 이유와 함께 적혀 있다.
받는 사람이 전부 받게 되므로, **다시 뽑을 수 있는 것은 안 넣는다.**

## 지켜야 하는 것

- **공유 체크아웃에서 직접 작업하지 않는다.** 본 clone 의 `main` 에서 바로
  고치지 말고 worktree 에 branch 를 따서 PR 로 올린다.
  - 남의 미커밋 변경 위에 덮어쓸 수 있다
  - 여러 세션이 같은 자리에서 브랜치를 옮기면 서로를 밟는다
- **파일을 쓰기 전에 `git status --short` 로 남의 미커밋 변경을 확인한다.**
- **`git checkout -- .` 이나 `git clean -fd` 를 「청소」 목적으로 쓰지 않는다.**
  지우는 명령은 범위를 파일 단위로 적는다. `.` 이나 `-A` 는 「내가 무엇을
  지우는지 세어 보지 않았다」는 뜻이다.
  2026-08-27 에 이것으로 커밋 안 한 수정 9개를 잃었다. 되살릴 방법은 없었다.

## 남은 정리 대상

2026-09-11 기준.

```
scratchpad/wt-*        11개   PR 머지 완료 · 지워도 된다
C:/work/foothold-lab-easy5    위 「정리 절차」 3번에서
C:/work/foothold-lab-sweep    위 「정리 절차」 3번에서
```
