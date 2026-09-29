"""원자료를 다시 집계해 외부 심사자용 2쪽 요약 PDF를 만든다."""
from pathlib import Path
import csv,json,hashlib,io
from statistics import mean
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.colors import HexColor
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import Paragraph,Table,TableStyle
from reportlab.graphics import renderPDF
from svglib.svglib import svg2rlg
import fitz
from submission_edit import PROJECT

ROOT=Path(__file__).resolve().parent
REPO=ROOT.parents[2]
W,H=595.276,841.89
L=44; WIDTH=W-2*L
INK='#161c26'; MUTED='#4a5566'; GREEN='#0b6459'; SOFT='#e0f0ed'; PAPER='#f6f5f1'; RED='#a3342a'
pdfmetrics.registerFont(TTFont('Malgun','C:/Windows/Fonts/malgun.ttf'))
pdfmetrics.registerFont(TTFont('MalgunBold','C:/Windows/Fonts/malgunbd.ttf'))
pdfmetrics.registerFontFamily('Malgun',normal='Malgun',bold='MalgunBold')

def source_bytes(path):
    snapshot=ROOT/'source/evidence'/path.relative_to(REPO)
    return (snapshot if snapshot.exists() else path).read_bytes()

def main():
    sweep=REPO/'sim/eval/results/20260928-v2-sweep/sweep_long.csv'
    rows=list(csv.DictReader(io.StringIO(source_bytes(sweep).decode('utf-8-sig'))))
    names={'discrete_obstacles','floating_ring','pit','repeated_boxes','repeated_cylinders','stepping_stones','star','wave'}
    rates={}; cells={}
    for model in ('nv','v1','v2'):
        selected=[r for r in rows if r['model']==model and float(r['difficulty'])==.5 and r['terrain'] in names]
        assert len(selected)==24 and {int(r['episodes']) for r in selected}=={100}
        rates[model]=mean(float(r['overall_success_rate']) for r in selected)*100
        cells[model]=len(selected)
    stones=mean(float(r['overall_success_rate']) for r in rows if r['model']=='v2' and float(r['difficulty'])==.5 and r['terrain']=='stepping_stones')*100
    falls={}
    evidence=[]
    for model in ('nvidia','v1','v2'):
        falls[model]={}
        for scenario in ('stop','hold','turn'):
            path=REPO/f'sim/eval/results/20260929-axis2-fall/{model}/{scenario}/per_env.json'
            data=json.loads(source_bytes(path).decode('utf-8'))
            assert len(data)==64
            falls[model][scenario]=sum(bool(r['fell']) for r in data)
            evidence.append({'path':path.relative_to(REPO).as_posix(),'sha256':hashlib.sha256(source_bytes(path)).hexdigest()})
    stairs={m:next(r for r in rows if r['model']==m and r['terrain']=='pyramid_stairs_inv' and float(r['difficulty'])==.9 and float(r['speed'])==1.5) for m in ('v1','v2')}
    slow={}
    for model in ('nvidia','v2'):
        path=REPO/f'sim/eval/results/20260929-axis2-ext-clips/{model}/slow010/per_env.json'
        data=json.loads(source_bytes(path).decode('utf-8'))
        values=[r['tracked_vx_mps'] for r in data if r.get('tracked_vx_mps') is not None]
        slow[model]=mean(values)
        evidence.append({'path':path.relative_to(REPO).as_posix(),'sha256':hashlib.sha256(source_bytes(path)).hexdigest()})
    output=ROOT/'output/FOOTHOLD-MVP-summary.pdf'
    c=canvas.Canvas(str(output),pagesize=(W,H))
    c.setTitle('FOOTHOLD MVP 종합보고서 · 심사자용 요약')
    c.setAuthor('FOOTHOLD')
    bounds=[]
    def para(text,y,size=10,leading=15,bold=False,color=INK,x=L,width=WIDTH):
        p=Paragraph(text,ParagraphStyle('p',fontName='MalgunBold' if bold else 'Malgun',fontSize=size,leading=leading,textColor=HexColor(color),wordWrap='CJK'))
        _,height=p.wrap(width,H)
        p.drawOn(c,x,H-y-height);bounds.append({'page':c.getPageNumber(),'top':y,'bottom':y+height,'text':text})
        assert y+height<790,(y,height,text)
        return y+height
    def line(y):
        c.setStrokeColor(HexColor('#d9d6cd'));c.setLineWidth(.6);c.line(L,H-y,W-L,H-y)
    def header(number,tag):
        c.setFillColor(HexColor(PAPER));c.rect(0,0,W,H,fill=1,stroke=0)
        drawing=svg2rlg(str(ROOT/'source/media/foothold-wordmark-ink.svg'))
        scale=125/drawing.width;drawing.scale(scale,scale)
        renderPDF.draw(drawing,c,L,H-44-drawing.height*scale)
        para(tag,43,9,13,color=GREEN,x=300,width=W-L-300)
        line(81)
        c.setFont('Malgun',8);c.setFillColor(HexColor(MUTED))
        c.drawString(L,27,'FOOTHOLD · MVP 2026.09.30 · 결과 기준 2026.09.29')
        c.drawRightString(W-L,27,f'{number} / 2')
    def section(title,y):return para(title,y,13,19,True,GREEN)+8
    header(1,'MVP 종합보고서 · 심사자용 요약')
    y=para('미경험 지형의 보행 성능을 높이고,<br/>명령 수행의 손실을 함께 평가했다',101,22,31,True)
    y=para(PROJECT['title'],y+12,10,15,color=MUTED)
    y=para('본 요약은 전체 프로젝트 중 시뮬레이션 정책 학습과 평가 결과를 다룬다. 실제 로봇의 험지 적응과 실기 자율주행 완성을 주장하는 결과는 아니다.',y+12)
    y=section('연구 질문과 접근',y+21)
    y=para('NVIDIA Go2 Rough 정책을 출발점으로, 학습하지 않은 지형에서도 전진 보행이 가능한지 평가했다. 지형을 만나는 경험을 늘리도록 학습 조건을 조정하고, 그 과정에서 정지와 회전 능력이 손상되는지도 별도로 확인했다.',y)
    y=para('foothold-v2는 사전학습 정책에서 추가 학습한 모델이다. 지형 통과(축 1)와 명령 수행·외란 대응(축 2)을 구분한다. 정지·회전과 저속 명령을 평가하고, 아직 평가하지 않은 범위도 명시했다.',y+9)
    y=section('핵심 결과 · 미경험 8종 평균 성공률',y+23)
    chart_y=y
    for i,(key,label) in enumerate([('nv','NVIDIA'),('v1','foothold-v1'),('v2','foothold-v2')]):
        by=chart_y+i*35
        para(label,by+2,10,15,x=L,width=105)
        c.setFillColor(HexColor('#e1ded5'));c.rect(L+110,H-by-22,310,19,fill=1,stroke=0)
        c.setFillColor(HexColor(GREEN if key=='v2' else '#6b807b'));c.rect(L+110,H-by-22,310*rates[key]/100,19,fill=1,stroke=0)
        para(f'{rates[key]:.1f}%',by+2,11,16,True,GREEN if key=='v2' else INK,x=L+430,width=77)
    y=chart_y+112
    y=para('조건: 난이도 0.5, 미경험 지형 8종, 속도 0.5·1.0·1.5 m/s. 모델별 24개 조건에서 조건당 100회 평가한 성공률의 단순 평균이다. 성공은 생존·전진·속도 추종·방향 기준을 함께 충족해야 한다.',y,9,14,color=MUTED)
    y=section('성과의 범위',y+21)
    y=para(f'foothold-v2는 NVIDIA 대비 {rates["v2"]-rates["nv"]:.1f}%p, foothold-v1 대비 {rates["v2"]-rates["v1"]:.2f}%p 향상했다. 다만 stepping stones 평균은 {stones:.1f}%에 머물렀다. 평균 성능의 향상이 모든 지형의 해결이나 모든 난이도에서의 우위를 뜻하지 않는다.',y)
    y=para('기여는 미경험 지형 평가와 명령 수행 평가를 연결해, 개선된 능력과 남은 실패를 같은 보고서에서 드러낸 데 있다.',y+9,10,15,True)
    c.showPage()
    header(2,'남은 실패 · 해석 범위 · 다음 연구')
    y=section('명령 수행은 별도 검증이 필요하다',102)
    y=para('전진 중심의 학습에서 지형 성능이 좋아져도 정지·회전 능력은 함께 좋아지지 않았다. 아래는 각 시나리오 64개 환경에서 낙상한 환경 수다. 시나리오별 수치이며 전체 명령 공간의 성공률이 아니다.',y)
    y+=12
    data=[['모델','정지 전환','정지 유지','회전']]+[[label]+[f'{falls[key][s]} / 64' for s in ('stop','hold','turn')] for key,label in [('nvidia','NVIDIA'),('v1','foothold-v1'),('v2','foothold-v2')]]
    table=Table(data,colWidths=[170,112,112,WIDTH-394],rowHeights=[26]*4)
    table.setStyle(TableStyle([('FONTNAME',(0,0),(-1,-1),'Malgun'),('FONTNAME',(0,0),(-1,0),'MalgunBold'),('FONTSIZE',(0,0),(-1,-1),10),('TEXTCOLOR',(0,0),(-1,-1),HexColor(INK)),('BACKGROUND',(0,0),(-1,0),HexColor(SOFT)),('LINEBELOW',(0,0),(-1,-1),.5,HexColor('#d9d6cd')),('VALIGN',(0,0),(-1,-1),'MIDDLE'),('ALIGN',(1,0),(-1,-1),'CENTER')]))
    table.wrap(WIDTH,H);table.drawOn(c,L,H-y-104);y+=116
    y=para('v2는 이 검사에서 정지 시 낙상이 없었지만, 회전에서는 7/64가 넘어졌다. NVIDIA의 회전 낙상 4/64보다 많았다. 횡이동·후퇴·외란 등 전체 축 2 능력을 이 세 검사만으로 판정할 수 없다.',y)
    y+=13
    iw=(WIDTH-12)/2;ih=iw*9/16
    for i,(file,label) in enumerate([('axis2-turn-v1.jpg','foothold-v1 · 넘어지는 장면'),('axis2-turn-v2.jpg','foothold-v2 · 서 있는 장면')]):
        c.drawImage(str(ROOT/'stills'/file),L+i*(iw+12),H-y-ih,iw,ih,mask='auto')
        para(label,y+ih+5,9,13,True,x=L+i*(iw+12),width=iw)
    y+=ih+25
    y=para('같은 env 8, 영상 3.5초의 사례. v1의 실패 사례를 골라 비교했다. v1 낙상 판정은 3.70초이며, 이 한 장면으로 각 모델의 전체 낙상률을 대신할 수 없다.',y,8.5,13,color=MUTED)
    y=section('남은 실패와 다음 연구',y+17)
    y=para(f'저속 명령은 덜 움직일수록 좋은 것이 아니다. 0.10 m/s 명령에서 실제 전진 속도 평균은 NVIDIA {slow["nvidia"]:.3f}, v2 {slow["v2"]:.3f} m/s였다. 명령에 대한 미달과 초과를 구분해 평가해야 한다.',y)
    y+=8
    y=para('고난도 하강 계단(난이도 0.9, 1.5 m/s)에서는 성공률이 v1 90%에서 v2 3%로 낮아졌다. 두 모델 모두 생존율은 100%였다. 이는 낙상과 속도 추종 실패를 구분해야 하는 사례다.',y)
    y=para('평가 지형 배치가 제한돼 있어 새로운 배치로의 일반화는 추가 검증이 필요하다. 다음 단계는 명령 범위를 넓히면서 지형 경험을 확보하고, 관측·기억·지형 인지 구조의 효과를 동일한 두 축에서 비교하는 것이다. 아직 검증된 개선책은 아니다.',y+8)
    y+=12;line(y)
    y=para('프로젝트 2026.07 ~ 2026.12.11 · FOOTHOLD<br/>팀장 오흥재 · 팀원 임석헌 · 오현민 · 맹라현 · 이민우',y+9,8.5,13,color=MUTED)
    para('<link href="https://foothold-project.vercel.app/research-20260928-v2-mvp-report" color="#0b6459">공개 종합보고서와 영상 보기</link> · 상세 조건과 전체 자료는 동봉한 종합보고서 참조',y+5,8.5,13,color=MUTED)
    c.save()
    doc=fitz.open(output);assert len(doc)==2
    for i,page in enumerate(doc):page.get_pixmap(matrix=fitz.Matrix(1.5,1.5)).save(ROOT/f'qa/summary-{i+1:02}.png')
    evidence.insert(0,{'path':sweep.relative_to(REPO).as_posix(),'sha256':hashlib.sha256(source_bytes(sweep)).hexdigest()})
    record={'rates_percent':rates,'cells':cells,'episodes_per_cell':100,'stepping_v2_percent':stones,'falls_per_64':falls,'slow010_tracked_vx':slow,'stairs':stairs,'sources':evidence,'summary_sha256':hashlib.sha256(output.read_bytes()).hexdigest(),'pages':2,'paragraph_bounds':bounds}
    (ROOT/'summary-evidence.json').write_text(json.dumps(record,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'pages':2,'rates':rates,'falls':falls,'last_text_bottom':max(b['bottom'] for b in bounds)},ensure_ascii=False))

if __name__=='__main__':main()
