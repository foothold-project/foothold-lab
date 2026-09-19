# FOOTHOLD A트랙 제작 설계 · 감독 승인용

> 분류: 계획
> 작성: 제작 설계 워커 · 2026-09-14 00:00
> 근거: brief.txt·brand-brief.txt 전체와 코디네이터의 감독 정정. 실제 프리비즈·생성 영상·카메라 데이터는 열람하지 않음
> 요지: 첫 디딤에서 대군의 안정된 정지를 거쳐 FOOTHOLD와 다음 걸음으로 이어지는 런칭 영상. 전체 길이는 실제 편집으로 결정
> 상태: 제작 설계 독립 검토 통과. 감독 승인용 제안이며 실물 소재 연결은 미확인
> 판: v1.2

**판정: 이전 안을 그대로 통과시키지는 않는다. 큰 서사는 유지하고, 정지 직전의 발 타이밍·폭풍의 공간 규모·카메라 방향 전환·참조 권한을 수정한다.** 영화의 절정은 폭풍의 크기가 아니라 폭풍을 지난 뒤에도 대열이 자기 발로 정확히 서는 순간이다. 상승은 두 번째 절정을 새로 만드는 장면이 아니라, 방금 본 정지의 의미를 FOOTHOLD라는 이름으로 완성하는 장면이다.

16의 2.8초, 17~18의 6.4초, 8192개체는 `기존 소재에 관한 브리프 제공값`이다. 최신 감독 정정에 따라 컷별 초수는 확정값이 아니라 편집 시작값으로 다룬다. 16의 후퇴 연출과 17~18의 저속에서 고속으로 이어지는 상승·로고 크기 매칭을 기준으로 삼되 실제 연결을 보고 감독이 재타이밍한다. 14→655 높이는 이전 안의 서술을 인용한 값이며 단위·실제 경로는 `미확인`이다. 나머지 프레임·화각·후보 수도 모두 `제안`이지 실측이나 모델 성공률이 아니다. 최신 브랜드 브리프의 기존 엔딩은 12초이며 디자인·폰트·크기·문구·시퀀스를 그대로 보존한다. 17과 18은 하나의 상승 소재 내부의 서사 구간으로 다룬다.

**브랜드 기준:** FOOTHOLD는 ‘Unitree Go2 미경험 험지 적응 시뮬레이션 및 실기 자율주행 프로젝트’다. 정식 락업은 심볼·FOOTHOLD·Terrain-Adaptive Locomotion Policy다. 브랜드 브리프가 설명하는 강화학습 보행 정책이 주인공이며, 로봇 한 대는 그 정책이 땅과 만나는 접점, 수천 대는 반복 학습·검증을 나타내는 규모다. 이 런칭 영상의 군집·정지는 상징 표현이며 실제 미경험 지형 성공률이나 실기 검증 결과를 입증하는 영상으로 제시하지 않는다.

서사 축은 **불확실 → 첫걸음 → 전진·규모 → 폭풍 관통 → 멈춤, 발 디딜 곳을 확보함 → FOOTHOLD → 다음 걸음**이다. 정지는 임무 포기가 아니라 다음 걸음을 가능하게 하는 안정된 지지다. 멈춘 로봇을 다시 걷게 하거나 로고를 재배열하지 않아도, 기존 엔딩의 FIND THE NEXT STEP과 ‘불확실한 지형에서도, 다음 걸음을 이어갑니다’가 그 의미를 이어받는다. 톤은 냉정·정밀·묵직, 실제 먼지·모래·돌의 물성이다. 군사적 위압·승전·무기·과장된 SF를 추가하지 않는다.

다크 베이스와 주황 액센트, 다크 위 흰 워드마크를 유지한다. 정본 SVG는 브랜드 브리프에 명시된 `foothold-brand/assets/logo/v1`의 승인 자산을 그대로 인계받아 사용하며 다시 그리지 않는다. 실제 자산의 바이트 동일성은 향후 인계·합성 단계에서 확인한다. 기존 12초 엔딩의 ‘찢김 → 워드마크 → 하얀 선 → FIND THE NEXT STEP → 문구 → 스택 락업’과 중앙 주황 10m 선 모티프를 보존한다. 새 텍스트·새 정지 이후 동작을 추가하지 않는다.

요청 범위는 글로 된 제작 설계다. 키비주얼의 **제작 명세**까지 제시하며 이미지·영상은 생성하지 않았다. 임시 산출물 외에 저장소 파일을 수정하거나 외부 게시·이슈·PR을 만들지 않는다. 도구 명칭과 태깅 관례는 브리프의 제공 조건을 따른다. 현 계정의 모델 버전·입력 개수·지원 길이는 확인하지 않았으므로 아래 문장은 프롬프트 원고이며 API 호출 형식이나 성공 보장이 아니다.

## A. 이전 12~17안 재검증과 확정할 수정

| 쟁점 | 판정 | 이유와 수정 |
|---|---|---|
| 전진·통과·감속·정지·후퇴·상승 | 통과 | 각 운동이 다음 사건을 만든다. 14~15b를 한 번의 정지로 묶으면 장관과 브랜드 상징이 연결된다. |
| 12와 13에서 같은 폭풍 통과 | 조건부 통과 | 동일한 통로·바람·경계를 유지하는 것은 맞다. 다만 거대한 폭풍 전체를 1.6초 만에 관통한 것처럼 설계하면 공간이 납작해진다. 큰 먼지장의 유한한 전방 돌출 띠를 실제로 통과한다. |
| 13 후반부터 카메라 감속 | 통과 | 출구와 정지 준비를 읽을 시간이 생긴다. 단, 카메라 감속과 로봇 감속을 구별한다. 로봇의 짧아지는 보폭·지면 대비 이동으로 실제 감속을 확인한다. |
| 14 마지막부터 같은 발이 내려오고 15 전체를 지나 15b에서 접지 | 수정 필수 | 이전 시간을 그대로 더하면 같은 발이 과도하게 오래 공중에 머문다. 14는 감속 중인 몸통과 이전 지지의 인계로 끝낸다. 마지막 오른앞발의 짧은 스윙은 15의 마지막 3프레임에서 시작하고 15b F6에 한 번 접지한다. |
| 15의 착착, 15b의 쿵 | 수정 후 통과 | 착착은 중간 지지와 인접 로봇의 접지, 쿵은 마지막 집단 지지의 마무리다. 똑같은 착지를 두 앵글로 재생하지 않는다. 15에서 이미 완전 정지한 테이크는 잘라 쓰거나 배제한다. |
| 여러 로봇의 접지 시차 2~3프레임 | 범위 축소 | 이를 8192대 전체의 물리적 동시성 조건으로 삼지 않는다. 가까이 보이는 소수의 마지막 지지를 좁은 시간창에 정렬하고, 원거리 대열은 이미 안정되어 있거나 정지를 마치는 상태로 합성한다. 사족 전체가 동시에 뛰어내리는 장면은 불합격이다. |
| 15b 0.8초 안의 정지 체감 | 수정 후 통과 | F6 접지, F7~11 하중 흡수, F12~23 안정된 정지로 재배분한다. 완전히 안정된 상태가 12프레임, 0.4초 보인다. 첫발과 달리 여기서는 다시 발을 들지 않는다. |
| 14 후방 구도에서 16 정면 구도로 넘어갈 가능성 | 기존안 불충분 | 발 타이트만으로 방향이 저절로 해결되지는 않는다. 실제 16이 정면이면 15에서 머리 방향과 고정 지형 표식이 함께 보이는 측면을 먼저 제시하고 15b를 그 측면의 타이트로 잇는다. 이후 16은 같은 사건을 다른 관측점에서 보는 명시적 컷이다. 카메라가 연속 회전했다고 주장하지 않는다. |
| 16 후퇴 연출과 2.8초 시작값 | 통과, 객체 상태 점검 필요 | 승인된 후퇴 감각·경로를 기준으로 실제 연결에서 재타이밍한다. 소재에 보행이 남아 있으면 카메라 승인과 보행 승인을 분리한다. 같은 카메라의 정지 대군 레이어가 필요하다. 보행까지 video_edit로 잠그면 15b의 의미가 취소된다. |
| 16→17 실제 연속성 | 미확인 | 영상을 보지 않고 통과 판정할 수 없다. 위치뿐 아니라 화면 내 지형·로봇의 이동 방향과 속도, 밀도, 축척, 렌즈, 높이, 피치가 이어지는지 실제 경계 프레임으로 본다. |
| 연결에 0.6초 추가 | 고정 상한 삭제 | 총 길이는 고정이 아니다. 필요한 연결 시간을 실제 경계로 정한다. 0.6초가 모든 높이 차이를 해결하지는 않는다. 우선 기존 핸들에서 접점을 찾고, 불가능하면 연결 경로와 시간을 구체화해 감독에게 보여준다. |
| 8192대에서 로고 형상으로 연속 리빌 | 서사 통과, 제작 방식 강화 | 이미 로고를 이루는 대형의 일부를 16에서 보는 구조가 맞다. 정확한 개체 위치·글자 윤곽은 Isaac 원본·레이어가 담당한다. 자유 생성 후 프롬프트만으로 8192대를 보존하려 하지 않는다. |
| 첫발의 사전 먼지와 마지막 발의 접지 먼지 | 구별 필수 | 03의 사전 먼지는 옆에서 넘어오는 바람·화면 밖 선행 발의 교란이다. 아직 닿지 않은 주인공 발 접점에서 먼지가 솟는 것은 금지한다. 15b의 새 먼지는 접지 직후 접점에서 발생한다. |
| ‘미경험 험지 적응’의 전달 | 보강 필요 | 먼지와 군집만으로는 적응보다 퍼레이드가 먼저 읽힐 수 있다. 03·10의 기존 지형 요철에서 발이 다른 높이에 닿고 몸통이 지나가는 모습을 짧게 읽힌다. 새 절벽·점프·낙상 복구를 삽입하지 않으며 실제 연구 성능의 증거처럼 수치화하지 않는다. |

### 12~14의 공간을 하나로 고정한다

월드 진행축은 +X, 로봇도 +X로 이동한다. 12~14 카메라는 +X를 보고 열린 통로 안을 전진한다. 화면에는 주로 로봇의 등과 후측면이 보인다. 바람의 주성분은 -X이며 약간의 횡성분을 하나 정해 유지한다. 화면에서 먼지가 흐르는 모양은 카메라 방향에 따라 달라지므로 전 컷에 같은 좌우 흐름을 기계적으로 붙이지 않는다.

13에서 가장자리의 가까운 로봇들은 뒤로 빠져나가지만, 연결 기준 로봇 R-A는 카메라 앞에 남는다. 카메라가 R-A까지 추월하면 14에서 같은 로봇을 다시 앞에 두지 않는다. 기준은 R-A, 통로 가장자리의 낮은 지면 돌기 L-A, 반대편 열 R-B다. 실제 보드에서 충돌 없는 통로 폭과 세 기준의 위치를 정한다.

