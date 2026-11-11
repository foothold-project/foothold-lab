> 분류: 구현 · CPU 소비 검증
> 작성: verifier-lx · 2026-11-11
> 근거: lead 12:25 · PR652 2a6a0965 · CG 69e5ac6b:242/244 · sonnet 12:30 상한 상속 해석기 없음 답
> 요지: E1F 노출 문자열을 default/positive 사전으로 변경하고 실제 E1 종료 상한을 승인과 계획에서 대조
> 상태: CPU 144 통과 · 실제 E1 종료 상한 미측정 · 기동 보류 · GPU/Kit 미실행

# E1F 노출 소비 꼴

`terrain.exposure_at_E1F`를 `default: {exposure: 0.0, level_cap: 0}`과 `positive: [{family: A, kinds_of: continuous, exposure: 1.0, level_cap: null}]`로 바꿨다. PR652의 `positive`가 읽는 꼴이다. 듬성·B~E 노출은 0이다. `same_as_E1_end` 의미는 승인 칸 `boundary.exposure_source`에 보존했다.

**상한을 5로 추측하지 않는다.** CG:242/244는 E1 종료 상한 5 또는 6을 그대로 잇는다. `prerequisites.predecessor_exit.continuous_level_cap`과 `exposure_receipt_sha256`은 빈 값이다. E1 종료 뒤 실제 상한 영수증을 확보하고 승인 칸과 계획 positive의 정수 상한을 함께 채운 뒤 재고정한다. 관측된 최대 레벨을 상한으로 대신하지 않는다. 이 출처 자료는 기존 부모 증거를 구체화한 것이며 새로운 학습 정책이나 팀장 승인 단계가 아니다.

일반 승인 검사기의 선택 항목 `inherited_stage_templates`가 승인 칸의 정수를 고정 노출 꼴에 대입하고 계획과 대조한다. E1F 전용 validator를 새로 만들지 않았다. 빈 값·범위 밖 값·bool·승인 상한6/계획5·float5.0·듬성 열 추가를 거절한다. 출처 SHA도 필수다. 자동 입장 관문 pending은 그대로이므로 이 변경은 E1F 기동 허가가 아니다.

## 확인됨

- CUDA 숨김 isaac311, 지정 CPU 10파일: `144 passed in 16.20s`.
- 답 아는 열 네 개: A 연속 두 열·A 징검돌·B 계단. 상한5와6 각각 노출 `[1,1,0,0]`, 상한 `[cap,cap,0,0]`을 얻었다.
- 위 입력은 현재 소비자와 **PR652 2a6a09658848aa36e3dd10cbbb3a9764fbc6ecfd 원문 소비자**를 각각 실행했다. PR652 원문은 임시 프로세스에서 불러왔고 운영 소스는 바꾸지 않았다.
- 제거본: 상속 상한 대조 제거 `6 failed, 4 passed`, 출처 SHA 대조 제거 `1 failed, 9 passed`. 모두 `DID NOT RAISE`로 목표 결함을 검출했다.
- E1F 및 approval pin 밖의 계획/승인 객체는 부모 20b84472와 같음을 직접 대조했다.
- 첫 시험 중 YAML 부분 생성의 anchor 이름 충돌과 잘못 남은 한 줄로 파싱 실패가 발생했다. alias 없는 부분 생성으로 고친 뒤 최종 전체 묶음을 재실행했다.

원자료: `/home/jay/mai/tmp/verifier-lx/e1f-exposure-1111/{cpu-final.log,pr652_probe.py,pr652.json,mutations.py,mutations.json}`. 승인 SHA `3309fe8c77c655e8d21a43204efefab35b295cf3e645ac39660a8abc79f71466`, plan SHA `ea32ceae03c0ec2604eace2ccaca6dd6a36df67a058438821e9dcf1b7e674606`.

## 남은 경계

실제 E1 종료 상한 및 출처 영수증은 아직 없다. 그 값과 기존 부모·landing 메시·깃발 기준선 증거를 채운 뒤 재고정해야 한다. 단계 고유 관문과 학습 runtime 연결은 각 담당의 별도 PR 범위다. 도는 E1 고정 사본에는 쓰지 않았다. PR658 위 후속이며 팀장 승인 전 병합 보류 조건을 이어받는다. Refs #555.
