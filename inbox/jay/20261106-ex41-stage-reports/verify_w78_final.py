import csv
import hashlib
import importlib.util
import json
import re
import subprocess
from pathlib import Path
from html.parser import HTMLParser

root=Path(__file__).resolve().parent
import sys
sys.path.insert(0,str(root))
import compare_w78_final as c
import update_w78 as w

def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
files=[root/'RESULT-EX41-T0prime.md',root/'W18-W10-FINAL-NOTE.md',root/'README.md']
c.render_cached()
first={str(p):sha(p) for p in files}
c.render_cached()
assert first=={str(p):sha(p) for p in files},'render not idempotent'
rows=c.read_rows(root/'data/w78_5500_6000_comparison.csv')
assert len(rows)==120
for r in rows:
    assert abs(r['delta_R']-(r['R_6000']-r['R_5500']))<1e-12
    assert abs(r['delta_distance_m']-(r['distance_m_6000']-r['distance_m_5500']))<1e-12
    command=r['command']
    den=(command[0]**2+command[1]**2)**0.5*r['seconds']
    for n in (5500,6000):
        assert abs(r[f'R_{n}']*den-r[f'distance_m_{n}'])<1e-8
        assert 0<=r[f'alive_{n}']<=r['n']

class Tables(HTMLParser):
    def __init__(self):
        super().__init__();self.tables=[];self.table=None;self.row=None;self.head=False;self.heading_id=None;self.ids=[]
    def handle_starttag(self,tag,attrs):
        if tag=='table':self.table=[]
        if tag=='tr':self.row=0
        if tag in ('th','td') and self.row is not None:self.row+=1
        for k,v in attrs:
            if k=='id':self.ids.append(v)
    def handle_endtag(self,tag):
        if tag=='tr' and self.table is not None:self.table.append(self.row);self.row=None
        if tag=='table':self.tables.append(self.table);self.table=None

renders={}
for p in files:
    text=p.read_text(encoding='utf-8')
    assert '\u2014' not in text
    for target in re.findall(r'\]\(([^)]+)\)',text):
        if '://' in target or target.startswith('#'):continue
        plain=target.split('#')[0]
        assert (p.parent/plain).exists(), (p.name,plain)
    request=json.dumps({'text':text,'mode':'gfm','context':'foothold-project/foothold-lab'},ensure_ascii=False)
    done=subprocess.run(['gh','api','markdown','--input','-'],input=request,text=True,encoding='utf-8',capture_output=True,check=True)
    html=done.stdout
    (Path('D:/mai-tmp/analyst')/(p.stem+'-w18-render.html')).write_text(html,encoding='utf-8')
    parser=Tables();parser.feed(html)
    bad=[r for table in parser.tables for r in table if r!=table[0]]
    assert not bad,(p.name,bad)
    renders[p.name]={'tables':len(parser.tables),'broken_rows':len(bad),'sha256':sha(p),'html_sha256':hashlib.sha256(html.encode()).hexdigest()}
    if p.name=='RESULT-EX41-T0prime.md':
        assert 'm11500 → m12000: 같은 시험지에서 바뀐 것' in html

out={'known_answers':w.known_answers(),'comparison_rows':len(rows),'identity_ratio_distance_delta_survival':'pass',
     'render_idempotent':True,'local_links_exist':True,'github_gfm_render':renders,
     'scope':'CPU report verification; raw audit counts and source SHA in w78_m5500_audit.json and w78_m6000_audit.json'}
(root/'data/w78_final_verification.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps(out,ensure_ascii=False,indent=2))
