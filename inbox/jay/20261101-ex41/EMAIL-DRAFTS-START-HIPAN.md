> 분류: 외부 연락 초안 (발송 전)
> 작성: lead · 2026-11-02 16:3x
> 근거: START arXiv 2512.13153 (Ruiqi Yu 외, Qiuguo Zhu 연구실, RA-L 2025) · HiPAN arXiv 2604.26504 (Jeil Jeong 외, KAIST SGVR Lab Sung-eui Yoon 교수, RA-L 2026) · 팀장 11/02 16:3x 「저자에게 이메일 시도」
> 요지: 두 논문 저자에게 학습 코드 · 가중치 · 하이퍼파라미터 공유를 요청하는 초안. 발송은 팀장이 직접(또는 팀장이 건별 승인)
> 상태: 초안. 받는 주소는 논문 PDF 의 교신 저자 주소를 팀장이 확인해 넣을 것(미확인)

# 저자 연락 초안

## 공통 원칙

- 우리가 무엇을 하는지(교육 과정 프로젝트, Unitree Go2, Isaac Lab) 와 무엇을 이미 재구현했는지를 먼저 밝힌다. 「처음부터 다 달라」 가 아니라 「재구현과 대조할 수 있게」 를 요청한다.
- 받은 코드 · 가중치는 공개 저장소에 올리지 않는다(저자 허락 범위 안에서만). 결과에 인용 · 감사 표기.
- 가장 받고 싶은 순서: ① 학습 설정 값(보상 가중 · 커리큘럼 · 네트워크 폭 · AdaSmpl 세부) ② 지형 생성 코드 ③ 학습 코드 ④ 가중치.

## START 저자께 (영문)

Subject: Request regarding START (arXiv 2512.13153): reproduction on Unitree Go2

Dear Dr. Yu and Prof. Zhu,

We are a student research team in Korea building a quadruped locomotion stack on Unitree Go2 with Isaac Lab. Your START paper is the core reference for our perception design: we re-implemented TR-Net, the I-E Estimator and AdaSmpl from the paper and your earlier work (2409.15692), and we are now training on stairs and rough terrain before moving to sparse footholds.

Several details we could not pin down from the paper make it hard to know whether our reproduction is faithful, for example the exact AdaSmpl statistics window, the reward weights for the foot-edge term, the network widths of the map encoder and attention layers, and the terrain curriculum schedule (the p_max formula in II-D3 appears to return a constant).

Would you be willing to share any of the following, under whatever terms you prefer: the training configuration, the terrain generation code, the training code, or trained weights? We would use them only to validate our re-implementation, would not redistribute them, and would cite and acknowledge your work in any report.

Thank you for publishing this work.

Best regards,
(이름 · 소속 · 연락처, 팀장)

## HiPAN 저자께 (한국어, KAIST SGVR)

제목: HiPAN(arXiv 2604.26504) 관련 문의: Unitree Go2 재현

정제일 연구원님, 윤성의 교수님께

안녕하십니까. 저희는 Unitree Go2 와 Isaac Lab 으로 4족 보행과 상위 경로 계획을 연구하는 학생 프로젝트 팀입니다. HiPAN 의 「상위 정책이 평면 속도와 몸 자세를 명령하고 하위 제어기가 수행하는」 구조를 저희 설계의 상위 층 기준으로 삼고 있으며, 하위 보행 정책에 몸 높이 · roll 자세 명령 칸을 이미 넣어 학습을 준비하고 있습니다.

논문만으로 확정하기 어려운 부분이 있어 여쭙습니다. 자세 명령 범위와 하위 제어기 보상, Path-Guided Curriculum 의 경로 생성 방식, 상위 정책의 관측 · 행동 정의입니다.

가능하시다면 학습 설정, 학습 코드, 또는 학습된 가중치 가운데 공유 가능한 것을 받을 수 있을지 문의드립니다. 받은 자료는 재현 검증에만 쓰고 재배포하지 않으며, 결과물에 인용과 감사를 밝히겠습니다. 정해 주시는 조건을 따르겠습니다.

감사합니다.
(이름 · 소속 · 연락처, 팀장)