폭풍은 한 장의 불투명 벽이 아니다. 12 첫 화면에 먼 본체와 그 앞의 맑은 지면을 남기고, 가까워진 돌출 먼지 띠를 카메라가 통과한다. 13은 그 유한한 띠 내부, 14는 같은 띠 반대편이다. 진입면과 출구면 사이 두께는 **카메라와 띠의 상대속도를 통과 시간 동안 적분한 이동거리**와 맞아야 한다. 실제 스케일 없이 두께나 속도를 숫자로 확정하지 않는다. 먼 본체는 프레임 밖 측후방으로 이어질 수 있으나 전방을 보는 14 배경에 뒤쪽의 폭풍을 다시 세우지 않는다.

12 마지막 3프레임만 깊게 가린다. 13 내부에는 지면과 가까운 등·어깨가 간헐적으로 읽혀야 한다. 13→14는 다시 화면 전체를 오래 막는 전환 대신 얇은 먼지가 걷히는 중의 운동 연결을 기본으로 한다. **진입은 차단, 내부는 저항, 출구는 시야 회복**으로 세 구간의 인지 기능을 다르게 한다.

### 16·17은 먼저 확인하고, 확인 결과에 따라 두 갈래로 진행한다

실제 16 시작·끝과 17 시작·로고 도달 프레임, 각 경계 앞뒤 최소 6프레임을 확인한다. 30fps가 아니라면 같은 0.2초 길이로 다시 센다. 프레임만으로 월드 위치를 확정할 수 없으면 Isaac 카메라 경로와 원점·단위를 함께 확인한다.

- **경계가 맞는 경우:** 승인된 16과 17~18의 경로와 현재 타이밍을 편집 시작값으로 연결한다. 근경의 크기 감소와 바닥의 흐름이 다음 컷에서 급변하지 않는지 정상속도로 판정한다. 실제 흐름을 본 감독이 최종 길이를 정한다.
- **경계가 맞지 않는 경우:** 먼저 기존 여유 프레임에서 접점을 찾는다. 연결 경로가 필요하면 차이와 필요 시간을 실제로 확인하여 감독에게 보여준다. 총 길이를 맞추기 위해 후퇴·상승 속도를 임의로 늘이거나 줄이지 않는다. 프레임 보간·먼지·디졸브로 공간 오류를 숨기는 것을 기본 해결책으로 삼지 않는다.

이 미확인 항목은 제작 설계의 빈칸을 감춘 것이 아니라, 실물 소스 없이 확정할 수 없는 입력 조건이다. 다른 컷의 키비주얼과 03·15b 시험 생성은 이 검사와 독립적으로 시작할 수 있다.

## B. 01~19 전체 흐름과 시간 배분

**오프닝은 성립한다. 다만 03은 02의 카메라 앞에 대군이 순간 도착하는 장면이 아니라, 멀리 있는 선두의 발밑으로 관측점을 옮긴 인서트여야 한다.** 02와 04는 같은 멀리 떨어진 관측점 A다. 03은 선두 가까이의 관측점 B다. 02→03→04 동안 사건의 시간은 앞으로 가고 카메라 위치만 달라진다. 03 배경에 A에서만 가까이 보이던 큰 바위를 다시 넣으면 이 관계가 무너진다. 지질·광원·진행 방향은 같게 하고 가까운 지면 표식은 다르게 한다.

02는 먼 실루엣을 작게 둔다. 가까운 금속 발소리를 첫 프레임부터 붙이지 않는다. 처음에는 저역의 반복과 희미한 착착을 바람 사이로 듣고, 03에서 음향의 거리를 발밑으로 바꾼다. 이때 첫발은 로봇의 최초 등장뿐 아니라, 추상적인 리듬이 실제 접점으로 확인되는 순간이다. 04로 돌아가면 소리도 다시 원경의 거리감을 갖는다. 04 대군은 렌즈 줌으로 갑자기 커지는 것이 아니라 같은 배경 기준에서 조금 전진한다. ‘조금 더 가까움’을 만들려고 짧은 시간에 지평선에서 전경까지 이동시키지 않는다.

05~11의 위험은 멋있는 행렬 장면이 연속해서 같은 정보를 반복하는 것이다. 시나리오 순서는 유지하되 05는 진입, 06은 횡방향 속도, 07은 Go2의 구조, 08은 통로의 깊이, 09는 가까운 물체의 스침, 10은 지면 대응, 11은 군집의 폭으로 역할을 나눈다. 11의 선회는 대군을 다 보여주는 완전한 탑뷰까지 가지 않는다. 마지막 로고 리빌의 정보는 남겨 둔다.

첫발보다 ‘쿵’을 더 크게 믹스하는 것만으로 결말이 커지지는 않는다. 03에서는 접지 후 몸통이 계속 지나가고, 15b에서는 발과 몸통의 이동이 끝나며 먼지만 남는다. 같은 접지의 시각 언어가 **지나감과 섬**으로 달라지는 것이 두 장면의 관계다. 14의 감속을 충분히 보여주면 정지는 고장·명령 대기·폭풍에 굴복한 정지로 읽힐 가능성이 줄어든다. 16 첫 화면의 대열은 서로 다른 곳에 흩어져 버틴 모습이 아니라, 이미 연결된 방향과 간격을 갖춘 안정된 상태다.

### 편집 예산

다음은 편집 시작값과 권장 범위다. **초수보다 인계받는 행동, 컷하는 순간, 속도 곡선이 먼저다.** 실제 생성물을 앞뒤 컷과 붙여 보고 감독이 다시 길이를 정한다. 30fps 표는 그 첫 조립을 위한 예시이며 실제 마스터 fps를 인계받아 환산한다. 모든 생성 컷은 사용할 구간의 앞뒤에 **각각 최소 0.5초, 가능하면 1.0초의 핸들**을 추가한다. 즉 사용 구간 외에 총 1.0~2.0초의 유효 운동을 확보한다. 지원 출력 길이는 실제 계정에서 확인하고 이 합계 이상을 담을 수 있는 길이로 생성한다.

핸들은 검은 화면·정지 복제·발의 공중 대기가 아니다. 03 앞은 지면·그림자의 시작 전, 뒤는 걸음이 떠난 이후다. 15·15b는 같은 접지를 앞뒤 각도에서 겹쳐 확보하되 최종 편집에서는 한 번만 보여준다. 12·13·14는 같은 통로와 동일 운동이 앞뒤로 계속되어야 한다. 연결 컷끼리는 경계 주변의 같은 사건 시간을 겹쳐 확보하고, 조립할 때 중복 시간을 제거한다. 후반 16·17~18에 핸들이 없으면 원본을 억지로 늘리지 말고 동일한 카메라·배치의 연장 소재가 필요한지 확인한다.

**생성 첫 프레임과 편집 F0은 다르다.** 생성 시작 G0은 편집 F0보다 앞 핸들만큼 이른 사건 상태다. 아래 F절의 ‘시작·중간·끝’은 핸들을 뺀 사용 구간이다. 시작 이미지 기능에는 G0을 넣고, F0은 사용 구간 진입을 고를 검수판 또는 실제 지원되는 중간 시점 참조로만 쓴다. 생성 끝 이미지도 뒤 핸들이 끝난 상태이며, 편집 마지막 프레임과 자동으로 같지 않다.

| 컷 | 앞 핸들 0.5초일 때 생성 G0 | 편집 F0의 위치·상태 |
|---|---|---|
| 03 | 사전 옆먼지·그림자보다 이른 빈 지면 | 생성 0.5초 뒤의 빈 지면. 이후 첫발 사건 시작 |
| 12 | 12의 편집 시작보다 앞선 맑은 접근 상태, 먼 띠·같은 통로 | 생성 0.5초 뒤의 승인된 원거리 접근 구도 |
| 13 분리 생성 | 12 끝보다 약 0.5초 이른 진입 접근 상태. 시작값 예시에서는 12 F57에 해당 | 생성 0.5초 뒤의 12 종료 경계, 13 진입 가림. 12 끝 이미지를 G0으로 잠그지 않음 |
| 15b | 최종 스윙보다 0.4초 이른 정상 지지·감속 상태. 사건 시간은 15 F21에 해당하며 **15b 카메라에서** 다시 구성 | 생성 0.5초 뒤 하강 중인 같은 발. 접지는 그 뒤 0.2초. 하강 이미지를 G0으로 잠그지 않음 |

15b 예시의 생성 시간은 G0 정상 지지, 약 0.4초에 짧은 스윙 시작, 0.5초에 편집 F0, 0.7초에 마지막 접지다. 앞 핸들을 1초로 잡으면 같은 사건을 그만큼 뒤로 옮길 뿐 발 스윙의 시간을 늘이지 않는다. 핸들에는 필요한 이전 지지·감속을 자연스럽게 담는다. ‘한 번 접지’는 지정한 마지막 접지를 중복 연출하지 말라는 뜻이며 핸들 속 실제 이전 보행까지 금지하는 뜻이 아니다.

최신 브랜드 브리프의 **12초 엔딩을 포함한 전체 권장 편집 탐색 범위는 약 44~50초**다. 최초 약 38초는 고정 목표가 아니다. 아래 시작값은 합계 47.0초로 이 범위 안에 있다. 더 짧게 볼 필요가 있으면 연결 컷의 반복 정보부터 줄인 시험 편집을 비교하되 첫 접점·폭풍 접근·정지 체감·기존 12초 엔딩을 숫자 때문에 삭제하지 않는다. 개별 컷 범위의 최소·최대를 모두 동시에 선택한다는 뜻은 아니며 전체 리듬으로 조정한다. 핸들은 최종 러닝타임에 더하지 않는다.

