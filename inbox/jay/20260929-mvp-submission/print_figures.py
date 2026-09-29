"""원 SVG의 문구와 값을 읽어 A4 인쇄용 도식으로 재배치한다."""
from pathlib import Path
import xml.etree.ElementTree as ET
from html import escape
import json, re

ROOT=Path(__file__).resolve().parent
NS={'s':'http://www.w3.org/2000/svg'}
OUT=ROOT/'print-figures';OUT.mkdir(exist_ok=True)
INK='#161c26';DIM='#4a5566';GREEN='#0e7a6e';GOLD='#a86a08';RULE='#d9d6cd'
checks=[]

def source(name):
    root=ET.parse(ROOT/'source/media'/name).getroot()
    texts=[{'x':float(e.get('x',0)),'y':float(e.get('y',0)),'t':''.join(e.itertext())} for e in root.findall('.//s:text',NS)]
    return root,texts

def wrap(t,width,size):
    lines=[];line='';length=0
    for c in t:
        delta=size*(.53 if ord(c)<256 else 1)
        if length+delta>width and line:lines.append(line);line='';length=0
        line+=c;length+=delta
    if line:lines.append(line)
    return lines

class Figure:
    def __init__(self,name,width=800):self.name=name;self.width=width;self.items=[];self.used=[]
    def text(self,t,x,y,size=14,color=INK,bold=False,width=None):
        lines=wrap(t,width,size) if width else [t]
        self.used.append(t)
        self.items.append(f'<text x="{x}" y="{y}" font-size="{size}" fill="{color}" font-weight="{700 if bold else 400}">'+''.join(f'<tspan x="{x}" dy="{0 if i==0 else size*1.5}">{escape(line)}</tspan>' for i,line in enumerate(lines))+'</text>')
        return y+(len(lines)-1)*size*1.5
    def rect(self,x,y,w,h,fill,stroke='none'):
        self.items.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" fill="{fill}" stroke="{stroke}"/>')
    def finish(self,height,texts):
        missing=[x['t'] for x in texts if x['t'] not in self.used]
        assert not missing,(self.name,missing)
        svg=f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {self.width} {height}" width="{self.width}" height="{height}" font-family="Malgun Gothic, sans-serif">'+''.join(self.items)+'</svg>'
        (OUT/self.name).write_bytes(svg.encode())
        checks.append({'file':self.name,'source_texts':len(texts),'missing_texts':missing,'method':'원본 문구와 수치를 자동 추출하고 인쇄용으로 재배치'})

