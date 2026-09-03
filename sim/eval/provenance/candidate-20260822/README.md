# Candidate 스냅샷 · 2026-08-22 판

**두 프로젝트 문서에서 바이트 단위로 동일하게 복원한 Candidate 스냅샷이다.
원래 RunPod 실행 파일은 회수하거나 직접 대조하지 못했으므로,
provenance 가 닫히기 전까지 검증된 런타임 정본으로 취급하지 않는다.**

## 이 폴더를 고치지 마십시오

여기 있는 넷은 **복원물**입니다. 우리 변경은 `sim/eval/` 활성 경로에 둡니다.
이 폴더를 고치면 「문서에서 나온 그대로」와 「우리가 바꾼 것」의 경계가 사라집니다.

고칠 일이 생기면 활성본을 고치고, 그 차이를 `../../PROVENANCE.md` 에 적으십시오.

## 무엇이 들어 있나

| 파일 | 크기 | 행수 | #125 활성 범위 |
|---|---|---|---|
| `eval_generalization.py` | 19,991 B | 652 | **포함** |
| `generalization_env_cfg.py` | 4,740 B | 148 | **포함** |
| `record_generalization.py` | 6,598 B | 246 | 보존만. 범위 밖 |
| `record_all_generalization.sh` | 575 B | 24 | 보존만. 범위 밖 |

해시는 `SHA256SUMS` 에 있습니다.

```bash
cd sim/eval/provenance/candidate-20260822 && sha256sum -c SHA256SUMS
```

## 어디서 나왔나

| 출처 | 승격 여부 |
|---|---|
| `inbox/lim/20260822-베이스라인 모델의 간단한 미경험 험지 성능 측정.md` | 임석헌 제출 원본 |
| `docs/research/benchmark-setup-lim.md` | 위의 승격본 |

두 문서가 품은 `cat > ... <<'PY'` 히어독을 그대로 푼 것입니다.
**두 벌에서 나온 넷이 모두 바이트 단위로 같습니다** `확인됨`.
승격 과정에서 코드가 변형되지 않았다는 뜻입니다.

다시 뽑아 대조하려면:

```bash
python sim/eval/provenance/extract_candidate.py --check
```

## 왜 「검증된 정본」이 아닌가

실행본 `/workspace/isaaclab/scripts/reinforcement_learning/rsl_rl/eval_generalization.py`
은 RunPod 컨테이너 안 경로이고, **회수하지 못했습니다** `확인됨`.

`benchmark-repro-protocol.md` §1-2 도 같은 것을 적어 두었습니다.
「벤치마크 스크립트 원본이 재현의 전제 · 실행자에게 원본과 커맨드라인 요청」.

원본이 나오면 `../runpod-<날짜>/` 로 나란히 두고 대조합니다.
그때 provenance 가 닫힙니다. 자세한 것은 `../../PROVENANCE.md`.