| 컷 | 권장 범위/핸들 | 편집 시작값 | 컷을 정하는 이유·인계 조건 |
|---|---|---:|---|
| 01 | 1.2~1.8초 / 생성 시 앞뒤 각 0.5~1.0초 | 1.6초 | 불확실한 지면이 읽힌 뒤 원거리 리듬을 인계 |
| 02 | 2.2~3.2초 / 생성 시 각 0.5~1.0초 | 2.8초 | 작은 실루엣이 ‘접근 중’이라고 인지된 뒤 첫발로 |
| 03 | 1.8~2.8초 / 반드시 각 0.5~1.0초 | 2.2초 | 빈 지면·사전 먼지·접지·계속 걷기가 모두 읽힐 때 |
| 04 | 1.2~1.8초 / 생성 시 각 0.5~1.0초 | 1.6초 | 같은 원경의 접근 지속을 확인한 뒤 내부로 |
| 05 | 1.4~2.0초 / 재생성 시 각 0.5~1.0초 | 1.8초 | 통로 안에 실제로 들어왔다는 시차를 확인 |
| 06 | 0.9~1.4초 / 재생성 시 각 0.5~1.0초 | 1.2초 | 측면 통과의 속도가 읽히는 한 동작 |
| 07 | 0.8~1.3초 / 재생성 시 각 0.5~1.0초 | 1.1초 | 실제 Go2 관절·몸통 정체성을 한 번 확인 |
| 08 | 1.1~1.7초 / 재생성 시 각 0.5~1.0초 | 1.5초 | 통로 깊이와 먼 열의 규모가 읽힘 |
| 09 | 0.7~1.2초 / 재생성 시 각 0.5~1.0초 | 1.0초 | 한 물체의 스침을 따라 다음 지면으로 |
| 10 | 1.0~1.6초 / 재생성 시 각 0.5~1.0초 | 1.2초 | 요철에 맞춘 실제 접지와 몸통 진행 확인 |
| 11 | 1.4~2.2초 / 생성 시 각 0.5~1.0초 | 1.8초 | 대군의 폭을 읽되 전체 로고는 숨긴 채 폭풍으로 |
| 12 | 2.2~3.3초 / 반드시 각 0.5~1.0초 | 2.4초 | 먼 접근이 충분히 읽히고 진입 가림에 도달할 때 |
| 13 | 1.4~2.2초 / 반드시 각 0.5~1.0초 | 1.6초 | 같은 통로의 통과 증거를 본 뒤 출구 띠에 도달 |
| 14 | 1.8~2.6초 / 반드시 각 0.5~1.0초 | 2.0초 | 시야 회복·보폭 감소·정지 준비를 인계 |
| 15 | 0.9~1.5초 / 반드시 각 0.5~1.0초 | 1.2초 | 중간 지지 뒤 마지막 발의 짧은 하강 중 컷 |
| 15b | 0.8~1.3초 / 반드시 각 0.5~1.0초 | 0.8초 | 마지막 접지 후 안정된 정지를 약 0.3~0.6초 읽힘 |
| 16 | 2.6~3.4초 탐색 / 원본 핸들 확인, 연장 시 각 0.5~1.0초 | 현 소재 2.8초 | 후퇴의 기존 감각을 기준으로 규모와 상승 경계를 실제로 비교 |
| 17 | 17~18 합계 6.0~7.4초 탐색 / 연속 소스 양끝 각 0.5~1.0초 확보 여부 확인 | 합계 현 소재 6.4초 | 부분 대형에서 전체 형상으로. 저속에서 고속으로 가는 곡선 유지 |
| 18 | 17~18 합계에 포함 / 17·18 사이 새 생성 핸들 중복 불필요 | 같은 6.4초에 포함 | 기존 로고 크기에 도달하는 실제 프레임에서 엔딩으로 |
| 19 | 기존 12초 시퀀스 그대로 / 생성 핸들 없음 | 12.0초 | 찢김·워드마크·하얀 선·태그라인·문구·스택 락업 유지 |

검산용 시작값: 01~11 17.8초 + 12~15b 8.0초 + 16 2.8초 + 17~18 6.4초 + 기존 엔딩 12.0초 = **47.0초**다. 이는 러닝타임 확정이 아니다. 17과 18을 각각 6.4초로 중복 계산하지 않는다. 실제 17/18의 내부 경계는 소재를 보고 기록하며 임의의 절반 분할을 하지 않는다.

## C. 컷별 제작 설계표

표의 모든 키비주얼은 **만들어야 할 프레임**이다. 이미 존재하거나 승인됐다고 주장하는 이미지가 아니다. 단일 스틸만으로 운동 승인을 대신하지 않으며, 핵심 컷은 시작·사건·끝의 묶음으로 검토한다.

### 참조 슬롯과 프롬프트 읽는 법

- **L, 소스 보존:** `@Video1`은 카메라와 객체 운동까지 올바르다고 확인된 한 컷이다. `@Image1`은 같은 컷의 승인된 재질 변환 키프레임, `@Image2`는 필요한 Go2 외형·재질 상세, `@Image3`은 배경 재질·빛의 스타일이다. 원본에 잘못된 보행이 있으면 L을 쓰지 않는다.
- **K, 새 동작:** `@Image1`은 앞 핸들 시작 G0의 올바른 구도·상태를 가진 키프레임, `@Image2`는 맞는 앵글의 Go2 정체성, `@Image3`은 로케이션 재질·빛만 담당한다. 잘못된 프리비즈 `@Video`는 넣지 않는다. 편집 F0·접지·편집 끝의 키비주얼은 검수판이며, 중간 시점 참조가 실제 지원될 때만 해당 시점에 바인딩한다. 생성 끝 프레임 기능을 쓰면 뒤 핸들까지 지난 상태를 넣는다.
- **P, 정확한 대군:** `@Video1`은 Isaac의 정확한 카메라·대열·글자 배치를 유지할 원본이다. 생성 결과는 허용된 재질·대기 레이어로만 쓴다. 개체 수·위치·글자 윤곽의 최종 권한은 원본과 합성에 있다.

`@Image`·`@Video`는 이 원고의 슬롯명이다. 실제 UI에서 업로드한 자산에 각 이름을 연결해야 한다. `video_edit`의 소스 표기는 브리프의 `<<<video_1>>>`에 실제 입력 영상이 연결되는 경우에 사용한다. 텍스트 속 토큰만 적는 것으로 파일이 첨부되지는 않는다. 엄밀한 t2v에는 이미지 슬롯이 없으므로 K의 이미지 참조 버전은 omni 계열 생성이다. F절에는 참조 없이 실행할 수 있는 순수 t2v 원고와 omni용 추가 문장을 구분해 둔다.

아래 각 영문 초안에 BRAND·HANDLE 문장과 해당 L/K/P 문장을 앞에 붙인다. 19는 생성 대상이 아니므로 이 공통문을 적용하지 않는다. F절의 순수 t2v 원고에도 BRAND·HANDLE을 붙이고 이미지 바인딩 문장은 omni에서만 사용한다.

**BRAND 공통:** `The subject is a terrain-adaptive locomotion policy expressed through authentic Go2 robots, not a warrior hero. Use a cool, precise, weighty and restrained visual mood with real sand, stone, dust, rigid mechanics and readable footing. Keep the approved dark-base palette and restrained orange accents; never invent a glowing grid, futuristic armor, weapons or victory gestures. Show scale as repeated trials of one policy, and settled footing as readiness for the next step. Preserve the existing logo and ending rather than generating any typography.`

**HANDLE 공통:** `The described action is the intended usable edit, not the full output duration. Include at least 0.5 seconds and preferably 1.0 second of valid continuous action before and after that usable section. Preserve event order and natural foot-contact timing. Handles must continue the same camera, geometry, lighting and action, not freeze frames, black padding, extra touchdowns or slowed airborne feet. Select an actually supported output duration long enough to contain the usable section plus both handles.` 이 문장은 생성 원고에 붙이며, 이미 완성된 소스를 단순 톤 변환할 때에는 존재하지 않는 프레임을 만들라는 뜻으로 사용하지 않는다. 그 경우는 확보된 원본 핸들까지 변환하거나 별도 연장 소재가 필요한지 확인한다.

**L 공통:** `@Video1 is the sole authority for the approved camera path, timing, geometry, robot placements and motion. @Image1 defines the approved surface treatment for that same geometry. @Image2 is Go2 appearance detail only; @Image3 is location materials and lighting only. Repaint surfaces only. Camera follows <<<video_1>>> 100%, no re-frame/re-time/re-angle. Remove the black grid by replacing its surface appearance, not the ground shape. Do not invent robots, change their gait or change their scale.`

**K 공통:** `@Image1 is the approved generated-clip opening at the beginning of the leading handle, before the usable edit starts. It defines this camera and that earlier event state. @Image2 defines the same Unitree Go2 identity and surface details, not its pose or camera. @Image3 is materials, light and atmospheric color only, never layout or motion. The usable edit starts later, after the leading handle. Generate physically consistent support and motion into that event; never hold an airborne foot to create padding. No source video is attached. No extra limbs, deforming chassis, giant robot scale or unmotivated camera moves.`

**P 공통:** `@Video1 is immutable layout and camera evidence. @Image1 is the approved look for the matching frame. @Image2 is Go2 surface detail only; @Image3 is atmosphere and lighting only. Preserve the source robot placements, orientations, ground coordinates and existing letter silhouette. This pass supplies surface and atmosphere treatment for compositing; it must not redesign the crowd or generate typography.`

프롬프트의 ‘100%’는 모델에 보내는 요구 문구다. 정확한 보존의 증거가 아니다. 원본과 비교해서 어긋난 결과는 합격시키지 않는다.

난이도의 후보 수는 **최종 합격 테이크 수가 아니라 탐색 예산 제안**이다. 낮음 2~4개, 중간 4~8개, 높음 8~16개, 최상 20~40개를 상한 범위로 계획하되 한 번에 전량 생성하지 않는다. 첫 4개에서 같은 구조 실패가 반복되면 참조나 방법을 바꾼다.

