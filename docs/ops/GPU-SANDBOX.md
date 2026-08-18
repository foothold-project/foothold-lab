# 외부 GPU 샌드박스 (V100 / KubeSphere)

> 작성 2026-08-13 · 근거: 배포받은 «V100 GPU 테스트 가이드 v2» (23쪽, 작성 유은호)
> 상태: **배정 완료 (2026-08-14)**. GIST 에서 계정 발급.
> ★ **계정 ID·비밀번호는 이 저장소에 적지 않는다.** #foothold-resource 채널에 있다.

## 1. 제공 규모 `확인됨`

| 항목 | 값 |
|---|---|
| 접속 | `http://210.125.70.71:30880` (KubeSphere 웹 콘솔) |
| GPU | **V100 24장** (컨테이너 1개당 **최대 8장**) |
| CPU · Memory | 제한 없음 |
| Storage (PVC) | **최대 4TiB** (4095Gi). Storage Class = `sandbox-container` |
| PVC Limit | 호스트 디스크 1Ti |
| 컨테이너 | Docker Hub 이미지 임의 사용 (예: `nvidia/cuda:11.6.2-devel-ubuntu20.04`) |
| 외부 접속 | NodePort. 공인 IP 는 **모든 컨테이너 공통(210.125.70.71)**, 포트로만 구분 |

## 2. ★ 우리 스택과의 결정적 제약

**Isaac Sim 은 이 샌드박스에서 돌지 않는다.** V100(Volta)에는 RT 코어가 없고,
NVIDIA 공식 요구사항이 *"GPUs without RT Cores are not supported"* 이다.
헤드리스 우회도 NVIDIA 직원들이 일관되게 부정했다.
근거와 출처는 [클라우드 GPU 조사](../research/cloud-gpu-options.md) §1 참조. `확인됨`

그래서 역할을 나눈다.

| 어디서 | 무엇을 |
|---|---|
| **로컬 워크스테이션 (RTX 5080)** | Isaac Sim/Lab 강화학습, Path Tracing 렌더 |
| **V100 샌드박스** | 대규모 병렬 평가(MuJoCo/MJX), 정책 증류, 3DGS 지형 재구성, ONNX 변환·추론 검증 |

V100 은 RT 코어가 없을 뿐 순수 CUDA 연산에는 강하다(FP32 15.7 TFLOPS · HBM2).
위 네 가지는 전부 레이트레이싱을 쓰지 않으므로 오히려 이쪽이 적합하다.

## 3. 운영 시 반드시 지킬 것 `확인됨`

- **데이터는 마운트한 PVC 에만 둔다.** 컨테이너 재시작 시 볼륨 밖 데이터는 복구 불가(가이드 15쪽).
- 팀 공유 데이터셋 볼륨은 **ReadWriteMany** 로 생성한다(가이드 9쪽).
- 컨테이너는 `command: ["bash","-c","sleep infinity"]` 로 PID 1 을 잡아야 죽지 않는다(16쪽).
- GPU 를 할당하면 노드 선택은 불필요하다. 스케줄러가 자동 배정한다(16쪽).
- SSH 는 컨테이너 내부 22번을 Service(NodePort)로 열어 외부 포트로 접속한다(20~22쪽).

## 4. 접속 조건

교육장 **공인 IP 등록**이 선행되어야 한다. 학원 네트워크는 NAT 이므로
공인 IP 하나로 팀원 전원이 접속한다. 학원 회선이 바뀌면 재등록이 필요하다.
개인 테더링·자택 IP 는 등록되지 않는다.

## 5. 신청 내역 (2026-08-13 제출)

| 항목 | 신청값 | 근거 |
|---|---|---|
| GPU | 상시 8장, 병렬 실험 기간 **최대 16장**(컨테이너 2개 × 8장) | 컨테이너당 8장이 상한이므로 컨테이너를 나눠 요청. 평가·증류·3DGS 세 갈래 동시 진행 |
| Storage | **총 2Ti** (공유 ReadWriteMany 1.5Ti + 개인 0.5Ti) | 상한 4TiB 의 절반. 평가 로그·체크포인트·3DGS 원본·시각 자료 |
| CPU / Memory | 컨테이너당 32코어 · 128GB | 문서상 제한 없음. MuJoCo 롤아웃은 CPU 병렬 비중이 높다 |
| 기간 | 2026-08 중순 ~ 12 중순 (최종 발표까지) | 과정 공식 일정 |
| 접속 IP | 교육장 공인 IP 1개 등록 | 학원은 NAT 이므로 IP 하나로 팀원 전원 접속 |

