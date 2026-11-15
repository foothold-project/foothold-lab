> 분류: 실험
> 작성: 오흥재 (lead_tmp 기록) · 2026-10-21
> 근거: #555 6309063175 · 6309236302 · 6310259601 · 사슬 상태 파일
> 요지: 몸 선속도 관측을 더한 C2-blind의 중단 이력과 G0 진단 연결을 기록한다
> 상태: 중단 보고 · 전체 목표 미완료 · 원자료 재측정·영상 판독 미실시

# EX-08 C2-blind · 중단된 선속도 관측 진단

## 가설

몸 선속도를 정책 관측에 제공하면 기는 자세가 바뀌는지 확인하려던 진단이다. [설정·시작 보고](https://github.com/foothold-project/foothold-lab/issues/555#issuecomment-6309063175)를 읽은 것은 `확인됨`이다. 댓글 게시 14:48:40과 본문 시작 14:45를 구분한다. 이 댓글만으로 결과 전 등록 시점을 입증하지 않는다.

## 설정

- 사슬 이름 `c2_blind_train`.
- 부모 S1-a 설정 + 공통 fbg0.25·clip17에서 몸 선속도를 정책 관측에 제공했다는 lead 보고. 토크 벌점 변경은 이 판의 변경이 아니다. resume 여부·소비 커밋·cfg·정확한 학습 폴더는 미확인.
- 계획 1501회, 14:45 시작·15:00 중단이라는 보고. GPU·프로세스 직접 확인 미실시.

## 결과

영상 없음 · 미확인. 이 세션은 C2 보행 영상을 확인하지 않았다. [15:01:48 정정](https://github.com/foothold-project/foothold-lab/issues/555#issuecomment-6309236302)은 150회 중단, model_100.pt·latest.pt 보존을 보고했다. 직접 재측정한 값이 아니다. 최초 「약1100회」는 철회된 보고이며 이 판으로 가설을 채택·기각하지 않는다.

16:28에 읽은 `C:/Users/AI-WS01/s2_lab/chain/chain_state.json`에는 해당 키가 `running`으로 남았다. 저장 상태값일 뿐 프로세스 생존 증거가 아니다. cancelled 수정 보고와의 불일치를 lead에 알렸으며 상태 파일은 수정하지 않았다. 후속 확인은 EXP-MAP에 남긴다.

`C:/Users/AI-WS01/s2_lab/eval_new/cdiag_1021/`은 S1-a scan·blind·v2의 별도 기준 측정이라는 보고다. C2 결과나 영상 경로로 바꾸어 쓰지 않는다.

## 다음

자동 재개 계획은 없다. [후속 결정](https://github.com/foothold-project/foothold-lab/issues/555#issuecomment-6310259601)에 따라 S2-G0 두 명령 판으로 간다. 몸 크기 비율·3 cm·10° 자세 합격선 폐기와 기존 41·52·gates 관문 유지는 [실험 지도](EXP-MAP.md)를 따른다.
