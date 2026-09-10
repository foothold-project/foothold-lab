# A/평가

일반화 벤치마크와 지표 측정. 담당 오현민.

> 폴더는 이슈의 «작업 영역» 라벨과 1:1 이다.
> 이 자리에 넣을 것이 생기면 브랜치를 파고 PR 로 올린다. inbox 를 거치지 않는다.

---

## 지금 상태 (2026-09-03)

**하네스 확장 `#125` 작업 중입니다.** 활성 하네스 본체가 생겼고,
2026-09-03 에 **처음으로 실제로 돌아 평지 기준선 100판**을 냈습니다 (`#99`).
같은 날 **미경험 험지 10종을 우리 기준(1.0 m/s)으로 1000판** 다시 쟀습니다 (`#99`).
`run_manifest.json` 에 정책 sha256 · GPU · Isaac Lab 커밋 · 실행 시각이 함께 남습니다.

그리고 같은 날 **20초 규격으로 다시 냈습니다** (`#99` 2번).
첫 판은 지형이 좁아 12초로 줄여 돌린 것이라 규격 밖이었습니다.
**발표에 쓸 것은 `results/20260903-flat-10m-spec20s/` 입니다.**

| 무엇 | 어디 |
|---|---|
| 원본 추적 · 무엇이 복원물인가 | `PROVENANCE.md` |
| 문서에서 복원한 Candidate 스냅샷 | `provenance/candidate-20260822/` |
| 스냅샷 재추출 · 대조 도구 | `provenance/extract_candidate.py` |
| 판정 · 집계 순수 함수 | `metrics.py` |
| 지형 이름과 순서 · **장애물 구간** | `terrains.py` |
| **에피소드 시계열 (parquet)** | `timeseries.py` |
| 활성 지형 설정 | `generalization_env_cfg.py` |
| 스냅샷과의 동치 · 구조 시험 | `tests/` |
| Go2 강체·충돌체 이름 프로브 | `probe_go2_bodies.py` |
| Go2 관절 한계 프로브 | `probe_go2_joint_limits.py` |
| **활성 하네스 본체** | `eval_generalization.py` |
| 원시 CSV -> 요약 · Wilson 구간 | `report.py` |
| **영상에 계측값 겹쳐 그리기** | `overlay/` |
| 실측 결과 | `results/` |
| 평지 10 m 기준선 100판 | `results/20260903-flat-10m/` |
| 험지 10종 1.0 m/s 1000판 | `results/20260903-rough10-1.0mps/` |
| pit env 44 · 겹쳐 그리기 실측 | `results/20260909-pit-env44-overlay/` |

## 영상만으로 읽기 (`overlay/`)

CSV 와 영상을 번갈아 보지 않아도 되게, **이미 만들어진 mp4 에 프레임별
계측값을 겹쳐 그립니다.** 시뮬을 다시 안 돌리고 렌더 경로도 안 건드립니다.

```bash
python sim/eval/overlay/render.py --video <mp4> --trace <trace.csv> --out <mp4>
```

