> 분류: A/정책학습
> 작성: 오흥재(analyst-lx) · 2026-11-14
> 근거: lead 02:25 의뢰 · #555 · scripter 48650679
> 요지: v27 Kit 5회 원자료를 양 rank로 재계산하고 기록 경로를 검증
> 상태: CPU 확인됨 · 새 Kit에서 수정된 기록은 미확인

# v27 Kit KL 분석과 기록 고침

보고서: [REPORT-KL-v27-1114.md](results/REPORT-KL-v27-1114.md). 그림과 숫자는 `analyze.py`가 만든다. 이 분석기는 지정된 **v27 5회 시험용**이며 공식 판정기나 일반 학습 관문이 아니다.

```bash
CUDA_VISIBLE_DEVICES='' PYTHONDONTWRITEBYTECODE=1 OMP_NUM_THREADS=2 MPLCONFIGDIR=/home/jay/mai/tmp/analyst/kl-kit-1114/mpl /home/jay/miniforge3/envs/isaac311/bin/python -B inbox/jay/20261114-analysis/kl-kit-v27/analyze.py --rank0-root /home/jay/data/foothold/s2_lab/ex42_kitshort_20261114_022112/main/EX-42-B-E1-again-kitshort_20261114_022112 --rank1-root /mnt/win-d/mai/tmp/runner/kitshort_20261114_022112/ex42_probe_rank1_EX-42-B-E1-again-kitshort_20261114_022112 --out /home/jay/mai/tmp/analyst/kl-kit-replay
```

설치기의 진입점 시그니처는 그대로다. `install_runner_kl_audit(runner, runtime=self)`. 진입점은 양 rank 모두 호출하기 전에 `runtime.record_dir`을 공유 원 실행 폴더로 설정한다. `runtime.plan_sha256`, `parent_sha256`, `stage_id`는 실제 값을 쓴다. 이미 v27의 `train_start.py:1206`에서 record_dir을 넣고 `:1313`에서 attach_runner를 부르는 것을 읽었다. 통합판의 931ceaa4 고침(plan/parent SHA와 update_start 검증)을 보존하며, scripter 48650679의 공유 출력 경로 고침을 통합 기준에 반영했다. 운영 사본을 수정하지 않았다.

## CPU 검증

```bash
CUDA_VISIBLE_DEVICES='' PYTHONDONTWRITEBYTECODE=1 OMP_NUM_THREADS=2 /home/jay/miniforge3/envs/isaac311/bin/python -B -m pytest foothold_s2/tests/test_ppo_kl_audit_cpu.py foothold_s2/tests/test_ppo_kl_audit_two_rank_cpu.py inbox/jay/20261114-analysis/kl-kit-v27/test_analyze.py -q -p no:cacheprovider --basetemp=/home/jay/mai/tmp/analyst/kl-kit-tests
```

- 기록기 21 PASS(8.28초), 집계 답 아는 입력 3 PASS(0.06초). 원 로그 `/home/jay/mai/tmp/analyst/kl-kit-1114/tests.log`.
- 양 rank gloo의 실제 설치기를 경유해 private runner.log_dir·disable_logs 조건에서도 공유 폴더와 같은 identity를 확인했다. actor 거울 끔·critic 거울 켬·한 rank 유효행 0의 세 경로에서 observer OFF/ON의 모델·optimizer·RNG·손실·LR·collective가 같았다.
- 정상 대조 8 PASS 뒤 돌연변이 4/4 검출. 결과 [mutations.json](mutations.json), 원 시험 로그 `/home/jay/mai/tmp/analyst/kl-kit-1114/mutations/`.

| 되살린 결함 | 실패 시험 수 |
|---|---|
| 출력 폴더를 runner.log_dir로 | 2 |
| 두 plan SHA 충돌 검사를 삭제 | 1 |
| 분산 실행인데 공유 경로 없어도 허용 | 1 |
| 출력 identity의 plan SHA를 null로 | 3 |

다음 실제 Kit에서 `RUN/ppo_kl_audit/ppo_kl_rank{0,1}.jsonl` 두 파일·같은 비null plan SHA·update_start/complete·100% 미니배치 결합을 확인해야 한다. CPU 성공을 새 GPU 실행 확인으로 쓰지 않는다. **desired_kl·LR 상하한·보상·명령·학습 사슬 변경 없음.**