def next_step():
    name='v2-next-step.svg';root,ts=source(name);f=Figure(name)
    get=lambda x,y:next(t['t'] for t in ts if t['x']==x and t['y']==y)
    f.text(get(0,14),12,25,20,bold=True)
    f.text(get(0,33),12,53,14,color=DIM)
    f.rect(0,73,800,200,'#eeece6')
    f.text(get(12,78),18,101,17,bold=True);f.text(get(12,98),18,127,14,color=DIM)
    for i,y in enumerate(range(122,277,22)):
        x=18+(i//4)*392;yy=155+(i%4)*31
        f.rect(x-4,yy-19,376,27,'#e0f0ed' if i==7 else '#fff')
        f.text(get(20,y),x+5,yy,14,color=GREEN if i==7 else INK)
    f.text(get(272,276),595,248,13,color=GREEN)
    y=292
    for titlex,tx,titley,ys,title in [(330,342,y,range(99,260,40),get(330,78)),(648,660,582,range(99,220,40),get(648,78))]:
        f.text(title,18,titley+18,17,bold=True,color=GREEN if tx==342 else GOLD)
        yy=titley+49
        for sy in ys:
            f.rect(18,yy-15,3,35,GREEN if tx==342 else GOLD)
            f.text(get(tx,sy),30,yy,14,bold=True)
            f.text(get(tx,sy+15),235,yy,14,color=DIM,width=540)
            yy+=48
    y=842
    for sy in [380,398]:
        y=f.text(get(0,sy),12,y,14,color=DIM,width=772)+30
    f.finish(y,ts)
    full=ET.parse(OUT/name).getroot()
    for i,(top,height) in enumerate([(0,280),(280,300),(580,y-580)]):
        full.set('viewBox',f'0 {top} 800 {height}');full.set('height',str(height))
        ET.ElementTree(full).write(OUT/name.replace('.svg',f'-{i+1}.svg'),encoding='utf-8',xml_declaration=False)

def summary():
    name='v2-generalization-summary.svg';root,ts=source(name);f=Figure(name)
    for t in ts:
        x,y=t['x'],t['y']
        if y<60:
            if y==52:
                i=[16,75.6,168.2].index(x);xx=[12,150,330][i];color=[DIM,GOLD,GREEN][i]
                f.rect(xx,69,12,12,color);f.text(t['t'],xx+19,80,14)
            else:f.text(t['t'],12+x,25 if y==14 else 53,18 if y==14 else 14,bold=y==14)
    for i in range(4):
        bx=(i%2)*400;by=102+(i//2)*226
        f.rect(bx,by,386,211,'#f6f5f1',RULE)
        for t in ts:
            if 206*i<=t['x']<206*i+186 and 60<=t['y']<210:
                rel=t['x']-206*i;y=t['y']
                if y==78:f.text(t['t'],bx+14,by+27,15,bold=True)
                elif y in [99,134,169]:
                    row=[99,134,169].index(y);val=float(t['t']);color=[DIM,GOLD,GREEN][row]
                    f.rect(bx+14,by+48+row*39,2.8*val,17,color)
                    f.text(t['t'],bx+305,by+62+row*39,18,bold=True,color=color)
                elif y==196:f.text(t['t'],bx+(14 if rel<100 else 310),by+193,13,color=DIM)
    for t in ts:
        if t['y']>=210:f.text(t['t'],12,570,14,color=DIM,width=772)
    f.finish(622,ts)

def curve():
    name='v2-difficulty-curve.svg';root,ts=source(name);f=Figure(name)
    for t in ts:
        if t['y']<=56:
            if t['y']==56:
                i=[x for x in ts if x['y']==56].index(t);xx=[12,150,330][i]
                f.rect(xx,69,12,12,['#626f82',DIM,GREEN][i]);f.text(t['t'],xx+19,80,14)
            else:f.text(t['t'],12+t['x'],25 if t['y']==14 else 53,18 if t['y']==14 else 14,bold=t['y']==14)
    children=''.join(ET.tostring(e,encoding='unicode') for e in root).replace('#7c8798','#626f82')
    for i,x in enumerate([20,480]):
        f.items.append(f'<svg x="70" y="{98+i*426}" width="660" height="416" viewBox="{x} 70 450 340" overflow="hidden">{children}</svg>')
    for t in ts:
        if 70<=t['y']<=404:f.used.append(t['t'])
        elif t['y']>404:f.text(t['t'],12,975,14,color=DIM,width=772)
    f.finish(1040,ts)
    for i,x in enumerate([20,480]):
        part=Figure(name.replace('.svg',f'-{i+1}.svg'))
        for t in ts:
            if t['y'] in [14,33]:part.text(t['t'],12,25 if t['y']==14 else 53,18 if t['y']==14 else 14,bold=t['y']==14)
            elif t['y']==56:
                j=[z for z in ts if z['y']==56].index(t);xx=[12,150,330][j]
                part.rect(xx,69,12,12,['#626f82',DIM,GREEN][j]);part.text(t['t'],xx+19,80,14)
        part.items.append(f'<svg x="20" y="98" width="760" height="574.222" viewBox="{x} 70 450 340" overflow="hidden"><defs><clipPath id="panel"><rect x="{x}" y="70" width="450" height="340"/></clipPath></defs><g clip-path="url(#panel)">{children}</g></svg>')
        if i==1:
            for t in ts:
                if t['y']>404:part.text(t['t'],12,701,14,color=DIM,width=772)
        part.finish(754 if i else 689,[])

def lineage():
    name='v2-lineage.svg';root,ts=source(name);f=Figure(name)
    for t in ts:
        if t['y']<=52:f.text(t['t'],12,25 if t['y']==14 else 52 if t['y']==33 else 78,18 if t['y']==14 else 13,bold=t['y']==14)
    for i,y in enumerate(range(88,395,34)):
        row=[t for t in ts if t['y']==y];yy=115+i*33
        label,value,desc=row
        if i%2==0:f.rect(0,yy-21,800,32,'#f6f5f1')
        f.text(label['t'],12+i*2,yy,14,bold=True)
        f.rect(132,yy-11,float(value['t'])*2.5,11,GREEN if i not in [0,5] else DIM if i==0 else '#a3342a')
        f.text(value['t'],397,yy,14,color=GREEN,bold=True)
        f.text(desc['t'],465,yy,13,color=DIM,width=324)
    for t in ts:
        if t['y']>420:f.text(t['t'],12,455,13,color=DIM,width=772)
    f.finish(488,ts)

def terrain():
    name='v2-terrain-bars.svg';root,ts=source(name);f=Figure(name)
    get=lambda x,y:next(t['t'] for t in ts if t['x']==x and t['y']==y)
    f.text(get(0,14),12,25,20,bold=True);f.text(get(0,33),12,52,14,color=DIM)
    for i,x in enumerate([16,75.6,168.2]):
        xx=[12,150,330][i];f.rect(xx,67,12,12,[DIM,GOLD,GREEN][i]);f.text(get(x,52),xx+19,79,14)
    f.text(get(230,72),263,104,13,color=DIM);f.text(get(550,72),535,104,13,color=DIM)
    bars=[e for e in root.findall('s:rect',NS) if float(e.get('x',0))==231 and e.get('rx')=='1.5']
    for i,y in enumerate(range(93,469,25)):
        yy=131+i*33
        if i%2==0:f.rect(0,yy-23,800,32,'#f6f5f1')
        f.text(get(0,y),8,yy,12,color=GREEN,width=63)
        f.text(get(74,y),80,yy,13)
        for j,e in enumerate(bars[i*3:i*3+3]):f.rect(268,yy-19+j*8,float(e.get('width'))*.92,5,[DIM,GOLD,GREEN][j])
        for x,xx in [(604,577),(622,620),(682,647),(750,715)]:f.text(get(x,y),xx,yy,13,color=GREEN if x>=682 else DIM,bold=x==682)
    f.text(get(0,516),12,682,14,color=DIM,width=772)
    f.finish(720,ts)
    full=ET.parse(OUT/name).getroot()
    children=''.join(ET.tostring(e,encoding='unicode') for e in full)
    for number,top,height in [(1,105,267),(2,372,348)]:
        total=105+height
        svg=f'<svg xmlns="http://www.w3.org/2000/svg" width="800" height="{total}" viewBox="0 0 800 {total}" font-family="Malgun Gothic, sans-serif"><svg width="800" height="105" viewBox="0 0 800 105" overflow="hidden">{children}</svg><svg y="105" width="800" height="{height}" viewBox="0 {top} 800 {height}" overflow="hidden">{children}</svg></svg>'
        (OUT/name.replace('.svg',f'-{number}.svg')).write_bytes(svg.encode())

def blown():
    name='v2-blown-runs.svg';root,ts=source(name);f=Figure(name)
    get=lambda x,y:next(t['t'] for t in ts if t['x']==x and t['y']==y)
    for t in ts:
        if t['y']<=52:f.text(t['t'],12,25 if t['y']==14 else 52 if t['y']==33 else 78,18 if t['y']==14 else 14,bold=t['y']==14,width=772)
    for x,xx in [(0,12),(126,215),(164,265),(206,322)]:f.text(get(x,80),xx,112,13,bold=True)
    for i,y in enumerate(range(101,362,26)):
        yy=146+i*24
        if i%2==0:f.rect(0,yy-18,800,23,'#f6f5f1')
        for x,xx in [(0,12),(126,215),(164,265),(206,322)]:f.text(get(x,y),xx,yy,13)
        val=get(600,y);status=get(610,y);color=GREEN if status=='완주' else '#a3342a'
        f.rect(387,yy-11,280,9,'#eeece6');f.rect(387,yy-11,280*int(val)/3000,9,color)
        f.text(val,681,yy,14,color=color,bold=True);f.text(status,733,yy,13,color=color)
    yy=434
    for y in [407,421,436]:
        t=next(t['t'] for t in ts if t['y']==y);yy=f.text(t,12,yy,14,color=DIM,width=772)+31
    f.finish(yy,ts)
    full=ET.parse(OUT/name).getroot()
    for i,(top,height) in enumerate([(0,409),(409,yy-409)]):
        full.set('viewBox',f'0 {top} 800 {height}');full.set('height',str(height))
        ET.ElementTree(full).write(OUT/name.replace('.svg',f'-{i+1}.svg'),encoding='utf-8',xml_declaration=False)

def main():
    next_step();summary();curve();terrain();blown();lineage()
    (ROOT/'print-figures-audit.json').write_text(json.dumps(checks,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(checks,ensure_ascii=False))

if __name__=='__main__':main()
