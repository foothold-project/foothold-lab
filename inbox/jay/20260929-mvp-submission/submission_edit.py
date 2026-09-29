"""사용자가 승인한 공식 제출본 편집 범위. 보존 원문은 수정하지 않는다."""
from bs4 import BeautifulSoup

PROJECT={
    'title':'Unitree Go2 미경험 험지 적응 시뮬레이션 및 실기 자율주행 프로젝트',
    'period':'2026.07 ~ 2026.12.11','mvp_date':'2026.09.30','data_date':'2026.09.29',
    'team':'FOOTHOLD','leader':'오흥재','members':['임석헌','오현민','맹라현','이민우'],
    'sources':{'title':'docs/REPORT.md:1','period':'web/_src/pitch.base.html:332','roster':'docs/ROLES.md:68-110','mvp_date':'docs/REPORT.md:23'},
}
REMOVE={
    's14-b003':'HUD 유무·제작 파이프라인에 관한 내부 기록',
    's14-b035':'영상 조각별 편집 길이',
    's14-b038':'영상 제작용 화면 축척 설명',
    's14-b039':'영상 제작 해상도 설명',
    's14-b040':'이전 영상과 화면 픽셀 수 비교',
    's14-b041':'화면 픽셀 수의 반복 설명',
    's14-b043':'영상 프레임 수와 검은 프레임 검수 기록',
    's14-b045':'이전 영상 삭제와 중복 판단 기록',
    's14-b046':'학습 진행 영상에 HUD가 없는 제작상 이유',
    's14-b047':'학습 진행 영상의 재촬영·편집 이력',
    's14-b048':'폐기한 영상과 화면 축척의 반복 설명',
    's14-b050':'MVP 판정에서 제외한 fs1·fs2 참고 항목 제목',
    's14-b051':'MVP 판정에서 제외한 fs1·fs2 참고 항목',
}

