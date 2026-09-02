# 평가 하네스 원본 추적

> 분류: 운영
> 작성: 오흥재 · 2026-09-02 15:20
> 근거: 실측
> 요지: 이 폴더의 하네스가 어디서 왔고, 무엇이 복원물이고 무엇이 우리 변경인지 가른다.
> 상태: 확정
> 판: v1.0
> 이슈: #125

## 1. 한 줄

**두 프로젝트 문서에서 바이트 단위로 동일하게 복원한 Candidate 스냅샷이다.
원래 RunPod 실행 파일은 회수하거나 직접 대조하지 못했으므로,
provenance 가 닫히기 전까지 검증된 런타임 정본으로 취급하지 않는다.**

## 2. 실행본을 찾지 못했다 `확인됨`

`benchmark-setup-lim.md` 가 가리키는 실행 경로는 RunPod 컨테이너 안입니다.

```
/workspace/isaaclab/scripts/reinforcement_learning/rsl_rl/eval_generalization.py
```

2026-09-02 에 다음을 전수로 뒤졌고 실행본은 없었습니다.

| 뒤진 자리 | 결과 |
|---|---|
| Windows 로컬 `Desktop/jay/인공지능사관학교/` 하위 | 하네스 파일명 0건 |
| WSL Ubuntu-24.04 `find / -xdev` | `/workspace` 부재 · `*isaaclab*` 0건 |
| Docker Desktop | 데몬 정지. 조회 불가 |
| `foothold-go2` 저장소 | `.py` 파일 0건 |
| `foothold-lab` git 전 이력 | 하네스 파일명 0건. 삭제 이력도 없음 |

`docs/research/benchmark-repro-protocol.md` §1-2 · §2-0단계가 같은 상태를 8/22 에 이미
적어 두었습니다. 「벤치마크 스크립트 원본이 재현의 전제 · 실행자에게 원본과 커맨드라인 요청」.

## 3. 복원한 것 · 복원한 방법

| 출처 | sha256 (문서) |
|---|---|
| `inbox/lim/20260822-베이스라인 모델의 간단한 미경험 험지 성능 측정.md` | `ece95275a8510089…` |
| `docs/research/benchmark-setup-lim.md` | `05b4233495a18dc0…` |

두 문서가 품은 `cat > ... <<'PY'` 히어독을 풀었습니다.
히어독은 마지막 줄에도 개행을 붙이므로 그것까지 맞췄습니다.

| 파일 | 크기 | 행 | sha256 |
|---|---|---|---|
| `eval_generalization.py` | 19,991 B | 652 | `1e39567a96c63d4e8219f16c65f959661326e5ce331039e73f5a3de8e4acc541` |
| `generalization_env_cfg.py` | 4,740 B | 148 | `054f00cc3c4013d7dabcccf2a004b977e93c5c999e0117fad08306b434c1a521` |
| `record_generalization.py` | 6,598 B | 246 | `bf95be21e377cdac9987b01e8bbdf9a2227c93b086aefec894af9842707bbca2` |
| `record_all_generalization.sh` | 575 B | 24 | `f6cdd054b7fc33288ef467670c49f7726cb3e66d75cbe1ef59881345194fbd56` |

**두 문서에서 나온 넷이 모두 바이트 단위로 같습니다** `확인됨`.
승격이 코드를 변형하지 않았다는 뜻입니다.

다시 뽑아 대조하는 것은 표준 라이브러리만으로 됩니다.

```bash
python sim/eval/provenance/extract_candidate.py --check
cd sim/eval/provenance/candidate-20260822 && sha256sum -c SHA256SUMS
```

이 저장소는 `core.autocrlf=true` 라 기본값대로면 체크아웃 때 CRLF 가 되어 해시가 깨집니다.
그래서 `sim/eval/provenance/.gitattributes` 에 `* text eol=lf` 를 걸었습니다.
루트 `.gitattributes` 는 건드리지 않았습니다.

## 4. 실행본과의 정합 · 간접 증거뿐이다 `추측`

직접 대조가 불가능하므로 산술로 맞춰 봤습니다.

| 증거 | 코드블록에서 계산 | 기록된 실측 |
|---|---|---|
| `gap` 틈 폭 | `0.15 + 0.5 × (0.40 - 0.15) = 0.275 m` | 27.5 cm |
| 이상 거리 | `0.5 m/s × 6.0 s = 3.0 m` | `ideal_distance_m` 3.0 |
| 판정 축 | survival · progress · tracking · direction + overall | 5축 |
| env 수 | `len(TERRAIN_NAMES) = 10` · 1행 10열 | env 10 |
| 좌우 이탈 계산 위치 | 추출본 487행 | 문서 837행 근처 |

**판정: 500판을 낸 그 코드와 같거나 극히 가까운 판본이다 `추측`.**
확정하려면 임석헌의 팟 원본 또는 실행 커맨드라인이 필요합니다.

## 5. provenance 를 닫는 조건

셋 중 하나면 닫힙니다.

1. 팟 원본 파일을 받아 `provenance/runpod-<날짜>/` 에 두고 해시가 일치
2. 실행 커맨드라인과 실행 로그를 받아 인자 · 관측 차원 · 지형 매핑이 일치
3. 같은 체크포인트로 이 스냅샷을 돌려 `generalization_raw.csv` v2 가 재현

닫히기 전까지 이 하네스로 낸 수치에는 **「Candidate 하네스 기준」**을 함께 적습니다.

## 6. 복원과 우리 변경의 경계

| 커밋 | 무엇 | 성격 |
|---|---|---|
| 0 | Candidate 스냅샷 · 추출기 · 이 문서 | **복원. 기능 변경 0** |
| 1 이후 | `sim/eval/` 활성본 | **우리 변경** |

활성본은 커밋 0 의 스냅샷에서 갈라져 나옵니다.
`provenance/candidate-20260822/` 는 그 뒤로 **고치지 않습니다.**

`record_generalization.py` 와 `record_all_generalization.sh` 는 **보존만** 합니다.
#125 활성 범위가 아니고, 정식 실행 경로로 승격하지도 않습니다.

## 7. 활성본이 스냅샷에서 갈라진 자리

커밋 1 부터 여기에 한 줄씩 쌓습니다.

| 커밋 | #125 항목 | 무엇이 달라졌나 |
|---|---|---|
| (아직 없음) | | |

## 판 이력

| 판 | 언제 | 무엇이 바뀌었나 | 근거 |
|---|---|---|---|
| **v1.0** | 2026-09-02 | 처음 씀. Candidate 스냅샷 복원 | #125 |
