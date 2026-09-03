# A/평가

일반화 벤치마크와 지표 측정. 담당 오현민.

> 폴더는 이슈의 «작업 영역» 라벨과 1:1 이다.
> 이 자리에 넣을 것이 생기면 브랜치를 파고 PR 로 올린다. inbox 를 거치지 않는다.

---

## 지금 상태 (2026-09-03)

**하네스 확장 `#125` 작업 중입니다.** 활성 하네스 본체가 생겼고,
2026-09-03 에 **처음으로 실제로 돌아 평지 기준선 100판**을 냈습니다 (`#99`).

| 무엇 | 어디 |
|---|---|
| 원본 추적 · 무엇이 복원물인가 | `PROVENANCE.md` |
| 문서에서 복원한 Candidate 스냅샷 | `provenance/candidate-20260822/` |
| 스냅샷 재추출 · 대조 도구 | `provenance/extract_candidate.py` |
| 판정 · 집계 순수 함수 | `metrics.py` |
| 지형 이름과 순서 | `terrains.py` |
| 활성 지형 설정 | `generalization_env_cfg.py` |
| 스냅샷과의 동치 · 구조 시험 | `tests/` |
| **활성 하네스 본체** | `eval_generalization.py` |
| 원시 CSV -> 요약 · Wilson 구간 | `report.py` |
| 실측 결과 | `results/` |

## 먼저 읽을 것

**`provenance/candidate-20260822/` 를 고치지 마십시오.** 문서에서 바이트 그대로 복원한
것이고, 원래 RunPod 실행본과 대조하지 못했습니다. 검증된 런타임 정본이 아닙니다.
우리 변경은 이 폴더(`sim/eval/`) 바로 아래 활성본에 둡니다.

이유와 provenance 를 닫는 조건은 `PROVENANCE.md` 에 있습니다.

## 이 워크스테이션에서 되는 것

Isaac Lab 도 GPU 도 없이 표준 라이브러리만으로 다음이 됩니다.

```bash
python sim/eval/provenance/extract_candidate.py --check
python -m unittest discover -s sim/eval/tests -v
```

`metrics.py` 는 `torch` 를 쓰지 않습니다. 스냅샷의 식을 그대로 옮겨 적은 것이고,
`tests/` 가 **스냅샷 원문을 다시 읽어** 같은 값이 나오는지 고정합니다.
고정되는 것은 식과 경계 조건이지 float32 반올림이 아닙니다. `PROVENANCE.md` §7 참고.

`report.py` 도 표준 라이브러리만 씁니다. 이미 나온 원시 CSV 에서 성공률과
Wilson 95% 신뢰구간을 뽑습니다.

```bash
python sim/eval/report.py sim/eval/results/20260903-flat-10m/generalization_raw.csv
```

## 실제로 돌리려면

지형 생성 · 정책 로딩 · CSV 산출에는 **Isaac Lab 과 GPU 가 필요합니다.**
RunPod 팟에서도 되고, Isaac Lab 이 깔린 워크스테이션에서도 됩니다.
2026-09-03 기준선은 워크스테이션에서 냈습니다. 명령줄 전문과 환경은
`results/20260903-flat-10m/README.md` 에 있습니다.

**돌리기 전에 `results/20260903-flat-10m/README.md` 의 「세계가 14 m 에서 끝난다」를
먼저 읽으십시오.** 안 읽고 시간을 길게 잡으면 로봇이 지형 밖으로 나가고,
그 판은 정책 성능이 아니라 낙하를 재게 됩니다.