def edit_section(sec,edits,excluded):
    sid=sec['id']
    if sid=='s16':
        for n in sec.select('[data-source-id]'):
            excluded.append({'source_id':n['data-source-id'],'reason':'원보고서 개정 이력은 웹 기록에 보존하고 공식 제출본에서 제외','text':n.get_text(' ',strip=True)})
        return False
    for n in list(sec.select('[data-source-id]')):
        key=n['data-source-id']
        if key in REMOVE:
            excluded.append({'source_id':key,'reason':REMOVE[key],'text':n.get_text(' ',strip=True)});n.decompose()
    replacements={
        's3-b020':'볼 것: 디딤돌 사이에서 발을 지지하는가. 1.0 m/s에서 NVIDIA와 foothold-v1의 종합 성공률은 0%, foothold-v2는 24%다. 0.5와 1.5 m/s에서는 세 모델 모두 0%다. 한 영상의 통과 여부와 100회 평가의 성공률은 구분한다.',
        's10-b020':'foothold-v1의 slow010 추종비 0.92는 추종비가 산출된 48개 환경의 집계다. 전체 64개 환경 중 낙상은 23개였다. 추종비의 유효 표본 수와 낙상 환경 수는 같은 분모를 뜻하지 않으므로 두 지표를 함께 해석해야 한다.',
        's10-b028':'확장 평가의 저속 명령 네 가지와 회전 두 가지를 세 모델의 영상 18편으로 비교한다.',
        's10-b040':'0.40 m/s는 배포본 학습 명령의 전진 속도 하한이다. 이 평가에서 세 모델의 평균 추종비는 0.87~0.94였다. 더 낮은 명령보다 모델 간 차이가 작았지만, 학습 구간 진입만으로 차이가 사라진다고 단정할 수는 없다.',
        's10-b013':'저속 명령 · 실제 전진 속도 (m/s · 최대 64개 환경 중 유효 표본 평균 · 명령에 가까울수록 좋다)',
        's10-b019':'두 모델의 오차 방향이 다르다. 0.10 m/s 명령에서 NVIDIA의 평균 전진 속도는 0.006 m/s로 미달하고, v2g2는 0.167 m/s로 초과한다. v2g2의 학습 명령 하한 0.4 m/s가 저속 추종에 영향을 줬을 가능성은 있지만, 이 비교만으로 원인을 분리해 확인한 것은 아니다.',
        's10-b029':'세 모델의 영상은 모두 env 51의 사례다. 캡션에서 해당 환경의 값과 전체 평가의 집계값을 구분한다. 사례 영상 하나가 64개 환경 전체를 대표하는 것은 아니다.',
        's10-b048':'turn_rev에서 +0.50 rad/s 명령의 평균 추종비는 NVIDIA 0.43, foothold-v1 약 0.00, v2g2 0.01이었다. 이 평가에서 양의 요레이트 추종이 약한 경향은 세 모델에 공통으로 나타났다. 다만 공통 경향만으로 학습 레시피의 영향을 배제할 수는 없다. 원인은 통제 실험으로 추가 확인해야 한다.',
        's10-b049':'외란 조건의 비교 평가 결과는 아직 제시하지 않는다. 외란 이벤트를 유지하는 옵션과, 외란의 크기·시점·판정 기준을 통제하는 독립 평가 시나리오는 구분해야 한다.',
        's10-b051':'현재 판정 아홉 항목은 평지에서의 명령 수행을 평가한다. 횡이동·험지 회전·장거리는 평가 하네스의 확장이 필요하다. 외란 이벤트 유지 옵션은 있지만, push_robot이라는 독립 평가 시나리오는 등록돼 있지 않다. 아래 표에서 구현과 측정의 부족을 구분한다.',
        's10-b054':'외란 평가는 이벤트의 크기·방향·시점과 회복 지표를 먼저 정하고, 실제 외란이 발생하는지 확인한 뒤 기준선 세 모델을 같은 조건으로 비교한다. 횡이동은 명령 프로필과 판정 기준을, 험지 회전과 장거리는 하네스의 지형·시간 설정을 확장해야 한다.',
        's14-b002':'각 영상은 지형 통과, 명령 응답, 남은 실패를 확인하기 위한 사례다. 개별 장면의 결과와 전체 평가에서 집계한 비율을 구분해 제시한다.',
        's14-b022':'정지 전환 영상은 10초, 정지 유지 영상은 20초다. 회전 영상은 NVIDIA와 foothold-v2가 18초, foothold-v1이 6.48초다. 영상 길이와 환경의 낙상 판정 시각은 구분한다.',
        's14-b037':'학습에서는 4,096개 환경을 200개 지형 칸에 배치해 칸당 약 20개 환경을 사용한다. 이 영상은 30개 칸에 600개 환경을 배치해 비슷한 밀도로 재생했다. 환경 간 물리 상호작용은 격리돼 있다. 영상은 저장된 정책을 재생한 시각 자료이며 학습 전체를 실시간 촬영한 것은 아니다.',
    }
    for key,new in replacements.items():
        n=sec.select_one(f'[data-source-id="{key}"]')
        if n:
            old=n.get_text(' ',strip=True);n.name='p';n.clear();n.append(new)
            edits.append({'section':sid,'source_id':key,'before':old,'after':new,'reason':'영상 제작 이력 대신 결과 해석에 필요한 조건을 서술'})
    heading=sec.select_one('[data-source-id="s10-b017"]')
    if heading:heading.name='h4'
    for key in ['s10-b011','s10-b052','s12-b015','s15-b002']:
        n=sec.select_one(f'[data-source-id="{key}"]')
        if not n:continue
        old=n.get_text(' ',strip=True)
        for row in list(n.select('tbody tr')):
            cells=row.select('td')
            if not cells:continue
            label=' '.join(c.get_text(' ',strip=True) for c in cells[:-1])
            def cell(index,text):cells[index].clear();cells[index].append(text)
            if key=='s10-b011' and 'push_robot' in label:
                cell(2,'외란 유지 옵션 있음 · 독립 시나리오 없음')
            if key=='s10-b052' and 'push_robot' in label:
                cell(2,'--keep_pushes는 기존 외란 이벤트를 유지하는 옵션이다. SCENARIOS에는 push_robot이 등록돼 있지 않으며, 비교 평가 결과도 없다.')
                cell(3,'외란의 크기·방향·시점과 회복 지표를 명세하고, 이벤트 발생을 검증한 뒤 NVIDIA·foothold-v1·배포본을 같은 조건으로 평가한다.')
            if key=='s10-b052' and '험지 회전' in label:
                cell(2,'축 2 프로브는 평면 지형을 사용한다. sim/eval/eval_command_response.py의 환경 구성에서 terrain_type을 plane으로 지정한다.')
            if key=='s12-b015' and '확장 축' in label:
                cell(-1,'저속 명령과 turn_rest·turn_rev는 배포본까지 평가했다. 횡이동·험지 회전·장거리 하네스는 확장이 필요하다. 외란은 이벤트 유지 옵션만으로 독립 평가가 완성되지 않으므로 조건과 회복 지표를 먼저 정의한다. turn_rev의 낙상 0.1562를 포함한 확장 평가 결과와 사례 영상은 9절에서 제시한다.')
            if key=='s12-b015' and 'resume' in label:
                cell(-1,'중단된 실험에 공통으로 있던 resume의 영향을 분리해야 한다. 초기 가중치, optimizer 상태, 명령·지형 조건을 통제해 비교한다. 아직 원인이 확인된 것은 아니다.')
            if key=='s12-b015' and '학습 전체 영상' in label:row.decompose()
            if key=='s15-b002' and 'HUD 유무를 센 것' in label:row.decompose()
            if key=='s15-b002' and '학습 진행 41.3' in label:
                cell(-1,'sim/eval/results/20260929-train-army-ramp/train-army.mp4 · 웹 사본 docs/assets/video/v2/train-army.mp4 · 생성 _out/loop/train_army_ramp.sh · 연결 _out/loop/train_army_ramp_join.py')
        if key=='s12-b015':
            for index,row in enumerate(n.select('tbody tr')):
                first=row.select_one('td')
                if first:first.clear();first.append('가나다라마바사'[index])
        new=n.get_text(' ',strip=True)
        if old!=new:edits.append({'section':sid,'source_id':key,'before':old,'after':new,'reason':'독립 검증 지적과 사용자 요청에 따라 구현 상태를 정정하고 제작 이력·개별 참고 실험명을 정리'})
    n=sec.select_one('[data-source-id="s14-b012"]')
    if n:
        old=n.get_text(' ',strip=True);table=n.select_one('table').extract();n.clear()
        p=BeautifulSoup('<p>세 모델의 영상은 모두 env 8의 사례다. foothold-v1이 stop·hold·turn에서 넘어지는 사례를 골라 같은 환경 번호로 비교했다. 이 장면은 대표 사례이며, 전체 64개 환경의 낙상 비율은 별도 표로 제시한다.</p>','html.parser').p
        n.append(p);n.append(table)
        edits.append({'section':sid,'source_id':'s14-b012','before':old,'after':n.get_text(' ',strip=True),'reason':'촬영 이력을 덜고 사례 선정 방식과 전체 평가의 구분을 보존'})
    return True

