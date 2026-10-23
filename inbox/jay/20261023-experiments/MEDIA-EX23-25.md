> 분류: A/평가 · 일반화 벤치마크 · 지표
> 작성: 오흥재 (lead_tmp 정리) · 2026-10-23
> 근거: luna-23b 기존 비교 영상 · lead_tmp 전체 해독 및 SHA256 대조 · 팀장 외부 열람 링크 요청
> 요지: EX-23·25 평지·rough 비교 영상의 외부 주소와 원본 해시를 연결한다.
> 상태: 연구 비교 자료 · 단일 시드·장면 · 정책 완성이나 우열 확정 아님

# EX-23·25 비교 영상

왼쪽 EX-23(정답 지도), 오른쪽 EX-25(지도 없음). 두 판 모두 model_1500, 약한 DR 고정, 추가 행동 지연 없음이다. 평지 근사와 rough에서 같은 명령 열을 연속 재생한다. 같은 지형 생성·명령이어도 실제 이동 경로와 회전 시작 자세가 달라지므로 독립적인 회전 능력 순위로 읽지 않는다.

영상은 Git 이력 대신 [연구 자료 Release](https://github.com/foothold-project/foothold-lab/releases/tag/research-ex23-25-20261023) 첨부 파일로 제공한다. 아래 다운로드 링크와 저장소의 종합 결과를 함께 본다.

| 장면·속도 | 외부 파일 | SHA256 |
|---|---|---|
| 평지 1배 | [MP4](https://github.com/foothold-project/foothold-lab/releases/download/research-ex23-25-20261023/ex23-ex25-flat-1500-1x.mp4) | `70fc8bcece9e59157a2c5d0989dd7e42ca8a10461e96a5480a24274201252638` |
| 평지 0.5배 | [MP4](https://github.com/foothold-project/foothold-lab/releases/download/research-ex23-25-20261023/ex23-ex25-flat-1500-0.5x.mp4) | `55f051a57e5f7fb92b6f383d02f8c920ed90307a60f9ad29028883dbc3f3f418` |
| rough 1배 | [MP4](https://github.com/foothold-project/foothold-lab/releases/download/research-ex23-25-20261023/ex23-ex25-rough-1500-1x.mp4) | `c61e2d616e75d0faf0ffff931b0b7718a50a5e5e5c8e956dfb49fd7c4f65a6b3` |
| rough 0.5배 | [MP4](https://github.com/foothold-project/foothold-lab/releases/download/research-ex23-25-20261023/ex23-ex25-rough-1500-0.5x.mp4) | `1b978afcf5c3c006d5beaf4695b2e2fe7ede80679414a451650c93252e4692f1` |

1배는12초·300프레임, 0.5배는24초·600프레임이다. 원본은 `C:/mai/wt/foothold-lab/luna-23b/inbox/jay/20261021-experiments/figs/ex23-25-luna-23b/` 아래에 같은 이름으로 있다. [종합 결과](../20261021-experiments/RESULT-EX23-25.md) · [전체 해독·해시 검증 기록](../20261021-experiments/figs/ex23-25-lead-review/comparison_video_check.json).