신청서에 적은 용도 네 가지: **평가 대량 롤아웃 · 정책 증류 · sim-to-sim 교차 검증 · 3DGS 지형 재구성.**
전부 레이트레이싱을 쓰지 않는 작업이라 V100 에 맞다(§2 참조).

### 배정 후 할 일

1. 공유 볼륨 생성 (`sandbox-container` · **ReadWriteMany** · 데이터셋용)
2. 컨테이너 생성 시 `command: ["bash","-c","sleep infinity"]` 확인
3. SSH Service(NodePort) 개설 후 팀원에게 외부 포트 안내 (계정·포트는 #foothold-resource)
4. 첫 작업: 평가 파이프라인을 이 환경에서 재현해 로컬 결과와 대조

## 6. 쓰는 법 (배정 후)

### 6-1. 팀이 계정 하나를 공유한다: 이것부터 합의

발급된 계정은 **하나**다. 5명이 같은 워크스페이스에 들어간다.
남의 컨테이너를 지우거나 GPU 를 다 물고 있으면 서로 막힌다. inbox 폴더와 같은 원칙을 쓴다.

| 규칙 | 왜 |
|---|---|
| 컨테이너·볼륨 이름 앞에 **자기 이름**을 붙인다 (`lim-eval`, `meang-terrain`) | 누구 것인지 이름만 봐도 안다 |
| **남의 것은 건드리지 않는다.** 지우기 전에 채널에 묻는다 | 실행 중인 학습이 날아간다 |
| GPU 를 다 쓰면 **컨테이너를 지운다**(볼륨은 남는다) | 24장은 다른 팀과도 나눠 쓸 수 있다 |
| 팀 공유 데이터셋은 **공유 볼륨 하나**에 (ReadWriteMany) | 같은 데이터를 5벌 복사하지 않는다 |

### 6-2. 처음 한 번

1. **교육장 네트워크**에서 브라우저로 콘솔 접속 (주소·계정은 #foothold-resource)
2. 첫 로그인 시 **패스워드 변경** (가이드 4쪽). 변경한 값도 채널에만 남긴다
3. `Workspace Management` → `virl` → `Projects` → `virl` 로 들어가면 할당 자원이 보인다

### 6-3. 작업 공간 만들기 (가이드 9~22쪽 요약)

```
① 볼륨          Storage → Persistent Volume Claims → Create
                Storage Class = sandbox-container
                공유 데이터셋이면 Access Mode 에 ReadWriteMany 추가
② 컨테이너      Application Workloads → Workloads → Create → Add Container
                Docker Hub 이미지 입력 · GPU Limit 입력(컨테이너당 최대 8)
                Port Settings: TCP · Container Port 22
                Storage Settings 에서 ①의 볼륨을 마운트 (예: /data)
③ 죽지 않게     Edit YAML → command: ["bash","-c","sleep infinity"]
④ SSH 설치      Pods → Terminal 아이콘 →
                apt update && apt install openssh-server -y
                mkdir /run/sshd && /usr/sbin/sshd
⑤ 포트 개방     Services → Create → Specify Workload
                Container Port 22 · Service Port 22 · Access Mode = NodePort
                생성 후 External Access 의 외부 포트 확인
⑥ 접속          ssh -p <외부포트> root@<콘솔호스트>
```

**GPU 를 할당하면 노드 선택은 하지 않는다.** 스케줄러가 알아서 배정한다(가이드 16쪽).

### 6-4. 붙자마자 확인할 것

```bash
nvidia-smi                      # V100 이 할당 수만큼 보이는가
df -h /data                     # 마운트한 볼륨이 붙었는가
python -c "import torch; print(torch.__version__, torch.cuda.is_available(),   torch.cuda.get_device_name(0), torch.cuda.get_device_capability(0))"
```

마지막 줄이 **`(7, 0)`** 을 찍으면 정상이다(V100 = Volta = sm_70).
**우리 워크스테이션 조합(torch 2.7.0+cu128)이 sm_70 에서도 도는지는 아직 확인 안 됐다** `미확인`.
안 되면 컨테이너 이미지의 torch 버전을 낮추면 된다. **로컬 학습 환경과 같게 맞출 필요는 없다.**
여기서 도는 것은 평가·증류·3DGS 이지 Isaac Sim 이 아니기 때문이다(§2).

### 6-5. 첫 작업

**평가 파이프라인을 이 환경에서 재현해 로컬 결과와 대조한다.**
같은 정책·같은 시드로 돌려 통과율이 같게 나오면, 이 환경을 믿고 대량 롤아웃에 쓸 수 있다.
숫자가 다르면 그 차이의 원인을 찾는 것이 먼저다. 믿을 수 없는 환경에서 6,000회를 돌려봐야 소용없다.
