# A/평가

일반화 벤치마크와 지표 측정. 담당 오현민.

> 폴더는 이슈의 «작업 영역» 라벨과 1:1 이다.
> 이 자리에 넣을 것이 생기면 브랜치를 파고 PR 로 올린다. inbox 를 거치지 않는다.

---

## 지금 상태 (2026-09-02)

**하네스 확장 `#125` 작업 중입니다.** 지금 여기 있는 것은 복원한 Candidate 스냅샷뿐이고,
활성본은 아직 없습니다.

| 무엇 | 어디 |
|---|---|
| 원본 추적 · 무엇이 복원물인가 | `PROVENANCE.md` |
| 문서에서 복원한 Candidate 스냅샷 | `provenance/candidate-20260822/` |
| 스냅샷 재추출 · 대조 도구 | `provenance/extract_candidate.py` |
| 활성 실행본 | 아직 없음. `#125` 커밋 1 부터 이 자리에 |

## 먼저 읽을 것

**`provenance/candidate-20260822/` 를 고치지 마십시오.** 문서에서 바이트 그대로 복원한
것이고, 원래 RunPod 실행본과 대조하지 못했습니다. 검증된 런타임 정본이 아닙니다.
우리 변경은 이 폴더(`sim/eval/`) 바로 아래 활성본에 둡니다.

이유와 provenance 를 닫는 조건은 `PROVENANCE.md` 에 있습니다.

## 이 워크스테이션에서 되는 것

Isaac Lab 도 GPU 도 없이 표준 라이브러리만으로 다음이 됩니다.

```bash
python sim/eval/provenance/extract_candidate.py --check
```

지형 생성 · 정책 로딩 · 실제 CSV 산출은 RunPod GPU 팟에서만 됩니다.
