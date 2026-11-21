> 분류: 제안 · 정책 정본 한 곳 → 앱 · go2 · Jetson 자동 최신
> 작성: Claude 세션 (오흥재 지시, app-lx) · 2026-11-22 04:3x
> 근거: 팀장 11/21 22:50 · 11/22 03:26 (제안 승인 · 병합도 최신으로 바로 · 개발 관련은 app-lx 담당) · `20261118-repo-roles-and-go2-handoff.md` v1.2 · 이 폴더 README v0.6 · foothold-app dev `1feb63c5` 실측
> 요지: lab 정본 폴더에 목록 파일 하나를 두고, 앱 · go2 · Jetson 이 모두 그것만 읽는다. 앱은 자동 시험 뒤 dev 에 바로 병합, 공개 go2 와 실기 전환은 갈림길로 팀장이 정한다
> 상태: 제안 · 갈림길 둘 (G1 공개 go2 에 정책 파일 · G2 Jetson 전환) 팀장 결정 필요

# 정책 정본 한 곳 → 앱 · go2 · Jetson

## 1. 지금 (11/22 실측)

| 자리 | 정책을 어떻게 아나 | 문제 |
|---|---|---|
| lab 정본 (`<이름>-app/`) | 폴더 · README · SHA256SUMS | 「지금 판」 이 README 문장에만 있다. 기계가 읽을 목록 없음 |
| app | 파일 이름 · SHA 를 코드 12 곳에 손으로 적음 (`deploy/prepare_sim.py` · `mobile/sim/*-adapter.js` · 시험 스크립트) | 새 판마다 손 교체 (PR #469 · #470). 서버 자산 폴더는 사람이 복사 |
| go2 (공개) | 없음 (`sim/policy/README.md` 만) | |
| Jetson | 없음 (정책 실행 환경 자체가 없음 · 11/22 묶음 준비) | |

## 2. 제안

### 2.1 목록 파일 하나 (lab)

`inbox/jay/20261103-policy-handoff/POLICY-MANIFEST.json` 을 정본으로 둔다. 모드 키마다 지금 판 하나.

```json
{
  "format": "foothold-policy-manifest/1",
  "updated": "2026-11-22",
  "approved_by": "오흥재",
  "modes": {
    "start": {"name": "start-m15500", "folder": "start-m15500-app", "files": {
      "start-m15500_map_on.onnx": "df91c2d7…", "start-m15500_map_off.onnx": "be6c8b10…"},
      "contract": "start-demo-onnx/1", "vectors": ["test_vectors_flat20_reconstruction.json", "…"], "real": true},
    "ame2": {"name": "ame2-m27001", "folder": "ame2-m27001-app", "files": {"ame2-m27001.onnx": "2f7a8b18…"},
      "contract": "ame2-onnx/2", "real": false},
    "nvidia": {"name": "nvidia-demo", "folder": "nvidia-demo-app", "files": {"policy_v2.onnx": "c9f3c5c0…", "policy_v2.f32": "da199be2…"}, "real": false}
  }
}
```

- 판을 바꾸는 사람 (lead · 팀장) 은 묶음 폴더를 만들고 이 파일의 한 칸만 바꾼다. 그 PR 병합이 「정본이 바뀜」 이다.
- `real` 은 실기에 올려도 되는 정책인지 (teacher · 시뮬 전용은 false).

### 2.2 앱 (자동 · 병합까지)

1. 앱은 `deploy/policy-manifest.json` (lab 목록의 사본) 만 읽는다. 어댑터 · `prepare_sim.py` · 시험 스크립트의 손 적은 이름 · SHA 를 이 파일에서 읽게 바꾼다 (한 번만 하는 코드 일 · app-lx).
2. 앱 저장소의 「정책 맞추기」 작업 (GitHub Actions, 매시 또는 lab 에서 dispatch): lab 목록이 바뀌었으면
   ① 사본 갱신 ② 정책 파일을 비공개 저장소에서 받아 SHA 대조 ③ 시험 벡터를 앱 실행기 (Node · 브라우저 Worker · Jetson 파이썬 실행기) 로 1e-4 안인지 ④ 통과면 PR 을 dev 에 **자동 병합** (팀장 03:26 「병합도 최신으로 바로」).
   실패면 병합하지 않고 PR 에 수치를 남긴다.
3. 서버 자산 폴더 (`/var/lib/foothold/private-assets`) 는 배포 때 목록을 보고 받는다 (지금처럼 사람이 복사하지 않음). dev 병합 = 서버 자동 배포이므로 2 의 시험이 그 앞 관문이다.

### 2.3 go2 (공개 · 최종 배포 묶음)

go2 는 앱 태그와 목록 사본을 가리키고, 앱 코드는 복사하지 않는다 (역할 문서 v1.2).

**갈림길 G1 · 공개 go2 에 정책 파일을 자동으로 올리나** (역할 문서 「공개라 정책 올리기는 팀장 확인 뒤」 와 03:26 「최신으로 바로」 가 부딪힘)

| 안 | 어떻게 | 좋은 점 | 나쁜 점 |
|---|---|---|---|
| A (권고) | go2 에는 목록 (이름 · SHA) 만 자동으로 올리고, 정책 파일 자체는 비공개 자리 (lab 릴리스 · NAS · 앱 서버) 에서 받아 SHA 로 대조 | 자동이어도 공개 저장소에 가중치가 나가지 않음 | 받을 자리 권한이 필요 |
| B | go2 에 정책 파일까지 자동 | 단순 | 팀원 정책 포함 가중치가 공개됨 (11/18 결정과 어긋남) |
| C | 지금처럼 팀장 확인 뒤 사람이 올림 | 안전 | 자동 최신 아님 |

### 2.4 Jetson (실기 · 저수준)

- agent (`apps/agent`, 저수준 실행기 = 팀장 11/19 01:27) 가 목록을 읽어 `~/foothold-policy/<모드>/<이름>/` 에 받고 SHA 대조 · 시험 벡터 (`python3 -m foothold_agent.policy.bench`) 까지 **자동**.
- **갈림길 G2 · 실제로 쓰는 판을 바꾸는 것도 자동인가**

| 안 | 어떻게 |
|---|---|
| A (권고) | 받기 · 확인은 자동, 「지금 쓰는 판」 전환은 앱 화면에서 팀장 (또는 총괄) 이 누를 때만. 로봇을 움직이는 프로그램이 바뀌는 일이라 foothold-go2 AGENTS.md 5a (로봇 명령은 팀장 동의) 와 맞춤 |
| B | 확인 통과면 다음 시작 때 새 판 자동 |

## 3. 순서 (app-lx)

1. 이 제안 확인 (G1 · G2).
2. lab 에 `POLICY-MANIFEST.json` 첫 판 (지금 판 그대로).
3. 앱: 목록 사본을 읽게 바꾸기 (어댑터 · prepare_sim · 시험) → PR.
4. 앱: 「정책 맞추기」 Actions (받을 자리 권한은 팀장).
5. Jetson: agent 받기 · 확인 (전환은 G2 결과대로).

## 4. 안 하는 것

- 학습 · 판 고르기 (lead · 팀장).
- 공개 저장소에 정책 파일 올리기 (G1 결정 전).
