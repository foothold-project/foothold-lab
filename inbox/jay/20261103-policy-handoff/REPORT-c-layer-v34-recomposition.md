# EX-40 C층 m6000 v3.4 재합성 기록
> 분류: A/평가
> 작성: 오흥재 (scripter 반영) · 2026-11-03 20:16
> 근거: C층 정본 영수증 · review 원자료 · v3.4-D168 합성기 · 전 프레임 검사
> 요지: 촬영을 다시 하지 않고 GPU1 108편과 GPU0 27편을 v3.4로 재합성하고 목록을 갱신했다.
> 상태: 확인됨 · 이번 스냅샷 135편

## 실행 범위

- 원자료: `D:/mai-tmp/c_layer_m6000_phase1_v2/out`의 정본 108편, `D:/mai-tmp/c_layer_m6000_phase1_gpu0/out`의 정본 27편. 각 편의 `review.done`과 MP4 · JSON · NPZ 해시를 대조했다.
- 합성기: `foothold_s2/eval/video25/compose_25e_v2style10.py`, 판 `v3.4-D168`, SHA256 `7407f7b68b8968847b9392817cb835fe9f5cf032b85aeeb7c1addfd4910a6c43`.
- 실행기: `foothold_s2/eval/recompose_c_layer_v34.py`. CPU로 원자료를 읽어 각 원본 `out` 옆 `out_v34`에 D48 이름을 그대로 썼다. Isaac Kit · GPU 촬영은 새로 실행하지 않았다.
- 결과: 135편 모두 450/450프레임, 로봇 분할 근거와 장면 · 지도 · 아래 띠 전 프레임 검사 PASS. 보류 0편. 기록 `D:/mai-tmp/scripter/c_layer_v34_recompose.log`.
- 첫 편: `D:/mai-tmp/c_layer_m6000_phase1_v2/out_v34/EX40-boxes_L0-m6000-eval_gt-1x-success.mp4`, SHA256 `f0fa828aff6215370c70edd6490cf27daadd4f3731230c74b83219c025a26994`. 범례 정지 화면은 같은 폴더의 `EX40-boxes_L0-m6000-eval_gt-1x-success.legend.png`이다.

## 재생 목록 되읽기

| 목록 | 확인 결과 |
|---|---|
| `C:/Users/AI-WS01/s2_lab/_playlists/EX40-C-m06000-all.m3u8` | 새 영상 135편, 중복 이름 0, 모든 경로 존재, 영수증 판 `v3.4-D168`, 목록 SHA256 `6fbc43e923336c58fd7cb8fe3a2f0ccdafcb287a3c9a8ff34785bd7ba47c59d0` |
| `C:/Users/AI-WS01/s2_lab/_playlists/EX40-C-m06000-fail.m3u8` | 이번 두 루트의 실패 정본 0편이므로 헤더만 있음 |
| `EX40-C-m06000-all_v32.m3u8` | 기존 목록 이름만 변경해 보존, SHA256 `06c9e8b5311cfe37b7207e1d6644dbfaa348508b3dcf09933d3359ac8e86c789` |
| `EX40-C-m06000-fail_v32.m3u8` | 기존 목록 이름만 변경해 보존, SHA256 `600e18056f1dd7d3fd6d3c04b49a0055e6a412dbacd31d1d28955804d4efb83e` |

이번 스냅샷은 20:16 KST에 확인한 영수증 135편이다. GPU0 루트의 정본 수는 합성 시작과 목록 갱신 시점 모두 27편이었다. 이후 새 촬영 영수증이 생기면 같은 실행기를 다시 돌려 새 영상과 목록을 추가해야 한다. 원래 촬영 대기열이 다시 움직여 옛 판 목록을 덮는지도 그때 확인해야 한다.
