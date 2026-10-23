> 분류: A/정책학습 · 학습 · 보상 · 관측 · 파인튜닝
> 작성: 오흥재 (lead_tmp 고정본 취합) · 2026-10-23
> 근거: sol82331727 · sonnet-code7cab5223 계보 · ASTRA-23e · lead_tmp CPU39시험
> 요지: 로컬에만 있던 START 구현을 새 코드 브랜치의 고정 사본으로 보존하며 기존 실행 사본은 수정하지 않는다.
> 상태: 코드 취합 · CPU 확인 · GPU/Kit 미실행

# EX-28 B·EX-29 START-TD 구현 사본

이 브랜치 `feature/start-topdown-b-jay`는 문서 브랜치의617e865f에서 갈라졌다. `foothold_s2/`는 sol의 완료 커밋8233172777e592877861c6e78918fc1f3bcfc0fe에서 `git archive`로 읽었다. sol/sonnet의 다른 미공개 변경 이력을 문서 브랜치에 병합하지 않았다. 코드의 원래 계보와 완료 커밋은 아래에 남긴다.

| 구성 | 고정 출처 |
|---|---|
| EX-23 이전 코드 기준 | sonnet-code7cab5223e0990533d51d46b4d498693213b99f73 |
| B 새 처치 | be26f565 |
| TopDown 새 처치 | 2b6f6d02 |
| 저장·재개·시작 지지·카메라 수정 | 7cf1d73f · 2455c8d1 · f5bfc15c |
| 초기 방향·curriculum RNG·초기 snapshot | 8233172777e592877861c6e78918fc1f3bcfc0fe |
| 평가 촬영·첫/reset 지도 마스크·고정 명령·물리 조건 | luna5651b5f64a79fba793c18dc895a67df32e1f9c42 |

사용할 학습 진입점은 `foothold_s2/scripts/train_23f_b.py`와`train_23f_topdown.py`다. 기존 실행기와 옛 배포 자료는 구성 요소의 원본을 보존하기 위해 함께 있으며, 이번 판의 기동 지시가 아니다. 프로그램 이름의23f는 코드 작업 식별자이고 실험 번호는 EX-28·29다.

실험 설정과 판단 기준은 문서 브랜치의 [계획](https://github.com/foothold-project/foothold-lab/blob/feature/verify-v2-mvp-jay/inbox/jay/20261023-experiments/PLAN-B-START-TOPDOWN-1023.md)을 따른다. SHA 목록은 파일 바이트의 출처 확인이며 CPU 또는 Kit 통과를 대신하지 않는다.

`확인됨`: CUDA를 숨긴 isaac311 Python에서 관련 다섯 CPU시험 파일39개가7.34초에 통과했다. 논문 저자 코드와의 동등성, 실제 PhysX·센서·접촉·GPU 메모리·학습 수렴은 확인하지 않았다. Isaac Lab2.3.2·rsl_rl3.1.2와 설치된 Go2 자산은 이 소스 폴더 밖의 의존성이다. Linux에서는 설치 경로·버전·실제 첫 입력을 다시 확인하며 Windows 물리 episode와 동일 궤적이라고 부르지 않는다.

`확인됨`: 고정 소스 원본289개는 sol archive와 바이트가 모두 같다. luna 완료본에서 녹화기와 시험 두 파일만 더했다. 결합 사본에서 녹화 계약15개·seq_video9개를 직접 재실행해 **24 PASS,7.31초**를 확인했다. 초기 호출의 결과 출력이 일부만 수집되어 같은 범위를 로그 파일로 다시 실행한 값이다. 학습39개와 검증 범위가 다르며 서로 대체하지 않는다.

[SHA256 목록](SHA256SUMS-start-topdown-b.txt)은 이 사본의 `foothold_s2/` 291개 파일이다. 새 실행 전 이 목록과 실제 실행 사본을 대조한다. 새 recorder의 실제 Kit 출력과 영수증 생성은 아직 미확인이다.
