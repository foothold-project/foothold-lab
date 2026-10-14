> 분류: A/평가 · #550 댓글 초안
> 작성: Codex Worker · 2026-10-14
> 근거: codexE/REPORT-17s.md · evidence_17s/run_20261014_230924_117964/summary.json
> 요지: 17s 지적 7항목 고침과 CPU 정상·반례·코드 변이 결과
> 상태: 게시 전 초안 · lead 게시 담당

# 1043 평가 후보 17s 고침 요약

- `codexE/cand_17s_base/`에 17r 후보 154개를 보존하고 SHA256 전수 대조 0불일치. 17s 후보 159개 전체 해시와 17r 대비 12개 변경은 `CAND-17S-SHA256SUMS.txt`, `CAND-17S-CHANGES.json`에 기록했다.
- 원본 q의 `loaded_iter` 누락만 허용하고 checkpoint·cmdr 검사는 유지했다. 승인 ID·실제 attempt·log를 B에 묶어 `write_root` 원자 장부에서 단회 사용을 강제한다. 실행 중 `max_wall_s`·STOP은 소유 자식 트리에 적용하고 종료 확인까지 lease를 보유한다. retry 0을 허용한다.
- 진단 비교는 의미·JSON 바이트·traj 바이트 세 값을 분리하고 byte-only 원인 코드를 기록한다. 반복·실패 run 보고 항목을 기본 run과 맞췄다. 공통 경로는 정확한 allowlist 예외를 지원한다.
- 최종 CPU 묶음 `evidence_17s/run_20261014_230924_117964/summary.json`은 10/10 종료 0. 17r 입력 변조 12종과 별도로 17s 코드 검사 비활성 변이 6종 모두 정상 선행·지정 실패 위치 일치로 CAUGHT. 실제 원본 meta SHA256 `4c4bed8364cf6cc1c873585dc895ec1fee99ab1bc699cf71bed9c19a834bb093`을 읽기 전용으로 검증했다.
- GPU·Isaac·실제 slot/guard/isolate/Kit·공통 lease 전체 참가 여부는 미확인. GPU 배정·시간창·위험 상한·종료 정책·반복 예산·재기동 범위·비교 통과선·공통 경로는 UNDECIDED. 승인 JSON 발급과 운영 기동은 보류한다.

상세: `codexE/REPORT-17s.md`. 이 파일은 댓글 초안이며 게시하지 않았다.
