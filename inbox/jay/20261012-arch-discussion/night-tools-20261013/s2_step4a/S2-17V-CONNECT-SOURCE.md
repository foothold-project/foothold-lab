> 분류: A/정책학습
> 작성: Codex Worker · 2026-10-15
> 근거: Isaac Lab 설치 소스 정적 읽기 · VERIFY-astra-17v.md 2절 · REPORT-s2-step3.md
> 요지: 3단계 미확인 호출 여섯을 실제 설치 소스와 대조하고 런타임 미확인을 분리한다
> 상태: 정적 대조 완료 · Isaac 실행 전 · GPU 미확인

# S2 17v 접속 호출 정적 대조

설치 소스 기준 루트: `C:/isaac/IsaacLab/source/isaaclab/isaaclab/`. 아래 줄 번호는 이 작업의 로컬 설치본이다. 호출이 소스에 있다는 것과 실제 E1 환경에서 원하는 값이 나왔다는 것은 별개다.

| 항목 | 정적 확인 근거 | 구현과 남은 확인 |
|---|---|---|
| 1 · 환경 원점·terrain type/level | `scene/interactive_scene.py:367~375`의 `scene.env_origins`, `scene.terrain`; `terrains/terrain_importer.py:335~353`의 `terrain_types`, `terrain_levels`, `env_origins` | `s2_connect_diag_17v.py`가 읽음. 8환경 0/1,2/3,4/5,6/7 배정은 실제 캡처 후 검사. 학습에서도 난이도·명령 curriculum 배정의 실측은 미확인. |
| 2 · RayCaster 갱신 세대 | `sensors/sensor_base.py:105~122,169~192,354~363`의 lazy data/update, `sensors/ray_caster/ray_caster.py:110~114,294~305`의 실제 private update와 raycast | 공개 generation accessor 없음. `s2_sensor_tracker_17v.py`가 private `_update_buffers_impl` 호출을 감싸 env별 세대와 `common_step_counter`를 기록. 설치판 의존 사본이며 실제 후킹 시점·reset 전후 갱신은 미확인. |
| 3 · Isaac·Kit·driver 판 | `utils/version.py:15~47`의 `get_isaac_sim_version()`은 `isaacsim.core.version.get_version()`을 사용. Python의 `torch.__version__`도 읽을 수 있음 | Isaac 판 호출은 찾음. Kit 판·driver 판의 이 설치판에서 검증된 호출은 못 찾음. 결과 metadata는 값을 꾸미지 않고 HOLD. `pynvml.nvmlSystemGetDriverVersion()`은 후보 호출이지만 실측 미확인. |
| 4 · 환경 전체 복원 | `scene/interactive_scene.py:567~652`의 `get_state()`는 articulation/rigid/deformable 자산 상태를 모음. `envs/manager_based_rl_env.py:181~241`은 물리·reward·reset·obs 진행 | 물리 solver·terrain curriculum·명령 generator·센서 내부 상태·CUDA RNG까지 한 번에 복원하는 API 근거 없음. `runner.load`는 지원하지 않음. 증분은 같은 learner 프로세스 barrier에서만 허용하는 계약. |
| 5 · 조우 이벤트·collision mesh | `sensors/ray_caster/ray_caster.py:162~208`은 한 mesh prim을 읽어 vertices/faces/world transform을 Warp mesh 캐시에 넣고 plane을 특수 처리. `:294~305`는 그 캐시로 raycast. `sensors/contact_sensor/contact_sensor.py:105,170,373~390`은 몸체별 접촉 force 접근 | mesh 원자료 접근 경로는 찾음. 접근선/완료선/추락·사건 ID를 제공하는 내장 API는 못 찾음. 별도 geometry event extractor와 collision mesh 대조 구현·실측 전까지 `encounters_verified=false`, 진단 `mesh_collision_verified=false`. |
| 6 · 단일 AppLauncher 안 순차 make/close | `envs/manager_based_rl_env.py:307`의 `close()`와 `scene/interactive_scene.py`의 초기화·reset은 있음 | 순차 다중 `gym.make/close`가 같은 AppLauncher에서 안전하다는 정적 증거 없음. 17v 사본은 한 8환경 장면에서 네 지형을 동시에 배치. 반복 scene 생성은 사용하지 않음. 실제 close 상태는 미확인. |

추가로 `isaaclab_rl/rsl_rl/vecenv_wrapper.py:138~164`는 `reset` 관측과 `step`의 `dones=terminated|truncated`를 반환하고 무한 horizon 설정일 때 `extras['time_outs']=truncated`를 넣는다. E1 설정이 무한 horizon인지는 현장 구성에서 다시 대조한다. `assets/articulation/articulation.py:399`는 `write_root_pose_to_sim`을 제공하며, `scene/interactive_scene.py:443~463`은 일부 env reset을 지원한다. 64/128/192 개입은 실제 캡처의 독립 영수증이 있어야 통과한다.

진단 코드의 mesh provenance와 고정 자세 구간은 현재 완성되지 않았다. `s2_connect_check_17v.py`는 필요한 출처 값이 없으면 HOLD한다. 합성 정답표의 8×256 PASS를 라이브 접속 PASS로 전하지 않는다.
