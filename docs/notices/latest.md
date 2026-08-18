📢 **GPU 서버 계정이 나왔습니다** (2026-08-14)

GIST 에서 GPU 자원을 배정받았습니다. **오늘부터 씁니다.**

**계정은 #foothold-resource 채널에 있습니다.** 여기(공지)와 저장소에는 적지 않습니다.
첫 로그인 때 비밀번호를 바꾸게 되는데, **바꾼 값도 그 채널에만** 남겨 주세요.

**받은 자원**
```
GPU        V100 24장 풀 (컨테이너 1개당 최대 8장)
CPU/메모리  제한 없음
스토리지    최대 4TiB
```

**⚠️ 계정이 하나입니다. 5명이 같이 씁니다**

이게 제일 중요합니다. 남의 컨테이너를 지우거나 GPU 를 다 물고 있으면 서로 막힙니다.
inbox 폴더와 같은 원칙으로 갑니다.

- 컨테이너·볼륨 이름 앞에 **자기 이름**을 붙입니다 (`lim-eval`, `meang-terrain`)
- **남의 것은 건드리지 않습니다.** 지워야 할 것 같으면 채널에 먼저 물어보세요
- 다 쓰면 **컨테이너를 지웁니다.** 볼륨은 남으니 데이터는 안 없어집니다
- 팀 공유 데이터셋은 **공유 볼륨 하나**에 (ReadWriteMany)

**⚠️ 데이터는 반드시 마운트한 볼륨에**

컨테이너가 재시작되면 **볼륨 밖의 것은 복구되지 않습니다.** 홈 디렉터리에 두지 마세요.

**접속 조건**

**교육장 네트워크에서만 됩니다.** 공인 IP 를 등록하는 방식이라 자택·테더링은 막힙니다.
학원 회선이 바뀌면 재등록이 필요하니, 갑자기 안 되면 그것부터 의심하세요.

**쓰는 순서 (요약)**
```
① 볼륨 만들기      Storage → PVC → Create (Storage Class: sandbox-container)
② 컨테이너 만들기   Workloads → Create → Docker Hub 이미지 + GPU 수 + Port 22
③ 안 죽게 하기      Edit YAML → command: ["bash","-c","sleep infinity"]
④ SSH 설치         Terminal → apt install openssh-server -y → /usr/sbin/sshd
⑤ 포트 열기        Services → Create → NodePort → 외부 포트 확인
⑥ 접속             ssh -p <외부포트> root@<호스트>
```
자세한 절차와 함정은 `foothold-lab/docs/ops/GPU-SANDBOX.md` §6 에 정리했습니다.

**붙자마자 이것부터**
```bash
nvidia-smi
python -c "import torch; print(torch.cuda.get_device_capability(0))"
```
`(7, 0)` 이 나오면 정상입니다. V100 은 Volta 세대라 그렇습니다.

**여기서 무엇을 하나**

이 서버는 **평가 대량 롤아웃 · 정책 증류 · sim2sim 교차 검증 · 3DGS** 용입니다.
Isaac Sim 학습은 여기서 돌리지 않습니다. 이유는 웹에 정리해 두었습니다:
<https://foothold-project.vercel.app/research-compute-resources.html>

**첫 작업**은 평가 파이프라인을 여기서 재현해 기존 결과와 대조하는 것입니다.
숫자가 같게 나와야 이 환경을 믿고 대량으로 돌릴 수 있습니다.

질문은 #foothold-general 로.
