"""Local stdio MCP client for reproducible Blender production. Not a UI-session claim."""
import json, os, subprocess, sys, threading, queue, time
from pathlib import Path
ROOT=Path(__file__).resolve().parent
env=os.environ.copy()
env['BLENDER_EXECUTABLE']='C:/Program Files/Blender Foundation/Blender 4.5/blender.exe'
server=Path(os.environ['LOCALAPPDATA'])/'Higgsfield/blender-mcp/node_modules/fnf-blender-mcp/dist/index.js'
p=subprocess.Popen(['C:/Program Files/nodejs/node.exe',str(server)],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,encoding='utf-8',env=env,creationflags=subprocess.CREATE_NO_WINDOW)
q=queue.Queue()
def read():
    for line in p.stdout:
        try:q.put(json.loads(line))
        except ValueError:pass
threading.Thread(target=read,daemon=True).start()
def errors():
    with (ROOT/'mcp-stderr.log').open('a',encoding='utf-8') as f:
        for line in p.stderr:f.write(line);f.flush()
threading.Thread(target=errors,daemon=True).start()
count=0
def call(method,params):
    global count
    count+=1
    p.stdin.write(json.dumps({'jsonrpc':'2.0','id':count,'method':method,'params':params})+'\n');p.stdin.flush()
    while True:
        r=q.get(timeout=600)
        if r.get('id')==count:return r
call('initialize',{'protocolVersion':'2025-03-26','capabilities':{},'clientInfo':{'name':'foothold-production','version':'1.0'}})
p.stdin.write(json.dumps({'jsonrpc':'2.0','method':'notifications/initialized'})+'\n');p.stdin.flush()
calls=json.loads(Path(sys.argv[1]).read_text(encoding='utf-8-sig'))
for idx,c in enumerate(calls):
    if 'code_file' in c:c['arguments']={'code':Path(c.pop('code_file')).read_text(encoding='utf-8')}
    r=call('tools/call',c)
    while r.get('result',{}).get('structuredContent',{}).get('state')=='running':
        job=r['result']['structuredContent']['job_id']
        time.sleep(2)
        r=call('tools/call',{'name':'bl_job_status','arguments':{'job_id':job}})
    (ROOT/f"mcp-{idx}-{c['name']}.json").write_text(json.dumps(r,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(r,ensure_ascii=False)[:14000],flush=True)
p.stdin.close()
try:p.wait(timeout=15)
except subprocess.TimeoutExpired:p.terminate()