| 컷·의도 | 서사 축·브랜드 상징 | 도구 | 참조 정책·금지 입력 | 필요한 키비주얼의 프레임 | 영문 프롬프트 초안, 공통문 뒤에 사용 | 난이도·후보 예산 |
|---|---|---|---|---|---|---|
| 01 공간을 먼저 읽힘 | 불확실. 아직 디딤이 없는 땅 | Isaac 유지 후 video_edit 톤 변환 | L. 지형이 맞으면 원본, 틀리면 구도만 K. 다른 사막의 산·건물 금지 | 시작·끝 2장. 지면 요철, 지평선, 먼 대군 여백. 검은 격자 없음 | `Reveal the uncertain terrain at its true scale before the formation becomes readable. Hold the source horizon and landforms. In a restrained dark-base look, subtle wind moves real loose grains while the land remains still.` | 낮음 2~4 |
| 02 원거리 접근 실루엣 | 불확실에서 전진. 정책의 반복이 리듬으로 먼저 들림 | Isaac·톤 변환, 먼 군집 합성 | L은 처음부터 멀리 존재할 때만. 팝업 원본 금지. 04와 카메라 공유 | 시작·끝 2장. 낮은 능선 너머 작은 실루엣과 긴 빈 지면 | `The formation is already far beyond the ridge. Tiny Go2 silhouettes approach steadily through dust as many expressions of one locomotion policy. Keep the viewpoint fixed; no sudden appearance, zoom or militaristic spectacle.` | 중간 4~8 |
| 03 첫 접점 | 첫걸음. 정책과 실제 지면이 만나는 디딤 | K omni 또는 t2v·먼지 합성 | 잘못된 트롯 @Video 금지. 지면 @Image1, 오른앞발 @Image2, 룩 @Image3. 완료 접지를 시작에 주지 않음 | 필수 4장. 예시 F0 빈 지면, F20 사전 먼지, F33 접지, F55 이탈 | `Begin on empty ground beside the distant leading row. A lateral sand drift precedes the first visible right forefoot. It plants once, accepts load and lifts as walking continues. Make this small precise foothold decisive through real contact, not giant scale or an explosive stomp.` | 최상 20~40, F절 |
| 04 원경의 진전 | 전진. 한 번 디딘 결과가 대군의 지속으로 이어짐 | 02와 같은 소스·합성 | 02 카메라·지형 고정. 03 근거리 표식과 거리 점프 금지 | 02 끝과 04 시작·끝 비교. 아직 먼지 속 | `Return to the exact distant viewpoint and lens of shot 02 at a later moment. The same formation continues forward modestly against unchanged terrain. Preserve distance and quiet certainty; do not teleport the robots to the foot-insert camera.` | 중간 4~8 |
| 05 내부 진입 | 전진·규모. 한 정책의 수많은 실행 안으로 들어감 | 기존 소재 또는 L | Go2·통로가 맞으면 보존. 비Go2·충돌은 구도만 K | 통로 입구·내부 2장 | `Enter the open corridor between authentic Go2 rows. Show many grounded executions of the same policy through depth and parallax. Preserve the approved camera move and spacing; never pass through a robot.` | 중간 4~8 |
| 06 측면 통과 | 전진. 과시보다 반복되는 안정된 지지 | 기존 소재·L | 동작까지 적합한 @Video1만. 외형이 틀리면 전체 락 금지 | 핵심 통과·경계 3장 | `Keep the approved lateral pass with precise mechanical movement. Near legs cross faster than distant terrain. Repeated planted contacts sustain progress; no sliding feet, rubber limbs or speed reset.` | 낮음~중간 2~8 |
| 07 근접 측면 | 전진. 기술을 실제 물성의 Go2로 읽힘 | 기존 소재·L 또는 부분 합성 | 해당 측면 @Image2. 틀린 머리·관절 락 금지 | 몸통·관절 핵심 1장과 경계 | `Read the authentic Go2 chassis and joints in the approved close side view. Keep compact proportions and restrained material detail. No heroic armor, anthropomorphic face or ornamental science-fiction parts.` | 중간 4~8 |
| 08 통로 깊이 | 규모. 개별 영웅 대신 반복 실행의 깊이 | 기존 소재·L | 통로·대열·이동 적합 시 원본. 다른 카메라 프롬프트 금지 | 통로 소실점·3단계 깊이 시작·끝 | `Travel through the approved corridor with a stable vanishing point. Let successive rows express the scale of repeated policy execution. Foreground parallax is stronger than distant motion; preserve real spacing and material variation.` | 중간 4~8 |
| 09 스침 | 전진. 추상적 수량을 몸체의 거리감으로 바꿈 | 기존 소재·L | 실제 스치는 몸통만. 임의 다리·먼지벽 금지 | 가림 직전·직후 2장 | `Retain one brief near-lens chassis pass and its continuous parallax. Make proximity tactile and precise, not violent. No collision, whip pan or invented opaque dust wipe.` | 중간 4~8 |
| 10 지면 대응 | 전진·다음 디딤. 요철에 따라 접점을 바꾸는 정책 | Isaac·톤 변환, 필요 시 K | 앤트 구도 유지. 접지 불량 제외. 03 슬램 반복 금지 | 요철·다른 접지 높이·몸통 진행 3장 | `Observe careful foot placement over the existing uneven ground. Different local ground heights require different contacts while progress continues. Keep sand, stone and support readable; no repeated ceremonial stomp or invented jump.` | 중간~높음 4~16 |
| 11 선회·군집 폭 | 규모. 무수한 시행이 한 체계로 보임 | 카메라 유지·Isaac 군집 합성 | 빈 원본을 완성 배치로 락하지 않음. 카메라만 추출 후 올바른 군집 K/P | 선회 3장. 통로 외 빈 공간 보강, 아직 글자 없음 | `Use the approved orbit around a dense continuous Go2 formation. Show scale as repeated trials of one policy, not a military victory. Keep the deliberate corridor, fill unintended gaps with the controlled layout and withhold the overhead logo.` | 높음 8~16, 합성 기본 |
| 12 폭풍 접근 | 불확실의 심화에서 관통으로. 다음 접점의 시야가 줄어듦 | K omni·대기 합성 | 렌즈 앞부터 뿌연 원본·폭풍 팝업 금지. 맑은 시작과 진입판 | 예시 F0 먼 본체·빈 지면, F42 접근, F69 가림 | `Start with clear air at the lens and a distant dust front. Advance through the open Go2 corridor into one finite approaching band. Use layered real dust and restrained force; uncertainty increases through lost visibility, not fantasy effects.` | 최상 20~40, F절 |
| 13 폭풍 내부 | 관통. 보이지 않아도 디딤과 진행이 이어짐 | K omni·12 경계 인계 | @Image1은 앞 핸들 시점의 12 접근 상태. 12 마지막 가림은 편집 F0 검수판. 새 진입 반복 금지. R-A 유지 | 생성 G0의 앞선 접근판 추가. 편집 예시 F0 가림, F18 지면·어깨, F42 출구 띠, F47 경계 | `Use the leading handle to continue the actual prior approach into the same band. At the usable edit start, preserve the incoming velocity inside it. Glimpses of feet, backs and corridor show continued support; thin the dust toward one exit without repeating entry.` | 최상 20~40, F절 |
| 14 감속·정렬 | 관통에서 foothold 확보로. 스스로 지지를 준비함 | K Go2·군집 합성 | 비Go2·단일열 원본영상 금지. 13의 R-A·지면 인계 | 출구·다열·감속 말미 3장 | `Emerge behind the same Go2 into ordered rows. Reduce stride length and body travel relative to the ground as support is secured. The motion is controlled and deliberate, not damage, exhaustion or surrender. End before the last short braking swing.` | 높음 8~16 |
| 15 착착 | foothold 형성. 여러 지지가 하나의 안정으로 모임 | K omni, 14·15b와 묶음 | 반복 트롯·완료 정지 원본 금지. 측면·우측 관절. 발 장기 체공 금지 | 중간 지지·짧은 최종 스윙 시작, 필요 시 머리 방향·지형 | `Show the final braking sequence from a readable low side view. Distinct support contacts converge toward one settled foothold. Begin the designated final forefoot swing only near the cut; do not stage repeated stops or heroic stomps.` | 높음~최상 12~24 |
| 15b 단체 쿵 | foothold. 무수한 시행이 안정된 지지로 모이는 절정 | K omni 또는 t2v·소수 근경 합성 | @Image1은 앞 핸들의 정상 지지·감속. 하강 중인 편집 F0은 검수판. 발 상세·정지 자세 인계, 트롯·점프 금지 | 생성 G0 정상 지지 추가. 편집 예시 F0 하강, F6 접지, F12 안정, F23 잔먼지 | `Start the generated clip in the earlier supported braking state. After the leading handle, complete the same short forefoot placement once as neighboring supports finish. Settle with precise mechanical weight and hold readiness for the next step, not collapse or defeat.` | 최상 20~40, F절 |
| 16 끝없는 후퇴 | foothold의 규모. 같은 확신이 대군 전체에 있음 | 기존 Isaac 후퇴 기준·P 합성 | 실제 정지 검사. 걷는 영상 락 금지. 같은 카메라 정지군집 필요 여부 확인 | 시작·끝 필수. 발 고정·넓은 대열, 전체 글자 미공개 | `Use the approved retreat as the movement baseline and provide valid handles where available. The formation is already settled at fixed ground coordinates. Camera motion reveals collective certainty and scale; no robot restarts walking. Match the ascent boundary.` | 높음, 룩 4~8·합성 검사 |
| 17 상승·부분 인식 | foothold에서 FOOTHOLD로. 개별 지지가 한 이름의 일부 | Isaac 연속 원본 기준·P | 경계 실측 전 통과 금지. 8192 위치·카메라 권한. 자유 t2v 금지 | 16 끝과 비교할 시작·부분 빈 획 중간 | `Continue into the approved slow-to-fast ascent curve. Keep the settled robots fixed and let elevation alone reveal that many precise footholds belong to one larger structure. No rearrangement, sudden aerial jump or premature complete logo.` | 룩 중간·연결 최상 |
| 18 전체 FOOTHOLD | FOOTHOLD. 같은 대군과 같은 정책의 이름을 발견 | 17 동일 소스 후반·P·기존 로고 연결 | 글자 윤곽·8192 배치·도달 크기 유지. 철자·폰트 생성 금지 | 전체 인식·최종 크기. 기존 엔딩과 중첩 비교 | `Finish the same ascent into the exact source FOOTHOLD formation and approved scale match. Maintain restrained clarity and open letter gaps. Preserve the formation and original logo asset; do not redraw, re-spell or resize the identity.` | 합성 정합 우선, 룩 2~4 |
| 19 기존 엔딩 | 다음 걸음. FIND THE NEXT STEP으로 정지의 의미 완성 | 기존 12초 시퀀스 유지 | 정본 SVG·문구·순서·폰트·크기 바이트 원본 권한. 생성 대상 제외 | 새 이미지 없음. 18 경계·기존 엔딩 첫 프레임 비교 | `NO GENERATION. Preserve the existing 12-second ending: tear, wordmark, white line, FIND THE NEXT STEP, existing Korean message and stacked lockup. Use the original symbol, FOOTHOLD and Terrain-Adaptive Locomotion Policy assets unchanged.` | 생성 0, 연결 확인 |

## D. 참조 오염을 막는 제작 절차

**프리비즈의 승인되지 않은 부분을 모델에게 보여준 뒤 말로 무시하라고 하지 않는다. 승인된 정보만 입력에 남긴다.** 카메라가 좋고 보행이 틀린 영상은 좋은 참조와 나쁜 참조가 동시에 들어 있는 파일이다. ‘카메라만 따라라’라는 문장만으로 둘이 분리된다고 가정하지 않는다.

| 입력 상태 | 전달 방식 | 적용 컷 | 해서는 안 되는 것 |
|---|---|---|---|
| 구도·카메라·객체·보행이 모두 맞고 표면만 clay | 원본 영상을 L로 주고 표면만 변환 | 적합 판정한 01·02·04~10, 일부 16 | 재질 때문에 올바른 카메라까지 새로 생성 |
| 카메라는 맞지만 동작이 틀림 | 원본 영상 제외. 지면·소실점·피사체 점유율만 기록하여 새 키비주얼 작성. 가능하면 잘못된 로봇을 제거한 깨끗한 지면판 사용 | 03·15·15b, 보행이 남은 16 | 트롯 영상을 넣고 ‘heavy stop’만 추가 |
| 한 장의 구도는 맞지만 로봇이 비Go2 | 그 프레임을 그대로 ‘기하의 유일한 정답’으로 잠그지 않음. 잘못된 몸통·다리를 제거한 구도판에서 진짜 Go2 시트로 다시 구성하고 승인 | 14, 필요 시 05~09 | 로봇 형태까지 틀린 이미지에 repaint only 지시 |
| 밀도가 부족함 | 카메라 자료와 군집 배치를 분리. 올바른 밀도의 Isaac 레이어·깊이 자료를 먼저 설계 | 11, 16~18 | 빈 군집 영상을 잠근 채 ‘더 빽빽하게’라는 모순 지시 |
| 카메라·먼지·타이밍 모두 의도와 다름 | 프리비즈를 생성 입력에서 완전히 제외. 시작·중간·끝 키비주얼과 별도 운동 원고로 재작성 | 해당하는 12·13, 03·15b | 실패 영상의 마지막 프레임을 다음 컷에 무조건 체이닝 |
| 전체 배치·문자 형상이 정확해야 함 | 원본·오브젝트 마스크·깊이를 합성의 구조로 유지 | 16~18 | 글자·군집까지 포함한 전체 프레임을 자유 생성 결과로 교체 |