프레임별 기록은 `record_flat_baseline.py --trace_csv <경로>` 로 영상과 함께
나옵니다. **그 인자를 안 주면 기존 동작 그대로입니다.**
자세한 것은 `overlay/README.md` 에 있습니다.

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
python sim/eval/report.py sim/eval/results/20260903-flat-10m-spec20s/generalization_raw.csv
```

## 머리 접촉 열 셋은 판정이 아니다 (2026-09-09)

원시 CSV 끝에 `head_contact_count` · `head_contact_peak_n` · `head_contact_first_s`
가 붙습니다. 실기 Go2 의 라이다가 얹히는 머리 링크(`Head_upper` · `Head_lower`)에
힘이 걸린 스텝 수와 세기입니다.

> **★ `overall_success` 에 안 들어갑니다.** 판정은 지금도 네 축
> (생존 · 전진 · 속도추종 · 방향)의 AND 입니다. **다섯째 축을 만들지 마십시오.**
> 근거 셋(성공률이 반드시 깎임 · 파손 임계 근거 없음 · `termination_reason` 이
> 조용히 거짓말함)은 `docs/research/20260909-head-contact-observation.md` 에 있습니다.
> `tests/test_metrics.py` 의 `HeadContactIsNotJudgement` 가 이것을 못 박습니다.

링크 이름은 **Go2 USD 를 직접 열어 확인한 것**입니다 (`probe_go2_bodies.py`).
아이작 Go2 에는 `lidar` 라는 이름의 강체가 없습니다. USD 가 바뀌어 이름이 달라지면
하네스가 **시작할 때 죽습니다.** 0 으로 찬 CSV 를 내는 것보다 낫기 때문입니다.

**옛 CSV 는 그대로 읽힙니다.** 정본 `results/20260903-rough10-1.0mps/` 는 20열이고
이 열들이 없습니다. `report.py` 가 없는 열을 빈 목록으로 처리해 머리 절을 아예
안 냅니다. 「안 쟀다」가 「안 닿았다」로 둔갑하지 않습니다.

## 분석 열 셋 (2026-09-10)

원시 CSV 가 **27열**이 됐습니다. `mean_reward_per_step` 뒤, 머리 접촉 셋 앞에
분석 열 셋이 붙습니다.

| 열 | 무엇 | 없으면 (`""`) |
|---|---|---|
| `traversal_success` | 생존 · 전진 · 방향 **셋만**의 AND. 속도 추종을 뺐다 | 언제나 값이 있다 |
| `gate_speed_mps` | 통과선을 지나는 **그 순간**의 전진 속도 (m/s) | 통과선을 못 넘겼다 |
| `speed_drop_ratio` | 장애물 구간 최저 전진 속도 / 명령 속도 | 구간에 표본이 없다 |

> **★ `traversal_success` 는 성공률이 아닙니다.** 이름에 `success` 가 들어가지만
> 판정은 지금도 `overall_success` 하나이고, 그것은 네 축의 AND 입니다.
> **문서 · 표 · 발표 · 이슈 어디에도 이 열을 성공률로 적지 마십시오.**
> 쓰임새는 「넘긴 했는데 명령 속도를 못 따라간」 에피소드를 세는 것입니다.
> `overall_success` 가 참이면 이 열도 반드시 참이고, 반대는 아닙니다.

**셋 다 판정 밖입니다.** 옛 24열의 값은 한 칸도 안 바뀝니다.
2026-09-10 에 같은 씨앗 · 같은 인자로 옛 코드와 새 코드를 나란히 돌려
**공통 24열 x 30줄이 글자 그대로 같은 것**을 확인했습니다 `확인됨`.

### `speed_drop_ratio` 의 정의

```
speed_drop_ratio = (장애물 구간 안 최저 전진 속도) / (명령 전진 속도)

장애물 구간 = [플랫폼 절반 폭, 그 지형의 장애물 끝]   ← 출발점 기준 전진거리
```

**구간을 지형 설정에서 계산합니다.** 지형 이름으로 숫자를 박아 두지 않았습니다
(`terrains.obstacle_zone_m`). `--difficulty` 를 바꾸면 구간도 함께 움직이고,
어느 규칙으로 잡았는지가 `run_manifest.json` 의 `obstacle_zone_basis` 에 남습니다.

| 지형 종류 | 끝을 어디로 | 난이도 0.5 에서 |
|---|---|---|
| `gap` | 플랫폼/2 + 틈폭(d) | 1.025 m |
| `floating_ring` | 플랫폼/2 + 고리폭(d) | 1.175 m |
| `rails` | 바깥 레일의 바깥 모서리 | 2.880 m |
| 그 밖 (`pit` 포함) | 타일 절반 | 4.000 m |

> **팀장이 적어 준 숫자와 둘이 다릅니다. 확인이 필요합니다.**
> 지시서의 값은 `gap 1.02` · `pit 2.70` · `rails 2.70` 이었습니다.
> `gap` 은 같습니다(난이도 0.5 에서 1.025).
> `rails` 는 **2.70 이 바깥 레일의 «안쪽» 모서리**입니다. 두께
> `rail_thickness_range[1]` 0.18 을 더한 2.88 이 바깥 모서리이고, 여기서는
> 그것을 「끝」으로 봤습니다.
> `pit` 은 2.70 이 나올 자리가 없습니다. 그 비율(0.6)은 `double_pit=True` 일 때만
> 쓰이는데 우리 설정은 `False` 입니다 (`mesh_terrains.py` 470행). 구덩이의
> 장애물은 플랫폼 가장자리의 턱 하나뿐이라 폭이 0 이 되어, 타일 절반으로 넓혔습니다.
> 근거는 Isaac Lab 0.54.2 원문을 직접 읽은 것이고 `확인됨`,
> **렌더해서 눈으로 재보지는 않았습니다** `미확인`.

속도는 **몸통 좌표계의 전진 성분**입니다. 명령이 걸리는 축이 그 축이고
`overlay/trace.py` 의 `vx_mps` 와 같은 값입니다. 뒤로 밀리면 음수가 나오고,
그대로 둡니다. 「많이 줄였다」의 극단이지 결측이 아닙니다.

## 에피소드 시계열 (`--timeseries` · 기본 꺼짐)

에피소드마다 시간축 원자료를 parquet 한 장으로 남깁니다.

```bash
python sim/eval/eval_generalization.py ... --timeseries
```

```
results/<실행이름>/<지형>/
   generalization_raw.csv        에피소드마다 한 줄 (27열)
   generalization_summary.csv    집계
   timeseries/
      ep0001.parquet             raw CSV 의 첫째 줄
      ep0002.parquet             raw CSV 의 둘째 줄