def cover(logo):
    return f'''<header class="cover" id="top">
<div class="cover-top"><img src="{logo}" alt="FOOTHOLD 로고"><span>인공지능사관학교 7기</span></div>
<div class="cover-title"><p class="eyebrow">MVP RESEARCH REPORT</p><h1>MVP 종합보고서</h1><p class="project-title">Unitree Go2<br>미경험 험지 적응 시뮬레이션 및<br>실기 자율주행 프로젝트</p><p class="cover-focus">미경험 지형의 보행 정책 일반화와 명령 수행 능력 평가</p></div>
<div class="cover-bottom"><dl><div><dt>프로젝트 기간</dt><dd>{PROJECT['period']}</dd></div><div><dt>MVP 중간발표</dt><dd>{PROJECT['mvp_date']}</dd></div><div><dt>결과 기준일</dt><dd>{PROJECT['data_date']}</dd></div></dl>
<dl class="cover-team"><div><dt>팀명</dt><dd>{PROJECT['team']}</dd></div><div><dt>팀장</dt><dd>{PROJECT['leader']}</dd></div><div><dt>팀원</dt><dd>{' · '.join(PROJECT['members'])}</dd></div></dl></div>
<div class="cover-bottomline"><span>FOOTHOLD</span><span>SIMULATION · POLICY LEARNING · EVALUATION</span></div></header>'''