브리프의 `IMAGE 1(clay) is the ONLY source of truth for geometry/composition`은 **그 clay의 기하가 실제 정답일 때만** 사용한다. 캐릭터가 틀린 프레임에는 적용하지 않는다. 승인 키비주얼을 새로 만든 뒤에는 그 이미지가 새로운 기하 기준이 된다. 이때 외형 시트는 같은 Go2의 표면·디테일을 확인하고 다른 포즈·카메라·배치를 덮어쓰지 않는다.

컷마다 다음 다섯 줄의 참조 기록을 남기도록 인계한다. 실제 제작에서는 자산 파일명과 버전으로 채운다.

| 기록 | 적을 내용 |
|---|---|
| 그대로 둘 것 | 카메라·지형·배치·동작 중 승인된 항목 |
| 새로 만들 것 | 첫발, 최종 정지, 올바른 Go2, 먼지 등 |
| 입력에서 뺄 것 | 틀린 동작·로봇·밀도·격자 질감이 들어 있는 영상 또는 영역 |
| 각 슬롯의 권한 | 구도, 정체성, 표면, 빛, 시작 상태, 끝 상태 중 하나 |
| 합격 증거 | 원본과 비교할 기준점, 핵심 접지 프레임, 다음 컷 경계 |

참조 수가 많을수록 안전해지는 것은 아니다. 현재 각도에 필요한 Go2 두세 면만 선별하고, 스타일판의 로봇·산·구조물은 크롭하여 형상이 유입되지 않게 한다. 모델 슬롯이 부족하면 캐릭터 시트 전체를 작은 콜라주로 욱여넣지 말고 승인 키비주얼을 우선하고 가장 중요한 상세 한 장을 남긴다. 이때 빠진 입력이 무엇인지 기록한다.

프레임 체이닝은 **검수된 사건 시간의 인계**다. 실패한 12 끝을 13에 넣으면 실패가 연속될 뿐이다. 분리 생성하면서 앞 핸들도 확보하려면 뒷 컷의 생성 시작에는 앞 컷 끝보다 핸들만큼 이른 상태를 준다. 앞 컷 끝은 뒷 컷의 편집 F0을 고를 기준이지 생성 G0이 아니다. 그 편집 경계가 먼지로 가려졌다면 마지막 가시 구조와 가림 프레임의 역할을 나눈다. 중간 시점 조건이 지원되지 않으면 경계판은 검수용으로 두고 유효 핸들을 가진 출력에서 연결 지점을 고른다. 두 이미지를 주는 것만으로 중간 운동이 보장되지는 않는다.

키비주얼에는 카메라 높이·화각·진행 방향·보행 위상·먼지의 원인을 감독 검토용 여백에 적는다. 모델 입력에는 같은 이미지의 **문자·화살표 없는 깨끗한 버전**을 사용한다. 그래픽 표식이나 화면 구석의 주석이 최종 영상에 생성되는 것을 막기 위해서다.

## E. Go2 캐릭터 시트와 로케이션 기준

Go2 시트는 새로운 로봇을 디자인하기 위한 무드보드가 아니다. **현재 프로젝트가 실제로 사용하는 Go2 자산 하나의 동일성 증명**이다. 자산의 정확한 변형·장착품·색상은 Isaac 원본에서 확인하고 그대로 고른다. 브랜드 이름만 보고 다른 Go2 구성이나 장착 센서를 추가하지 않는다. 메시의 치수·관절 한계·재질이 현실의 특정 제품 사양과 동일하다는 외부 검증은 이 문서에서 하지 않는다.

### Isaac에서 추출할 시트 목록

| 묶음 | 앵글·부위·상태 | 조명·배경 | 쓰임 |
|---|---|---|---|
| 형태 기준 | 정면·후면·좌측·우측·위·아래. 같은 중립 자세·같은 배율의 6면 | 중성 확산광, 무늬 없는 중간 명도 배경, 접지 그림자 약하게 | 몸통 길이·다리 연결·앞뒤 구별. 측면을 뒤집어 반대쪽으로 재사용하지 않음 |
| 화면용 기준 | 앞좌·앞우·뒤좌·뒤우 3/4, 몸통 높이의 실제 원근 | 중성광 한 벌, 최종 로케이션 주광 방향 한 벌 | 05~09·14·16의 화면 각도에 맞는 정체성 |
| 낮은 카메라 | 우측 앞발을 보는 저공 측면·낮은 사선, 후측면 발목 높이 | 최종 지면 위에서 접지 그림자 보존 | 03·10·15·15b. 카메라가 지면을 관통하지 않고 발이 과대하게 보이지 않게 확인 |
| 관절 | 앞다리와 뒷다리 각각의 몸통 연결, 상·하부 관절, 케이블·하우징이 있는 면 | 중성광, 작은 사광을 추가해 형태 읽기 | 다리 수 증가·관절 반전·고무처럼 휘는 생성 판정 |
| 발 | 오른앞발의 앞·옆·바닥, 접촉면, 바닥과 닿는 경계 | 중성광 및 최종 지면 사광 | 첫발과 마지막 발의 형태. 실제 자산 접촉부 재질을 확인하고 금속·고무를 임의로 바꾸지 않음 |
| 몸통 식별 | 전면 센서 부위·측면 패널·등·후면 | 텍스처가 과노출되지 않는 중성광 | 다른 로봇 머리·장갑·눈·장식이 생기는지 확인 |
| 재질 | 같은 몸통 면을 정면광·사광·역광에서 각각 | 노출과 화이트밸런스 고정 | 중성광 시트의 색을 유지하면서 폭풍 속에서도 동일 개체로 읽기 |
| 지지 자세 | 네 발 안정 지지, 브레이킹 직전, 마지막 오른앞발 접지 직후 | 고정 카메라와 지면, 접지 그림자 선명 | 정지 키포즈. 실제 확보된 올바른 자세만 사용 |
| 보행 위상 | 한 주기의 주요 접지·이탈 상태를 같은 시점 간격으로 | 같은 시점·카메라·바닥 | 일반 보행 검수용. 실제 정지를 못 하는 RL 트롯은 정지 동작의 참조로 쓰지 않음 |

시트의 텍스트 라벨과 관절 표식은 검토판에만 둔다. 모델에는 해당 뷰의 고해상도 개별 크롭을 전달한다. 전체 6면 시트는 먼저 감독·제작자가 동일성을 확인하는 판이며, 매 영상 생성의 필수 입력이 아니다. 발 클로즈업에 정면 머리 시트를 주고 정체성이 지켜질 것이라 기대하지 않는다.

@Image2에는 **그 컷에서 보일 각도**의 Go2 이미지를 연결한다. 03·15b는 낮은 오른앞발 및 관절 접지 상세, 07은 해당 측면, 12~14는 후측면, 16은 실제 시작 구도에 맞는 면을 쓴다. K의 @Image1에 이미 올바른 Go2가 있다면 @Image2가 자세·크기·위치를 바꾸지 못하게 역할을 제한한다. 두 이미지의 로봇이 서로 다르면 생성부터 하지 않고 기준 자산을 정리한다.

### 로케이션은 한 장소, 여러 거리다

로케이션 기준판은 세 부분을 가진다. 하나는 로봇 없는 전체 지형, 하나는 발이 닿을 지면의 입자·요철, 하나는 먼지 안과 밖의 광원·색 관계다. 01·02·04에서 공유할 먼 능선, 12~14의 통로와 L-A 표식, 16~18의 동일 월드 배치를 따로 기록하되 모두 하나의 월드 좌표계에 둔다. 가까운 표식을 다른 장소에 무작정 복사하지 않는다.

14~16의 열과 통로는 18의 최종 대형에서 역으로 지정한다. 정지한 뒤 로고를 만들려고 로봇이 옆으로 이동하지 않는다. 해당 구역의 정지 전 동작도 최종 접지 좌표로 이어지도록 설계한다. 넓은 글자 사이의 빈 공간은 낮은 카메라와 선택한 시야 때문에 앞서 보이지 않을 수 있지만, 없던 대열을 17에서 새로 만들어 채우지는 않는다. R-A는 연결 검사용 기준일 뿐 정책을 대신하는 영웅 캐릭터가 아니다.

한 개의 주광 방향, 하나의 지면 재질 계열, 하나의 노출·색 관리 기준을 고른다. 먼지 안에서는 산란과 콘트라스트 감소로 바뀌고, 출구에서 갑자기 다른 시간대나 다른 색의 사막이 되지 않는다. 폭풍을 빠져나온 14~16에는 몸통 하단과 발 주변에 지나온 먼지의 흔적을 약하게 남겨 통과 사건의 잔여를 보인다. 새 로봇처럼 깨끗해지는 장면 전환은 피한다.

다크 베이스를 검게 뭉개라는 뜻으로 해석하지 않는다. 접점·입자·관절은 읽히고 대기·차체의 명도 관계는 차분하게 유지한다. 주황은 실제 승인된 기준선·게이트가 소재에 있을 때만 제한적으로 이어받는다. 없는 10m 선을 새로 그려 실측처럼 보이게 하지 않으며, 그런 자산이 없으면 영상 본편은 실제 지면을 유지하고 주황 모티프는 기존 엔딩이 담당한다. 검은 격자 제거와 주황 기준선 보존 여부를 서로 다른 항목으로 확인한다.

스타일 이미지에 찍힌 태양을 어느 카메라에서도 화면 오른쪽에 복제하지 않는다. 월드에서 빛이 오는 방향을 고정하고 카메라가 바뀌면 화면상 방향은 그에 맞춰 변한다. 렌즈·심도·셔터 느낌은 컷의 목적에 맞추되 재질과 광원의 세계는 유지한다. 지나치게 얕은 심도로 접점이나 군집의 수를 지우지 않는다.

16~18 합성에 필요한 제작 인계 항목은 원본 카메라·프레임 타이밍, 지형판, 정지 군집, 깊이·개체 또는 열 마스크, 접지 그림자다. 추출 가능 여부는 실제 Isaac 씬에서 확인한다. 가까운 몇 열은 상세 외형을 보완하고 먼 열은 원본 배치를 유지하며 거리·대기만 조정한다. 정확한 글자 배치를 담당하는 원본 레이어를 마지막까지 남긴다.

## F. 세 극적 비트의 프레임 설계와 생성 원고

프레임은 모두 0부터 시작하는 30fps **편집 시작값 예시**이며 범위 양끝을 포함한다. 예를 들어 0.8초 시작값은 F0~23, 24프레임이다. B절 권장 범위 안팎에서 실제 연결에 따라 재타이밍할 수 있으며, 모델이 각 프레임을 그대로 생성한다는 뜻이 아니다. 프레임 번호는 앞뒤 핸들을 제외한 사용 구간 기준이다. 앞뒤 각 최소 0.5초, 가능하면 1.0초를 별도로 확보한다. **무엇을 이어받고 어디서 컷하는지가 초수보다 우선**이다. 재타이밍할 때 빈 지면·접근·정지 후 여유를 조정하고 짧은 발 스윙을 통째로 느리게 늘이지 않는다.

