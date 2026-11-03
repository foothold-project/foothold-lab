# EX-41 m6450 밀기 영상 세 모드와 C층 dispatcher 인계

> 분류: A/평가
> 작성: 오흥재 · scripter · 2026-11-04
> 근거: EX-41 model_450.pt, `a_push_m6450_dual/summary.json`, 세 모드 영수증과 MP4 SHA256, C층 고정 계획과 실행 코드
> 요지: 밀기 두 번을 같은 시드와 지형에서 세 지도 모드로 촬영했고, C층 자체 반복기는 멈춘 채 한 칸 실행 계약을 인계한다.
> 상태: 실측 완료 · 영상은 시연 자료이며 독립 평가 판정이 아님

## 촬영 결과

고정 촬영 코드 HEAD `70ca7a4be308d161e023b2bf311ba08bc392e6bc`, 저장본 SHA256 `c5314db17791c8e09539efb8977af7d1d5b66e5cf73c42246f01d418516f85a0`. 세 편 모두 pyramid_stairs L0, env 0, seed 42, 전진 명령 1.0 m/s, 같은 group ID `c61e127e43474c75e61c1238844a1cb0bea8ae80ac3d672dc5b68adc26f1afd3`를 쓴다. 시연용 외력은 t=2.0 s에 world +x 방향 1.5 m/s, t=4.0 s에 같은 방향 2.0 m/s로 적용됐다. 2.0 m/s는 학습 DR 범위 밖의 시연 처치이므로 학습 평가값으로 해석하지 않는다.

| 지도 모드 | 영상 | SHA256 | 프레임 · 감사 | 밀기별 회복 시간 중앙값 |
|---|---|---|---|---|
| 정답 `eval_gt` | `D:/mai-tmp/scripter/a_push_m6450_dual/attempts/c61e127e43474c75e61c1238844a1cb0bea8ae80ac3d672dc5b68adc26f1afd3/eval_gt/styled.mp4` | `203956071a5524a72ac4f40eb036e877b845a4a24963449b696638f5ebb2c599` | 150 · PASS | 1.11 s · 1.22 s |
| 복원 `eval_pred` | `D:/mai-tmp/scripter/a_push_m6450_dual/attempts/c61e127e43474c75e61c1238844a1cb0bea8ae80ac3d672dc5b68adc26f1afd3/eval_pred/styled.mp4` | `9440ab76d8b999408ea3c244b622a9b3a1df1e58eac5c4d1e0a07c4fee345680` | 150 · PASS | 1.12 s · 1.34 s |
| 지도 끔 `probe_prop_only` | `D:/mai-tmp/scripter/a_push_m6450_dual/attempts/c61e127e43474c75e61c1238844a1cb0bea8ae80ac3d672dc5b68adc26f1afd3/probe_prop_only/styled.mp4` | `c5abd22f37e5a646a43f18c0ff25f9a75569268d6864cbed5e42de2e769bd19d` | 150 · PASS | 1.26 s · 1.18 s |

독립 `Get-FileHash`로 세 영상의 SHA256을 영수증과 대조해 모두 일치했다. 각 영수증의 `dr_recovery_by_event`는 두 건이다. `summary.json`의 모드별 감사도 모두 PASS다. 앞·중·뒤 정지 화면은 각각 `D:/mai-tmp/scripter/a_push_m6450_dual/before_1p8s.png`, `push_2p08s.png`, `after_recovery_3p4s.png`다. 밀기 중 PUSH 상자와 몸통 화살표, 회복 창 뒤 범례 복귀를 화면으로 확인했다. 원자료와 요약 영수증은 `D:/mai-tmp/scripter/a_push_m6450_dual/`에 있다.

## C층 dispatcher 인계

C층 자체 반복기는 현재 중단돼 있고 `out/c_layer.lock`도 없다. 이를 다시 띄우지 않는다. 2시드 고정 계획의 남은 칸은 dispatcher가 `run-next`로 한 칸씩 맡는다. 정확한 PowerShell argv, 완료 판정 파일, 잠금·우선순위 규칙은 `D:/mai-tmp/scripter/C-LAYER-RUN-ONE-ARGV.md`에 기록했다. 입력 계획 SHA256은 `481d3997aa38ccf648fe9adc4c5ebe01d0d92b439f51a2aa9fc1c7a6b0cb1b1e`, manifest SHA256은 `25dc9f7ee32712d039d6d198c6e8df864ac8052ae3f77cdfb35d4b8ce65ff411`이다.

CPU 한정 시험은 2시드 계획의 실패 예산·기술 실패 분리·P1 양보 등 좁은 묶음 6건 통과였다. 실제 고정 큐에서는 계획 갱신 뒤 한 칸이 촬영 성공했고 칸 경계에서 중단됐다. dispatcher 연결 자체는 아직 미실행이므로 그 결과는 미확인이다.
