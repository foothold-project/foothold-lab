"""Explicit stdio MCP client for REA. Keeps full local evidence, prints no target secrets."""
import argparse, asyncio, json, os
from pathlib import Path

async def run(a):
    env = os.environ.copy()
    env["JAVA_HOME"] = "/home/jay/data/tools/jdk/jdk-21.0.13.1+2"
    env["PATH"] = env["JAVA_HOME"] + "/bin:" + env["PATH"]
    env["REA_JADX_MCP_JAR"] = "/home/jay/data/tools/dl/jadx-headless-mcp-0.7.1-all.jar"
    env["REA_APKTOOL_COMMAND"] = "/home/jay/data/tools/rea/apktool"
    env["REA_JADX_HEAP_MIB"] = "4096"
    env["TMPDIR"] = "/home/jay/data/go2-app-study-20261120/tmp"
    out = Path(a.output); out.parent.mkdir(parents=True, exist_ok=True)
    with out.with_suffix(".stderr.log").open("wb") as err:
        proc = await asyncio.create_subprocess_exec("/usr/bin/node", "/home/jay/.local/share/rea-mcp/node_modules/rea-agents/scripts/rea.mjs", "mcp", stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE, stderr=err, env=env, limit=64*1024*1024)
        async def rpc(i, method, params):
            proc.stdin.write((json.dumps({"jsonrpc":"2.0","id":i,"method":method,"params":params})+"\n").encode()); await proc.stdin.drain()
            while True:
                raw = await asyncio.wait_for(proc.stdout.readline(), timeout=a.timeout)
                if not raw: raise RuntimeError("MCP server closed before response")
                msg = json.loads(raw)
                if msg.get("id") == i: return msg
        init = await rpc(1,"initialize",{"protocolVersion":"2025-03-26","capabilities":{},"clientInfo":{"name":"foothold-apk-evidence","version":"1.0"}})
        proc.stdin.write(b'{"jsonrpc":"2.0","method":"notifications/initialized"}\n'); await proc.stdin.drain()
        if a.tool:
            args=json.loads(Path(a.args).read_text()) if a.args else {}
            result=await rpc(2,"tools/call",{"name":a.tool,"arguments":args})
        else: result=await rpc(2,"tools/list",{})
        out.write_text(json.dumps({"initialize":init,"response":result},ensure_ascii=False,indent=2))
        proc.stdin.close()
        await asyncio.wait_for(proc.wait(), timeout=20)
        print(json.dumps({"output":str(out),"server":init.get("result",{}).get("serverInfo"),"rpc_error":result.get("error"),"isError":result.get("result",{}).get("isError"),"returncode":proc.returncode}))
        if result.get("error") or result.get("result",{}).get("isError"): raise SystemExit(2)

if __name__ == "__main__":
    ap=argparse.ArgumentParser();ap.add_argument("--tool");ap.add_argument("--args");ap.add_argument("--output",required=True);ap.add_argument("--timeout",type=float,default=240);asyncio.run(run(ap.parse_args()))