### 03 첫발 · 시작값 2.2초, 66프레임 예시. 권장 1.8~2.8초

이 장면의 주인공은 큰 발이 아니라 작은 접점이 일으키는 실제 변화다. 넓은 지면이 먼저 있고, 그 위를 진짜 크기의 Go2가 통과한다. 첫발을 전신 낙하·거인 발·괴수 발소리로 만들면 물리감 대신 장르가 바뀐다.

카메라는 고정된 낮은 사선이다. 출발 제안은 지면 위 8~12cm, 풀프레임 환산 28~35mm 정도의 시야다. 실제 Go2 자산 크기와 프레이밍에 맞춰 조정한다. 발목~아랫다리와 바닥이 읽히고, 몸통 전체를 초반부터 드러내지 않는다. 로봇은 화면 왼쪽에서 오른쪽으로 지나가는 측면 관계를 기본으로 하며, 카메라가 발을 쫓지 않는다. 전경 지면 표식은 02·04 관측점의 표식과 다르다.

| 프레임 | 보이는 동작 | 먼지·음향·카메라 |
|---|---|---|
| F0~8 | 지면만 보임. 발·다리 없음 | 멀리 있던 리듬의 잔여와 지면 가까운 바람. 화면을 흔들지 않음 |
| F9~16 | 화면 밖 앞선 발·바람에 교란된 얇은 입자가 옆으로 들어옴 | 주인공 발의 미래 접점은 아직 조용함. 입자는 기존 바람 방향을 따르며 새 수직 분출 없음 |
| F17~21 | 먼저 그림자가 들어와 다가오는 형체를 예고 | 실루엣이 전부 보이지는 않음. 음악이나 바람을 잠깐 얇게 만들어 다음 접점을 읽을 여백 확보 |
| F22~32 | 오른앞발이 프레임 밖에서 들어와 짧고 연속적으로 내려옴 | 관절 연결 유지. 땅 바로 위에서 멈추거나 떠 있지 않음. 카메라 고정 |
| F33 | 한 번의 첫 접지 | 접지 순간의 짧고 단단한 저중역 충격. 실제 접촉부에 맞는 마찰음을 얹고 쇠망치 울림으로 만들지 않음 |
| F34~37 | 관절이 하중을 받음. 발은 지면 표식에 고정 | 이때부터 접점에서 낮은 먼지가 옆으로 퍼짐. 필요하면 1~2프레임의 미세한 촬영 충격만 적용 |
| F38~44 | 발이 지지하는 동안 몸통은 계속 전진 | 몸통 전체를 멈추지 않음. 지나가는 차체와 지면의 시차가 유지됨 |
| F45~50 | 하중이 다음 지지로 옮겨가며 발이 이탈을 준비 | 같은 발을 두 번 찍지 않음. 먼지가 발 형태를 삼키지 않음 |
| F51~58 | 발이 들려 진행 방향으로 떠남 | 동작이 계속 걷기임을 확정. 다른 다리가 보이더라도 첫 접점의 인지를 가리지 않음 |
| F59~65 | 발이 떠난 자리와 흩어지는 먼지 | 04 원경의 소리로 거리감을 되돌릴 준비. 발이 남아 있는 정지 컷으로 끝내지 않음 |

사전 먼지의 인과를 설명할 수 없는 후보는 폐기한다. 주인공 발이 공중에 있는데 바로 아래에서 원형 먼지 폭발이 먼저 생기는 후보는 ‘극적’이어도 틀렸다. 반대로 접지 먼지를 너무 크게 만들어 발이 닿는 순간이 안 보이는 후보도 제외한다.

**03 순수 t2v 프롬프트 전문**

```text
Create a single continuous photoreal cinematic shot of the first visible footfall of a real-scale Unitree Go2 quadruped robot in a vast dry terrain location. This is a close insert beside the distant leading rows of an advancing army, not the arrival of the whole army at the previous distant observer.

The policy is the subject, and this precise foot contact expresses its first foothold. Use a cool, restrained, weighty mood, actual sand and stone, and the approved dark-base palette without invented orange lights or military heroism. The action below describes the usable edit. Include at least 0.5 seconds, preferably 1.0 second, of valid action before and after it; do not create padding by hovering a foot, slowing contact or repeating a touchdown.

Use a locked camera roughly at ankle height, close to the ground, with a restrained wide-angle field of view. Show granular sand, small embedded stones and low terrain relief. Begin with terrain only: no foot, leg or robot is visible. The robot will travel from screen left toward screen right. Preserve authentic compact Go2 proportions, four mechanically connected legs, rigid joint housings and a rigid chassis. Never enlarge the robot into a giant machine.

During the empty-ground opening, a thin lateral drift of loose grains enters from outside the frame, carried by the established wind after an earlier offscreen disturbance. It does not erupt from the future footprint. A moving shadow follows. Only then does the right forefoot enter from outside the frame and descend in one continuous short placement.

Around the middle of the shot, the foot contacts the ground exactly once. The contact remains visible. The foot fixes to the same ground point while the joints take the load and the chassis continues traveling forward. Give this small metal robot a convincing grounded mass through load transfer, stable contact, brief joint settling and restrained ground disturbance. Do not use a human stomp or a whole-body fall. A small low dust puff begins at the contact point only after touchdown and spreads along the surface.

The robot keeps walking. Transfer the load to the next support, lift the planted forefoot and let it travel out of the close view. Finish on the continuing movement and residual dust, not a stopped robot. The camera remains locked, with at most a tiny brief contact impulse. Maintain one location, one directional light and readable ground texture throughout.

No jump, no hover, no repeated touchdown, no sliding planted foot, no extra limbs, no soft or bending chassis, no animal paws, no giant scale, no explosive dust wall, no pre-contact dust eruption beneath this foot, no slow-motion suspension, no zoom, no camera following the foot, no text or generated logo.
```

**03 omni 추가 바인딩:** `@Image1 is the approved empty-ground generated opening at the start of the leading handle, before the usable opening. @Image2 is the authentic Go2 right-forefoot and lower-leg identity. @Image3 is the matching terrain material and directional lighting only. No gait video is attached. The contact keyframe is a later event reference, never the generated opening.` 접지 이미지를 넣을 슬롯이 없거나 중간 시점 역할을 지정할 수 없으면 접지판은 후보 검수에만 사용한다.

### 15b 마지막 발 · 시작값 0.8초, 24프레임 예시. 권장 0.8~1.3초

14부터 같은 발이 오래 내려오지 않도록 15를 먼저 고친다. 15 F0~32에서는 지지의 인계가 진행되고, 마지막 오른앞발의 짧은 스윙은 F33~35에서 시작한다. 15b F0~5가 그 스윙을 이어받고 F6에서 닿는다. 따라서 지정한 마지막 스윙은 약 0.3초 규모다. 이는 동작 원고의 제안이며 실제 관절 동작을 보지 않고 Go2의 특정 제어기 성능이라고 주장하지 않는다.

15b 카메라는 낮은 우측 사선, 지면 위 8~15cm를 출발점으로 잡는다. 접촉면과 관절 하단이 동시에 보이고, 전경 발 뒤에 최소한 서로 다른 로봇의 지지가 읽힌다. 너무 긴 망원으로 여러 발을 하나처럼 겹치지 않는다. 필요하면 35~50mm 환산 시야로 시작하되 실물 프레임에서 정한다. 15에서 로봇 머리 방향·지형 표식을 읽혔다면 15b는 같은 쪽을 유지한다.

| 프레임 | 보이는 동작 | 먼지·음향·카메라 |
|---|---|---|
| F0~5 | 15에서 시작한 동일한 오른앞발의 남은 하강 | 다른 지지발들은 이미 땅을 받치고 있음. 마지막 발 밑에 새 먼지가 먼저 솟지 않음 |
| F6 | 전경 기준 발 한 번 접지 | ‘쿵’의 핵심 어택. 한 발의 음량만 과장하기보다 가까운 몇 로봇의 마지막 지지를 하나의 질량으로 묶음 |
| F5~8의 주변 로봇 | 가까운 소수의 마지막 필요한 지지가 좁은 시차로 마무리 | 각 로봇의 나머지 발은 지지 유지. 모든 네 발이 동시에 공중에 있는 후보는 제외 |
| F7~11 | 관절의 짧은 하중 흡수와 몸통 안정화 | 접점에서 낮게 먼지가 퍼짐. 작은 수직 정착만 있고 고개 끄덕임·차체 반동은 억제 |
| F12~23 | 발·몸통의 전진이 끝나고 지면에 고정 | 12프레임, 0.4초의 안정 상태. 먼지와 짧은 잔향만 계속됨. 카메라도 이 접지 인서트 안에서는 안정 |

배경 8192대의 네 발을 같은 프레임에 모두 찍을 필요는 없다. 정지의 집단성은 읽히는 소수의 접지, 뒤의 여러 열, 다음 16의 안정된 대군으로 완성한다. 순수 생성에서 근경 동시성이 반복 실패하면 **전경 R-A 한 대의 올바른 접지를 먼저 확보하고, 배경 소수의 별도 접지와 정지 군집을 합성**한다. 이때 겹치는 다리·먼지·그림자의 앞뒤를 깊이와 마스크로 확인한다.

‘쿵’ 이후 16에서는 추가 정지 홀드를 삽입하지 않는다. 고정된 발과 움직이는 카메라의 차이가 바로 규모를 만든다. 첫 0.2초 정도 충격 잔향과 낮은 잔먼지가 이어질 수 있으나 16이 대군을 보여주는 순간을 가리지 않는다. 먼 원거리 군집까지 모든 개별 금속 소리가 동시에 또렷하게 들리는 음향은 피한다.

**15b 순수 t2v 프롬프트 전문**

```text
Create a single continuous photoreal close shot of the final braking foot placement of a formation of authentic, real-scale Unitree Go2 quadruped robots after they have crossed a dust band. This is the completion of one stop already in progress, not a new stomp and not a jump landing.

Express a secure foothold that makes the next step possible. Many supports converge into quiet certainty, not victory, exhaustion or defeat. Use cool precision, grounded mechanical weight and real sand and stone in the approved dark-base look. Include at least 0.5 seconds, preferably 1.0 second, of valid continuous action before and after the intended usable edit. The preceding handle continues the real braking action and the following handle holds supported stillness; neither repeats the landing.

Place a steady camera low beside the right forefoot of the nearest robot, in a three-quarter side angle that clearly separates the foot, the lower joint and the ground contact. Show the supporting feet of several other robots in the next rows behind it. Keep the compact Go2 chassis and mechanically connected legs consistent. Preserve the established terrain, travel heading and directional light.

Begin the full generated clip before the final swing, in a normal supported braking state seen from this shot's low camera. Use the leading handle for the preceding support transfer. Only near the end of that handle does the designated right forefoot begin its short final swing. At the later start of the usable edit, it is already descending while other feet maintain support. Early within that usable section it touches down once and stays fixed. A few neighboring robots finish their own final necessary contacts within a small stagger. They do not lift all four feet or jump in unison.

After touchdown, show a brief controlled load transfer through the joints and a restrained final settling of the rigid chassis. Convey grounded mechanical mass through support, deceleration and the end of body travel. Small low dust puffs begin at the individual contact points only after those feet land. Let the dust spread sideways along the surface, never as an explosion covering the feet.

For the latter part of the usable section and throughout its trailing handle, the planted feet and bodies remain visibly settled relative to the ground. Dust alone continues moving. No robot starts another stride after the final settling. Keep the camera stable and let the stillness of the supported formation carry the weight.

No repeated touchdown, no jump landing, no synchronized four-foot leap, no foot sliding, no continued trot, no hovering foot, no extra limbs, no deforming chassis, no exaggerated body recoil, no human head nod, no giant scale, no pre-contact dust beneath the incoming foot, no full-frame dust burst, no camera retreat inside this insert, no generated text or logo.
```

