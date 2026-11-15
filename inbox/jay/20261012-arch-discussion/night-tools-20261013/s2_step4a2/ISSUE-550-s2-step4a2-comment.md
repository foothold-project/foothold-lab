# #550 댓글 초안 · S2 A2 17w CPU 고침
> 분류: A/정책학습 · 이슈 댓글 초안
> 작성: Codex Worker · 2026-10-15
> 근거: `REPORT-s2-step4a2.md` · `r20261015_17w_a2_final3/summary.json`
> 요지: 정보 수집 전용 A2 경로의 CPU 고침·완결 복사·독립 import 확인 결과
> 상태: lead 게시 대기 · GPU/Isaac 미실행 · 승인값 UNDECIDED

ASTRA 17w A2 고침을 `codexE/s2_step4a2_frozen/`에 39파일로 고정했습니다. 필수 실행 의존 23파일 해시를 계약에 묶고, 고정본을 깨끗한 임시 폴더로 복사해 `python -I -B`로 Python 모듈 22개를 실제 import했습니다. 통합 실행 `r20261015_17w_a2_final3`은 CPU 정상 84 PASS, 기존 A 코드 변이 5/5, 새 A2 코드 변이 7/7 지정 첫 FAIL로 CAUGHT입니다. NaN 높이, fixed 1, root+100 m, step/stones 표식 소거, 정적 평지 reset 정답, cuda:1, UUID 교체, disk 1 byte, raw 선기록 실패를 시험했습니다.

실제 Isaac 장면·mesh 선택·고정 자세·Kit 장치·VRAM·USD 변환은 미확인입니다. 첫 GPU 일은 **단회 정보 수집 전용**이며 결과는 강제 `HOLD_INFORMATION_ONLY`, optimizer 0, 자동 재시도와 후속 학습 없음입니다. 독립 watchdog이 없어 참석자가 터미널을 유지하는 관찰만 지원합니다. lead가 승인값과 실제 자원 한도를 동결한 뒤 `s2_stage0_prelaunch.py` GO를 되읽어야 기동 여부를 판단할 수 있습니다. 전체 해시·시험 위치·남은 accessor는 `codexE/REPORT-s2-step4a2.md`에 적었습니다.
