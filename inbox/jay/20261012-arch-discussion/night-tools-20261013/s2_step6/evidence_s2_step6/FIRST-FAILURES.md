# S2 step6 CPU 시험의 첫 실패
> 분류: A/정책학습
> 작성: Codex Worker · 2026-10-15
> 근거: test_s2_step6_execution.py 첫 CPU 실행 출력 · 수정 후 최종 묶음
> 요지: checkpoint 재적재 시험의 첫 실패와 수정을 보존한다.
> 상태: 첫 실패 보존 · 수정 후 재검증됨

첫 `test_s2_step6_execution.py` 실행은 실제 E1 CPU PPO arm A 1회 업데이트와 양의 gradient norm, 가중치 변화까지 진행했으나 `roundtrip_policy()`에서 `copy.deepcopy(policy)`가 `RuntimeError: Only Tensors created explicitly by the user (graph leaves) support the deepcopy protocol`로 실패했다. 이때 결과는 `HOLD`, 실행된 update는 1, `roundtrip`은 null이었다.

수정은 모델 객체 복제를 없애고, 저장된 체크포인트를 같은 정책에 다시 적재해 확인하는 방식이다. 저장 뒤 actor bias를 의도적으로 바꾸어 고정 입력의 출력이 달라지는 것을 먼저 확인하고, `load_state_dict()` 후 같은 입력의 출력이 비트 동일해야 통과한다. 그 뒤 A 1회, B 2회 정상 시험과 전체 새 run-id를 통과했다. 실패를 실제 GPU/Isaac 결과로 해석하지 않는다.