**15b omni 추가 바인딩:** `@Image1 is the generated opening at the start of the leading handle: normal supported braking before the final swing, reconstructed from the same event time in shot 15 using the shot-15b camera. @Image2 is authentic Go2 foot and joint identity only, not a pose override. @Image3 is surface and lighting only. The descending-foot image is the later usable-edit F0 checkpoint, never the generated opening. Use it as an intermediate condition only if that timed function is supported; otherwise it is for selection. A supported end-frame input must show the settled state after the trailing handle. No trot or jump-landing video is attached.`

### 12·13 먼지 통과 · 시작값 2.4초+1.6초. 권장 2.2~3.3초+1.4~2.2초

12는 ‘원래 렌즈 앞에 없던 먼지가 가까워지는 것’, 13은 ‘그 안에서 계속 전진한다는 것’을 각각 증명한다. 카메라는 로봇 몸통 상단 부근 높이의 통로 안을 움직이며, 실제 Go2 높이에 맞춰 설정한다. 사람이 서서 걷는 높이를 막연히 ‘머리 높이’로 적용하지 않는다. 열린 통로를 지나고 몸통·다리를 통과하지 않는다.

| 컷·프레임 | 동작·구조 | 카메라·먼지·소리 |
|---|---|---|
| 12 F0~20 | 맑은 렌즈 앞, 빈 지면, 멀리 있는 먼지 본체와 다가오는 돌출 띠 | 초반부터 앞으로 조금 움직임. 폭풍이 프레임 안에서 갑자기 생성되지 않음. 먼 바람은 아직 둔함 |
| 12 F21~47 | 통로의 지면이 뒤로 흘러 접근 거리가 줄어듦 | 완만하게 가속. 먼 층보다 가까운 먼지 가닥의 시차가 커짐. 화면 전체의 투명도만 낮추지 않음 |
| 12 F48~68 | 지면 가까운 모래가 먼저 흐르고 가까운 띠가 렌즈에 닿음 | 상승하는 바람·입자 소리. 기존 발 리듬이 안으로 잠기되 사라졌다가 새로 시작하지 않음 |
| 12 F69~71 | 가장 짙은 진입 가림 | 약 0.1초의 90~100% 가림 제안. 여기서 컷 가능. 속도는 계속 전진 |
| 13 F0~5 | 같은 가림 속을 계속 움직임 | 12의 바람·전진 속도·색 인계. 새 진입 가속 없음 |
| 13 F6~32 | 가까운 등·어깨가 양옆으로 빠지고 지면·통로가 간헐적으로 읽힘 | R-A는 여전히 앞에 남음. 먼 대열은 중앙에서 상대적으로 오래 머묾. 몸통이나 다리 사이를 관통하지 않음 |
| 13 F33~41 | 출구 방향의 대비가 돌아옴 | 카메라의 상대 추월 속도를 완만하게 줄임. 로봇은 아직 진행. 먼지의 흐름 방향은 유지 |
| 13 F42~47 | 얇은 마지막 먼지 띠, 같은 지면·R-A가 그 너머에 보임 | 완전 가림을 다시 만들지 않음. 14 첫 6프레임 정도에 같은 띠가 걷히도록 연결 |

13의 내부 전체가 불투명하면 삭제하거나 재생성한다. 카메라가 전진한 증거인 근경·원경의 차등 이동, 바닥 접점, 한 번의 출구가 보여야 한다. 12와 13은 가능하면 **한 개의 연속 통과 후보에서 편집상 두 구간을 얻는 방법을 먼저 시험**한다. 같은 공간을 이어갈 가능성을 높이려는 제작 선택이며, 모델 지원 길이·동작 안정성에 따라 나눠 만들 수도 있다. 나눌 때는 하나의 기준 이미지와 실제 앞 컷 경계로 인계한다. 두 독립 t2v 결과가 저절로 같은 장소가 된다고 가정하지 않는다.

**12 순수 t2v 프롬프트 전문**

```text
Create a single continuous photoreal cinematic approach to a dust storm in a dry terrain location occupied by marching, authentic Unitree Go2 robots. At the opening, the air immediately in front of the lens is clear. A substantial dust body is visible far ahead beyond a readable stretch of open ground. A finite projecting band from that dust body is moving toward the marching formation. Do not place the camera inside fog at the beginning.

Show uncertainty confronting a continuing locomotion policy with cool precision and restrained physical weight. Use real dust, sand and stone, not supernatural storm effects, glowing grids or a military charge. Keep the approved dark-base palette. The described approach is the usable edit; include at least 0.5 seconds, preferably 1.0 second, of valid continuous travel before and after it. The trailing handle continues inside the same band without restarting the approach.

The Go2 formation moves forward along one world direction. The camera also travels forward in an already open corridor between rows, looking in that same direction at the backs and rear three-quarter surfaces of the robots. Keep one designated lead robot ahead of the camera. The camera may pass nearer robots beside the corridor, but it must not pass through any chassis or leg and must not overtake the designated lead robot.

Begin with restrained forward movement, then smoothly gain relative speed as the distance to the approaching dust band closes. Preserve a visible ground gap for the opening portion. Build depth with separate dust layers: low grains begin moving over the ground, nearer wisps move faster across the view, and the more distant body remains slower and softer. The dust band must approach through space rather than appear as a sudden transparency overlay.

Near the end, enter this same finite band. Let a nearby sheet of dust pass the lens before denser dust briefly obscures almost the whole image. Maintain forward velocity through the final frame. The shot ends just inside the band; it does not reach the exit and does not begin a second approach. Keep the same directional light, terrain material, formation heading and authentic Go2 proportions throughout.

No instant fog at the opening, no flat expanding wall, no opaque screen for the entire shot, no camera spin, no reframe, no camera passing through a robot, no teleporting crowd, no robot scaling, no storm appearing from nowhere, no second storm, no generated text or logo.
```

**12 omni 추가 바인딩:** `@Image1 is the approved earlier clear-air generated opening at the start of the leading handle, with the same corridor and lead Go2. @Image2 is rear-view Go2 identity only. @Image3 is location surface, light and dust color only. The usable opening and near-entry keyframes are later event checkpoints, not the generated opening. Reject an earlier source video that begins in dense lens-level fog.`

**13 순수 t2v 프롬프트 전문**

```text
Create a single continuous photoreal cinematic segment whose usable edit begins just inside a finite moving dust band. The full generated clip starts earlier, at the beginning of its leading handle, continuing the same approaching corridor and moving dust edge from the previous shot. Enter the band once during that handle and reach the usable-edit start already traveling forward in the inherited brief dense occlusion. Do not repeat entry within the usable edit and never restart the camera from rest.

The policy continues finding support through uncertainty. Keep the mood cool, precise, restrained and physically weighty, with real dust and mechanically grounded Go2 motion rather than fantasy spectacle. Retain the approved dark-base palette. Include at least 0.5 seconds, preferably 1.0 second, of valid matching travel before and after the intended usable edit. These handles overlap the preceding entry and following exit in event time; the final edit must not repeat either event.

Continue through an open corridor between marching, authentic Unitree Go2 robots. The camera looks along the robots' forward travel direction from roughly their upper-body height. Near backs and shoulders move outward and backward toward the frame edges as the camera advances relative to them. A designated lead Go2 stays ahead in the corridor view. More distant rows remain smaller near the center for longer. Keep the bodies rigid and the legs mechanically connected.

Let changing dust density reveal intermittent ground texture, planted feet and the same corridor boundaries. These glimpses must show actual forward travel through a three-dimensional volume. The camera must not pass through a robot. Dust continues in one established world-space wind direction, with near wisps moving differently from distant layers because of perspective.

In the final portion of the usable section, the far edge of this finite band becomes readable. Ease the camera's relative passing speed smoothly as ground contrast returns. The intended edit endpoint is where thin wisps clear from the designated lead robot and the same landmark. Then continue into clear air for the trailing handle, overlapping the next shot's event time. Keep the same robots moving into their later deceleration; do not complete a stop in this segment.

No repeated storm entry, no second dust wall, no prolonged fully opaque screen, no camera restart, no camera rotation, no reversed travel, no lead robot teleportation, no sudden new terrain, no clean new robot replacing the dusty lead, no extra limbs, no camera penetration through bodies, no generated text or logo.
```

**13 omni 추가 바인딩:** `@Image1 is the generated opening at the beginning of the leading handle, taken from the matching event time before shot 12 ends, not its final occluded frame. @Image2 preserves Go2 identity and persistent corridor geometry from the last clear view; it must not override the opening robot positions or restart that earlier action. @Image3 is matching light and dust color only. Shot 12's final state is the later usable-edit F0 checkpoint. Shot 14's opening is the usable-edit endpoint checkpoint, not the generated endpoint; an end-frame input must be after the trailing handle. Use intermediate checkpoints as timed inputs only if supported, otherwise use them for selection. Preserve the incoming velocity and lead robot.` 이 컷은 가림 속 구조 복원이 우선이므로 @Image2를 일반 캐릭터 시트 대신 마지막 가시 구조에 배정한 **명시적 예외**다. 12·13을 한 연속 소재에서 얻으면 두 컷 사이는 내부 편집 경계이며 별도 생성 시작 이미지를 만들지 않는다.

### 세 비트의 소리 관계

02의 먼 착착, 03의 가까운 첫 접점, 15의 짧은 착착, 15b의 묶인 마지막 지지가 하나의 리듬 언어를 쓴다. 03은 접지 뒤에도 다음 걸음이 이어지고, 15b 뒤에는 걸음의 어택이 끝난다. 12·13의 바람은 지면·몸통의 가림에 맞춰 밀도가 바뀌고, 14에서 시야와 함께 공간의 음향도 열린다. ‘쿵’은 큰 폭발음이나 포격음보다 접촉·마찰·짧은 기계 정착·저역의 합으로 만든다. 기존 엔딩의 음향과 타이밍은 바꾸지 않고 18까지의 연결에서 정리한다.

