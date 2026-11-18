> 분류: 현장 진단 도구
> 작성: 오흥재 · 2026-11-18
> 근거: 20261118 순정 Stand 열 사건 · 설치된 Unitree SDK2 receive-only subscriber
> 요지: 다음 냉간 부팅에서 Damping 상태의 온도·reserve·lowcmd·Sport marker·errorlist를 50 Hz로 함께 기록한다
> 상태: source 정적 guard·CSV 요약기 단위시험 2건·Jetson 실제 SDK build·5초 receive-only smoke run 통과
> 판: v1.1

# Go2 냉간 부팅 read-only monitor

이 도구는 다음 부팅 때 순정 Stand보다 먼저 실행할 안전 관찰기다. `rt/lowstate`, `rt/lowcmd`, `rt/sportmodestate`, `rt/errorlist`를 **구독만** 한다. publisher와 Unitree motion client를 만들지 않는다. 로봇을 눕히거나 Damping으로 바꾸는 기능도 없으므로 사람은 조이스틱과 물리 전원 차단을 계속 준비해야 한다.

## 기록하는 값

- BMS SOC/status, pack voltage/current.
- 12개 모터 temperature, `reserve[0]`, lost, q, dq.
- 현재 `rt/lowcmd`의 kp, kd, q command.
- SportModeState의 `error_code`, mode, gait type, body height.
- `rt/errorlist` callback 수.
- lowstate/lowcmd/sportmodestate의 마지막 callback 이후 지난 시간(ms). CSV가 계속 써져도 DDS 입력이 끊긴 경우를 구분한다.

`SportModeState.error_code=1001`은 설치된 공식 `sport_api.hpp`에서 Damp API ID다. 이 도구는 그 필드를 `sport_marker`로 표시하며 fault로 판정하지 않는다. `reserve[0]`의 비트 의미와 안전 온도 문턱도 임의 판정하지 않고 원값을 보존한다.

## 전원 투입 전 조건

1. 업체 답변 또는 사용자가 정한 안전 재개 조건이 있어야 한다.
2. 로봇을 Damping 상태로 안정되게 놓고 사람·물건·케이블을 다리에서 치운다.
3. Stand 버튼을 누르지 않는다.
4. ai-lt01과 Jetson의 유선 직결 `192.168.50.1 ↔ 192.168.50.2`를 사용한다.

## ai-lt01에서 Jetson으로 복사

foothold-lab main을 받은 ai-lt01에서 실행한다.

```bash
cd /home/jay/jay/foothold/foothold-lab
git pull origin main
scp -r inbox/jay/20261118-go2-readonly-boot-gate \
  nvidia@192.168.50.2:/home/nvidia/go2_diag/
```

## Jetson에서 build

```bash
cd /home/nvidia/go2_diag/20261118-go2-readonly-boot-gate
python3 verify_readonly_source.py
cmake -S . -B build
cmake --build build -j2
```

source guard는 금지된 publisher/motion client token이 없고 네 receive-only subscriber가 있는지 보는 정적 검사다. 실제 binary 동작이나 안전을 보증하지 않으므로 build 결과와 현장 동작을 별도로 확인한다.

## Damping 냉간 기준 기록

먼저 120초를 기록한다. 출력 폴더는 새 이름으로 만들고 기존 기록을 덮지 않는다.

```bash
mkdir -p /home/nvidia/go2_diag/records/20261118-cold-damping
cd /home/nvidia/go2_diag/20261118-go2-readonly-boot-gate
./build/go2_readonly_monitor \
  enP8p1s0 \
  120 \
  /home/nvidia/go2_diag/records/20261118-cold-damping/monitor.csv \
  2>&1 | tee /home/nvidia/go2_diag/records/20261118-cold-damping/console.log
```

화면에는 1초마다 FR/FL hip 온도, 전체 최고 온도, `reserve[0]` nonzero 개수, 최대 kp/kd, Sport marker, errorlist 수가 나온다. 다음 중 하나면 Stand로 가지 않고 Jetson 정상 종료 뒤 Go2를 끈다.

- 전면 적색 점멸 또는 비정상 소리/자세.
- 냉간부터 FR/FL hip `reserve[0]`가 다시 `0x04`.
- 앞 hip 온도가 다른 관절과 달리 빠르게 계속 상승.
- Damping인데도 설명되지 않은 큰 kp/kd가 지속.
- `state_age_ms`가 계속 커지거나 state callback 수가 멈춤. CSV 자체는 stale 값을 계속 기록할 수 있으므로 파일 크기만 보지 않는다.

위 항목은 현장 중단 조건이지 공식 fault code 해석이나 안전 온도 문턱이 아니다.

## 순정 Stand 1회가 허용된 뒤

업체와 P0 관문이 허용한 경우에만 새 폴더와 새 monitor process로 기록한다. monitor가 화면과 CSV를 정상적으로 쓰는 것을 먼저 확인하고, 사용자가 조이스틱으로 Stand 1회를 수행한다. 기록 중 monitor를 재시작하거나 다른 DDS command process를 띄우지 않는다.

Stand가 끝난 뒤 아래를 원본 그대로 보존한다.

- `monitor.csv`, `console.log`.
- 사용자가 누른 조이스틱 버튼 순서와 화면에 보인 mode 이름.
- 전면 LED 영상 또는 사진.
- 시작·최고·종료 온도와 `reserve[0]`, kp/kd 전환 시각.

CSV 요약은 다음 명령으로 만들고 원본과 같이 둔다. 요약기는 숫자를 모을 뿐 안전 합격을 자동 판정하지 않는다.

```bash
python3 summarize_monitor.py \
  /home/nvidia/go2_diag/records/20261118-cold-damping/monitor.csv \
  /home/nvidia/go2_diag/records/20261118-cold-damping/summary.json
```

## 실행 뒤 판정하지 말아야 할 것

- `1001`만 보고 오류라 부르지 않는다.
- `reserve[0]=0` 한 번만 보고 열 문제가 해소됐다고 하지 않는다.
- 모터 온도 숫자만으로 Unitree 공식 허용 한계를 만들지 않는다.
- monitor가 끝났다는 이유로 Stand·정책·SLAM 관문을 통과 처리하지 않는다.

## 변경 이력

| 판 | 날짜 | 내용 |
|---|---|---|
| v1.1 | 2026-11-18 | Jetson Orin NX의 설치 SDK2로 실제 build · 5초/250표본 smoke run · lowstate 약 500 Hz, lowcmd 약 494 Hz, sport 약 300 Hz, errorlist 0, message age 최대 약 14 ms 확인 |
| v1.0 | 2026-11-18 | lowstate/lowcmd/sportmodestate/errorlist 동시 receive-only monitor, source guard, CSV 요약기와 단위 시험, 냉간 Damping 실행 절차 작성 |