```

**인자를 안 주면 한 줄도 안 돕니다.** CSV 도 실행 시간도 지금과 같습니다.
켰을 때의 값은 30 에피소드 실측에서 34.0초 -> 35.7초였습니다 `확인됨`.

**성공한 에피소드도 남습니다.** 같은 난이도에서 넘은 것과 못 넘은 것을 겹쳐 보는
것이 이 자료의 가장 큰 쓰임새라, 실패만 남기지 않습니다.

**92열입니다.** 앞 16열은 `overlay/trace.py` 의 열을 **글자 그대로** 씁니다
(두 벌을 만들지 않았습니다). 뒤에 몸통 16 · 발 12 · 관절 48(각도 · 속도 · 토크 ·
목표 각도 x 12)이 붙습니다.

**크기는 재본 값입니다** `확인됨` (20초 규격 한 에피소드 · 1,000줄 x 92열).

| 형식 | 한 에피소드 | 19,000 에피소드면 |
|---|---|---|
| CSV | 1.62 MB | 약 30 GB |
| parquet | **0.28 MB** | **약 5.2 GB** |

**줄임 비율은 에피소드 길이에 딸립니다.** 1,000줄짜리는 5.73배지만, 일찍
넘어져 146줄인 에피소드는 3.6배입니다 `확인됨`. parquet 의 꼬리표(footer ·
페이지 머리)가 짧은 파일에서 상대적으로 크기 때문입니다.

`pyarrow` 가 필요합니다. 없으면 **시뮬을 띄우기 전에** 죽고 무엇을 깔라고
말합니다. 7분을 돌고 끝에서 죽지 않게 하는 자리입니다.

```bash
python -m pip install pyarrow
```

실행이 끝나면 하네스가 **파일 수를 세고, 첫 장을 되읽고, 그 장을 접어**
판정 표의 그 줄과 대조합니다. 셋 중 하나라도 어긋나면 그 자리에서 죽습니다.

## 결과가 둘인데 어느 것을 쓰나

| 폴더 | 무엇 | 쓰나 |
|---|---|---|
| `results/20260903-flat-10m-spec20s/` | **20초 규격** 100판 | **이것을 쓴다** |
| `results/20260903-flat-10m/` | 12초로 줄여 돌린 100판 | 규격 밖. 증거로만 둔다 |
| `results/20260903-flat-10m/spec-20s/` | 테두리를 안 넓히고 20초를 돈 100판 | **성능으로 인용 금지.** 낙하를 잰 숫자다 |

## 실제로 돌리려면

지형 생성 · 정책 로딩 · CSV 산출에는 **Isaac Lab 과 GPU 가 필요합니다.**
RunPod 팟에서도 되고, Isaac Lab 이 깔린 워크스테이션에서도 됩니다.
2026-09-03 기준선은 워크스테이션에서 냈습니다. 명령줄 전문과 환경은
`results/20260903-flat-10m-spec20s/README.md` 에 있습니다.

**세계의 크기와 시간이 맞아야 합니다.** 이상 거리(`command_vx x eval_duration`)가
지형의 전방 한계보다 길면 로봇이 지형 밖으로 나가고, 그 판은 정책 성능이 아니라
**낙하**를 재게 됩니다. 2026-09-03 에 실제로 그렇게 됐습니다.

**이제는 하네스가 실행 전에 막습니다.** 좁으면 시작하지 않고 얼마나 모자란지
말해 줍니다. 시간을 줄이지 말고 `generalization_env_cfg.py` 의 `border_width` 를
키우십시오. 테두리는 격자 **바깥**이라 험지 10종의 타일도 `env_origin` 도
안 움직입니다 `확인됨` (`results/20260903-flat-10m-spec20s/README.md` §4-2).

| `border_width` | 전방 한계 | 담기는 시간 (1.0 m/s) |
|---|---|---|
| 10.0 (옛값) | 14 m | 12초까지 |
| **20.0 (지금)** | **24 m** | **20초 규격 + 4 m 여유** |
