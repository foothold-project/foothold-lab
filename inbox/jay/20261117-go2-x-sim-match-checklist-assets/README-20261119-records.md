분류: 실기 원자료 (읽기 전용 감시 기록)
작성: Claude 세션 (오흥재 지시, lead-lx)
근거: Jetson `go2_readonly_monitor` 출력 · 이슈 #861
요지: 11/19 쓰러진 뒤 15 초 기록 (01:27) 과 정상 서기 20 분 기록 (03:14) 두 벌
상태: 원자료 보관 · 해석은 #861 과 APP-ROBOT-DIRECTION-1119.md 5b · 사건 절

# 11/19 Go2 X 읽기 전용 감시 기록 두 벌

둘 다 Jetson 에서 로봇 상태를 **읽기만** 하는 감시 도구 (`go2_readonly_monitor`) 로 남긴 것이다. 로봇에 명령을 보내지 않는다.

## 20261119-0127-after-collapse

- 무엇: 01:22 서기 → 01:26 쓰러짐 (적색 점멸 · 뒷다리 뒤집힘) 직후 01:27 에 켠 10 초 기록.
- 보이는 것: 배터리 16 % · RR hip 71 °C (다른 hip 31~35 °C) · reserve 0 이 아닌 관절 있음 · sport 상태 1001.
- 빠진 것: 서 있던 4 분 동안의 기록은 없다 (lead 가 서기 전에 장시간 감시를 켜지 않았다 · #861 에 잘못으로 기록).

| 파일 | sha256 |
|---|---|
| console.log | dd79bdb8d41a0a0b71b059754e5a256489cae1c332e893096b0c5d603ffa3e31 |
| monitor.csv (500 행 · 50 Hz) | dca44ad4cc4c14f3b852f2af936e05c146f241c90b93d56f16e47ee52fbe3721 |

## 20261119-0314-stand-monitor

- 무엇: 03:15 부터 20 분 서 있는 동안의 기록 (팀장이 Stand · 감시를 먼저 켬).
- 보이는 것: 배터리 93 → 82 % · 가장 뜨거운 관절 46 °C (RR calf) · reserve 0 · 오류 메시지 0. 정상 서기.
- monitor.csv 는 57 MB 라 gzip 으로 줄여 올렸다. 원본은 ai-lx01 `/home/jay/data/go2x_raw/20261119-0314-stand-monitor/monitor.csv`.

| 파일 | sha256 |
|---|---|
| console.log | c98fcf7abd9fd7963c26a3cd517ceb086e9fcc6768772e9d56bc8de90b4c7fff (Jetson 원본과 같음) |
| monitor.csv (원본 · 60000 행 · 50 Hz) | e669223583fd5a720b134597d8f0df2ea8dea4715edb70ad655b802aebfae3e2 (Jetson 원본과 같음) |
| monitor.csv.gz (올린 것) | d872485c33bded232436366185cc5257105b44935e705bc523ad780e0c695bce |

풀어서 원본 sha 를 확인하려면: `gunzip -c monitor.csv.gz | sha256sum`.