## G. 제작 우선순위·선별·실패 대안

### 실제 제작 순서

| 순서 | 먼저 확보할 결과 | 이유·다음 진행 조건 |
|---|---|---|
| 1 | 기존 16 시작·끝, 17 시작·끝, 19 길이·첫 프레임의 확인 기록 | 결말이 고정된 영화이므로 거기서 필요한 축·정지·밀도·크기를 역산한다. 실제 자료에 접근할 수 없으면 이 항목은 미확인으로 남기되 03 독립 시험은 가능하다. |
| 2 | Go2 기준 시트·지면판·주광 방향·승인할 룩 한 벌 | 동일성을 정하기 전 20~40개를 생성하면 서로 다른 로봇 40개를 얻게 될 수 있다. 16 근경과 03 발에서 같은 재질이 성립하는지 먼저 본다. |
| 3 | 03과 15b의 키비주얼 묶음 및 각 4개 정도의 소규모 동작 시험 | 영화의 시작과 절정, 실패 위험이 가장 큰 부분이다. 올바른 접지·형태가 하나도 없으면 많은 군집 컷을 먼저 완성하지 않는다. |
| 4 | 15b 합격 동작에서 15·14 경계 역설계 | 마지막 발이 언제 내려오는지 확정한 후 앞 컷을 맞춘다. 완성된 15를 붙이기 위해 15b 접지를 두 번 보여주지 않는다. |
| 5 | 12·13 연속 후보 또는 동일 통로의 경계 묶음 | 14 출구 구도에서 역으로 통로·R-A를 정하고 실제 생성은 진입에서 출구까지 인과 순서로 만든다. 단순히 영상을 역재생하지 않는다. |
| 6 | 11의 군집 밀도, 16~18의 원본 보존 합성 시험 | 생성 모델의 배치 보존 한계를 이때 확인한다. 8192대·글자 윤곽을 변경하지 않는 구조를 먼저 확정한다. |
| 7 | 01·02·04와 기존 05~10의 필요한 부분 | 핵심 비트와 룩이 고정된 뒤 연결 컷을 채운다. 이미 좋은 소재는 다시 만들지 않고 차이만 해결한다. |
| 8 | 전체 약 44~50초 범위에서 조립·재타이밍·음향 비교 | 핸들을 활용해 실제 연결로 길이를 정한다. 설명 없이 첫 디딤·한 번의 관통·안정된 정지·같은 대군의 로고·다음 걸음이 읽히는지 본다. 기존 12초 엔딩은 비교하여 그대로 보존한다. |

순서 1의 실제 파일 점검과 순서 2의 시트 준비는 병행할 수 있다. 이 문서는 제작 계획만 작성하며 위 생성·추출·합성 작업을 수행했다는 보고가 아니다.

### 후보 20~40개를 쓰는 방법

숫자는 합격 보장이 아니라 탐색 한도다. 03·15b·12~13처럼 실패 비용이 높은 비트에 집중하고, 모든 컷에 같은 수량을 배정하지 않는다. 첫 묶음에서는 카메라·외형·접지·사건 순서를 보고, 두 번째 묶음에서는 살아남은 구조의 무게·먼지만 조정한다. 4개 중 4개가 같은 발 미끄러짐이나 동일성 오류를 보이면 단어를 늘리기보다 구도·참조·합성 경로를 바꾼다.

자동 선별은 존재한다고 가정하지 않는다. 제작 단계에서 준비할 경우 검은 격자 잔존, 큰 프레임 깜박임, 기준점 이동, 로고 실루엣 차이처럼 제한된 항목을 우선 거르는 보조 수단으로 둔다. 검출 점수가 접지 물리·영화적 인지의 최종 판정을 대신하지 않는다. 이 요청에서는 코드를 만들지 않았다.

| 판정 | 즉시 탈락 조건 | 합격 후보 사이의 비교 |
|---|---|---|
| 정체성·기하 | 다리 수·연결 변화, 차체 변형, 다른 로봇, 원본 로고 변형 | 동일 Go2로 읽히는 표면·빛·근경 디테일 |
| 접지 | 발 미끄러짐, 체공 정지, 반복 착지, 쿵 뒤 보행 재개 | 접점의 가독성, 짧은 하중 흡수, 억제된 반동 |
| 먼지 | 미래 접점에서 먼저 폭발, 모든 동작 가림, 컷마다 바람 반전 | 입자 크기·층·잔여 움직임의 공간감 |
| 사건 순서 | 대군 팝업, 두 번의 폭풍 진입, 여러 번 완전 정지 | 기대·접촉·결과가 자연스럽게 읽히는 박자 |
| 연결 | R-A·통로·밀도 순간 교체, 방향·스케일 급변 | 정상속도에서 시선이 끊기지 않는 정도 |
| 브랜드 | 멈춤이 고장처럼 보임, 로고를 위해 개체가 재배열됨 | 정지의 안정과 상승의 발견이 같은 사건으로 읽힘 |

하드 조건을 통과한 후보끼리 무음 정상속도, 접지 부근 프레임 확인, 소리를 붙인 정상속도 순서로 본다. 무음에서 성립하지 않는 접지를 큰 소리로 합격시키지 않는다. 반대로 프레임 하나의 작은 먼지 차이 때문에 정상속도에서 좋은 연결을 불필요하게 폐기하지 않는다. 기준은 각각의 결함이 장면의 인과와 정체성을 바꾸는가다.

### 실패 시 대안

| 위험 | 첫 대응 | 계속 실패하면 |
|---|---|---|
| 03이 괴수 발·점프·가짜 사전 먼지로 나옴 | 전신을 덜 보이는 낮은 사선, 실제 발 상세, 순수한 한 번의 걸음으로 단순화 | 올바른 Go2 발 동작 한 개를 확보하고 사전 옆먼지·접지 후 먼지를 별도 합성. 임팩트를 위해 틀린 착지 채택 금지 |
| 15b 집단 동시 정지가 무너짐 | 읽히는 로봇 수를 소수로 제한하고 마지막 필요한 지지만 맞춤 | 전경 한 대, 중경 소수, 후경 정지 군집으로 분리. 단체 점프를 대안으로 쓰지 않음 |
| 12·13이 두 개의 다른 폭풍이 됨 | 한 연속 후보에서 두 구간을 얻는 시험, 마지막 가시 통로로 체이닝 | 맞는 카메라·대군 판에 전경·중경·후경 먼지 층을 합성. 불투명 화면 연장으로 접속 오류를 가리지 않음 |
| 14가 1열·다른 로봇으로 회귀 | 문제 영상 제외, 실제 Go2를 넣은 다열 키비주얼 승인 | 근경 Go2와 측면 군집을 따로 구성. 처음부터 틀린 영상의 재질 변환 반복 금지 |
| 11이 계속 텅 비어 보임 | 의도된 통로와 잘못된 빈 공간을 구별해 원본 군집 보강 | 카메라를 바꾸지 않는 Isaac 군집 레이어를 구조로 채택 |
| 16에서 다시 걷거나 밀도가 달라짐 | 카메라 유지, 객체 상태 별도 검사·정지 군집 준비 | 원본 경로 기반 합성을 기본 산출물로 전환. ‘카메라 확정’을 ‘보행도 확정’으로 해석하지 않음 |
| 16·17의 실제 경계가 불연속 | 기존 핸들·공통 지형·카메라 경로 확인 | 맞는 연결 경로와 필요 시간을 구체화해 감독 재승인. 0.6초면 해결된다고 선약하지 않음 |
| 18에서 글자·수량이 변형됨 | 생성 결과의 구조를 폐기하고 원본 윤곽·위치 복구 | 대군 형상은 원본 유지, 룩·대기만 합성. 기존 로고·엔딩 재생성 금지 |
| 키비주얼은 좋지만 운동이 매번 망가짐 | 설명문을 더 화려하게 만들지 않고 동작의 자유도·보이는 개체 수를 줄임 | 직접 제어 가능한 키포즈·소수 개체 동작과 합성으로 전환. 이를 미래 제작 대안으로 두며 이번 작업에서 리깅·코드·렌더를 실행하지 않음 |

### 감독 승인에 올릴 묶음과 완료 조건

승인 질문을 수십 개로 나누지 않는다. 한 번의 검토 묶음에 02→03→04의 공간 관계, 03 첫 접점, 12~14의 같은 먼지 띠, 14~15b 한 번의 정지, 16→17 실제 경계, 로고 도달 프레임을 놓는다. 검토용 키비주얼 옆에는 해당 컷의 시작·사건·끝과 다음 컷의 첫 프레임을 배치한다. 동일 크기의 예쁜 포스터 20장으로 대체하지 않는다.

감독이 이 설계를 승인하면 **Go2·로케이션 기준판과 03·15b·12~13의 키비주얼·핸들 포함 시험 생성에 바로 착수할 수 있다.** 실제 생성물을 앞뒤 컷과 붙여 감독이 길이를 정한다. 16·17의 실제 연결과 기존 12초 엔딩의 인계 프레임은 소재 확인 후 최종 편집을 잠그는 조건이다. 실물 확인 없이 완성 영상의 연속성까지 승인됐다고 보고하지 않는다.

이 설계의 최종 합격은 ‘화려한 대군이 나왔다’가 아니다. **멀리서 걸어오던 같은 Go2 대군이 같은 지면과 먼지를 지나, 한 번 정확히 멈추고, 그 자리에 선 채 FOOTHOLD로 드러나야 한다.** 로고와 엔딩은 그 결과를 기존 디자인으로 받아 마무리한다.

## 검토 이력

| 판 | 변경 내용 | 검증 상태 |
|---|---|---|
| v1.0 | 브리프 A~G 재검증, 01~19·15b 제작표, 참조 정책, 시트 명세, 세 핵심 비트 프레임·영문 원고, 제작 순서·대안 | 내부 초안, 후속 정정에 따라 교체 |
| v1.1 | 추가 브랜드 브리프·감독 길이 정정 반영. 정책 중심 서사 열·공통 룩·기존 12초 엔딩·권장 범위·앞뒤 핸들·47초 시작값 명시 | gpt-6-astra·high 1차 검토: 수정 필요. 13·15b 생성 시작과 앞 핸들 충돌 2건 |
| v1.2 | 생성 G0·편집 F0·생성 끝을 분리하고 공통문·표·t2v·omni·체이닝에 동일 적용. 한국어 주어 수정 | gpt-6-astra·high 2차 검토: 발행 가능. 기존 차단 2건 해소, 잔존 모순 없음 |

검증은 `codex exec --model gpt-6-astra -c model_reasoning_effort=high`로 두 차례 수행했다. 2차 검증자는 수정 주장을 믿지 않고 본문과 원자료를 다시 대조하여 컷표 20행, 47.0초·1410프레임의 편집 시작값, 마지막 발 스윙 0.3초, 안정 정지 0.4초를 재확인했다. 이 판정은 **글로 된 제작 설계의 일관성과 요구 충족**에 대한 것이며, 실제 영상의 완성도·모델 출력 성공·16→17 실물 연결을 검증했다는 뜻이 아니다.
