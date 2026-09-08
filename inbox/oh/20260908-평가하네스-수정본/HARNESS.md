# RunPod 평가 하네스 (`play_eval.py` 계보)

> 분류: 실험
> 작성: 오현민 · 2026-09-08 16:40
> 근거: 실측
> 요지: 2026-09-08 지형 한계선 측정에 쓴 평가 하네스의 사용법과, 그 도중 고친 조용한 오작동 4건이 코드 어디에 들어갔는가
> 상태: 초안

> `sim/eval/` 의 `eval_generalization.py` 와 **다른 하네스다.** 섞지 않는다.

2026-09-08 「지형 한계선 측정 (틈 · 턱 · 보폭)」 실험에 실제로 쓴 코드다.
그 실험 도중 발견해 고친 조용한 오작동 4건(#297 #298 #299 #300)이 이 판에 들어 있다.
지금까지 Pod 과 노트북 로컬 사본에만 있었다.

🔴 **이것은 제출본이다. `sim/eval/` 로 옮길지는 팀장이 판단한다.**
팀원이 쓸 수 있는 자리는 `inbox/<자기이름>/` 이다(`AGENTS.md` 2절).

결과와 결론: 위키 「연구 기록 20 · 지형 한계선 측정」.

---

## 두 하네스를 헷갈리지 않기

| | `sim/eval/eval_generalization.py` | `play_eval.py` (이 폴더) |
|---|---|---|
| 어디서 도나 | Isaac Lab 깔린 워크스테이션 | RunPod 팟 |
| 지형 정의 | `generalization_env_cfg.py` | `terrain_cfg.py` |
| 이력 관리 | `PROVENANCE.md` (2026-08-22 스냅샷 대조) | 없음. 이 `HARNESS.md` 가 전부 |
| 무엇을 재나 | 미경험 험지 10종 일반화 | 지형 파라미터 스윕 (틈 · 턱 · 명령속도) |

**같은 이름의 파일이 아니므로 충돌하지 않지만, `terrain_cfg.py` 와
`generalization_env_cfg.py` 중 어느 것이 활성 지형 정의인지 매번 확인하고 쓴다.**

## 어디에 놓고 도는가

이 폴더의 `.py` 3개와 `.sh` 4개는 **Isaac Lab 트리 안에서 돈다.**

```
<볼륨>/isaaclab/scripts/reinforcement_learning/rsl_rl/
    play_eval.py
    terrain_cfg.py
    terrain_audit.py
```

`play_eval.py` 머리 주석에 적힌 이유: 같은 이름 파일이 양쪽에 있으면 isaaclab 쪽이
이겨서, 고친 `terrain_cfg.py` 대신 원본이 불린다. 그래서 이 자리여야 한다.

셸 러너는 아무 데나 두어도 되지만 `run_pipeline.sh` 는 `run_audits.sh` ·
`run_gap.sh` 를 **자기 위치 기준**으로 부르므로 셋을 같은 폴더에 둔다.

볼륨 경로는 `VOL` 환경변수로 받는다. 기본값 `/data/$USER`.

```bash
export VOL=/data/<사용자ID>
bash run_pipeline.sh
```

## 무엇이 무엇인가

### Pod 에서 도는 것 (GPU · Isaac Lab 필요)

| 파일 | 하는 일 |
|---|---|
| `play_eval.py` | 평가 본체. 정책을 얹고 에피소드를 돌려 `*_steps.csv` 와 `manifest.json` 을 낸다 |
| `terrain_cfg.py` | 지형 정의. `FLAT_GAP_SWEEP` `ROUGH_GAP_SWEEP` `STEP_SWEEP` 등 |
| `terrain_audit.py` | **관문.** 지형이 의도대로 만들어졌는지 검사한다. 실패하면 `os._exit(2)` |
| `run_audits.sh` | 지형 18종 전수검사 |
| `run_gap.sh` | 틈 스윕 평가 (브리지 4 + FLAT 7 + ROUGH 7 + 영상) |
| `run_stepheight.sh` | 높이 턱 스윕. 고정할 틈 [m] 을 인자로 받는다 |
| `run_pipeline.sh` | 검사 -> 전부 통과했을 때만 평가. **옛 이름 `chain.sh`** |

### 노트북에서 도는 것 (`analysis/`, 표준 라이브러리만)

| 파일 | 하는 일 | 필요한 환경변수 |
|---|---|---|
| `summarize.py` | 원시 CSV -> 성공률 · 낙상률 · 부트스트랩 CI95 | (없음. 인자로 CSV 를 받는다) |
| `stride.py` | 발 접촉 CSV -> 보폭 · 착지주기 · 접지비율 | `STRIDE_OUT` |
| `sweep_table.py` | 스윕 결과표 | `GAP_OUT` |
| `audit_table.py` | 지형 감사 결과표 | `GAP_OUT` |
| `pick_gstar.py` | CI 하한 기준으로 g* 선정 | `GAP_OUT` |

🔴 **`analysis/verify_alt.py` 만 예외다.** 교대 높이 생성기를 검증하려고
`AppLauncher` 를 띄우므로 **Isaac Lab 이 필요하다.** 이름만 보고 노트북에서
돌리려 하면 `ModuleNotFoundError: isaaclab` 이 난다.

`summarize.py` 는 `--help` 를 지원하지 않는다(argparse 를 안 쓴다). 인자 설명은
파일 274행 근처 주석에 있다.

## 이 판에 든 수정 4건

| 이슈 | 무엇이 틀렸나 | 어디 |
|---|---|---|
| #297 | `terrain_audit.py` 에서 `AssertionError` 가 났는데 `exit=0` 이었다. 검사에 실패한 지형으로 평가가 그대로 진행됐다 | `terrain_audit.py:293-305` (flush 를 `close()` 앞으로, `os._exit(2)`), `run_audits.sh:5` (로그의 `[AUDIT] OK` 이중 확인) |
| #298 | `int(0.075/0.025)` 가 2 라서 틈 7.5 cm 가 5 cm 로 만들어졌다. 에러가 안 난다 | `terrain_cfg.py:417-419`, `:596` (`round` 후 `eps` 스냅. 수평 · 수직 양쪽) |
| #299 | 검사기가 `horizontal_scale` 을 하위 cfg 에 전파하지 않고, 생성기 함수를 하드코딩했다. **만든 지형과 검사한 지형이 달랐다** | `terrain_audit.py:80` (전파), `:114` (`cfg.function` 을 따라감) |
| #300 | `play_eval.py` 가 `--flat` `--mixed` `--mixed8` 셋만 받아 새 지형 cfg 를 부를 방법이 없었다 | `play_eval.py:140-147` (`--terrain_cfg NAME` · `DICT:key` 문법) |

**넷 다 에러를 내지 않는다.** 종료코드 0, CSV 정상 산출, 틀린 숫자만 조용히 나온다.
그래서 기록이 유일한 방어선이다. 자세한 것은 각 이슈와 위키 11절 「파이프라인 결함」.

## 재현할 때 밟는 지뢰

1. **틈 7.5 cm 의 격자 칸 수가 3 인지 확인한다.** 2 면 #298 이 되살아난 것이고
   그 실험은 버려야 한다. `audit_table.py` 의 「gap_px」 열을 본다
2. **체크포인트를 절대경로(`--checkpoint`)로 고정한다.** 빠뜨리면 로그 폴더에서
   아무 중간 산출물을 집는다. 에러가 안 난다. `manifest.json` 의
   `checkpoint.source` 가 `cli_absolute` 인지 본다
3. **「경계(boundary)」가 두 뜻으로 쓰인다.** `manifest` 에서
   `runup_x_m` = 험지 시작, `boundary_x_m` = 타일 끝인데, `terrain_audit.py` 에서는
   `boundary_x_m` 이 험지 시작이다. 표에 손으로 적지 말고 `manifest` 에서 읽어 넘긴다
   (`sweep_table.py` 가 그렇게 한다)
4. **보폭은 `contact` 의 0 -> 1 전이만 센다.** `contact == 1` 인 스텝을 다 세면
   보폭이 0 에 가깝게 나온다

## 원자료

CSV 와 영상은 용량 때문에 저장소에 없다. 목록과 SHA-256 은 `DATA.md`.

## 검사 기록 (2026-09-08, 커밋 전)

| 검사 | 결과 |
|---|---|
| `python3 -m py_compile` 9개 | 전부 통과 |
| `bash -n` 4개 | 전부 통과 |
| `--help` | `terrain_audit.py` 정상. 나머지는 Isaac Lab 미설치(노트북) 또는 argparse 미사용 |
| `summarize.py` 실동작 | `flat025_steps.csv` 로 위키 게재값 재현. 성공률 0.222 CI95 [0.152, 0.286] · 낙상 0.086 [0.035, 0.142] · 전진 중앙값 2.28 m · 에피소드 109. **표 ② FLAT 2.5 cm 행과 일치** |
