"""M69 System-Prompt ablation scorer (A800). Fixed context (seed source), vary System
prompt {on=anti-hallucination, off=none}. Stores answers. Usage: python3 task3_sysabl.py <inst> <out> <model>"""
import json, sys, time, threading
from concurrent.futures import ThreadPoolExecutor
from openai import OpenAI
INST=sys.argv[1]; OUTF=sys.argv[2]; MODEL=sys.argv[3]; WORKERS=10
client=OpenAI(base_url="http://localhost:8000/v1", api_key="x", max_retries=0)
SYS_ON=("你是代码库跨文件依赖分析专家。严格遵守:1.只依据提供的上下文/代码作答,"
        "不使用记忆里的结构,不臆测;2.上下文里没有的信息明确说\"未包含\",绝不编造文件名/类名;"
        "3.结构化逐条列全。")
def call(ctx,q,sys_on):
    msgs=[]
    if sys_on: msgs.append({"role":"system","content":SYS_ON})
    msgs.append({"role":"user","content":f"{ctx}\n\n问题: {q}\n请列出相关的项目内依赖文件/模块(文件路径或模块名)。"})
    for a in range(6):
        try:
            r=client.chat.completions.create(model=MODEL,messages=msgs,temperature=0.0,max_tokens=400,timeout=90)
            return r.choices[0].message.content or ""
        except Exception as e:
            if a==5: return f"__ERR__ {e!r}"
            time.sleep(2*(a+1))
data=json.load(open(INST)); results=[]; lock=threading.Lock(); done=[0]
log=open(OUTF+".log","w")
def lg(*a): s=" ".join(str(x) for x in a); print(s,flush=True); log.write(s+"\n"); log.flush()
lg(f"[start] sysabl n={len(data)} model={MODEL}")
def work(inst):
    rec={"id":inst["id"],"keywords":inst["keywords"],"category":inst["category"],
         "context":inst["context"],"ans":{}}
    for tag,on in [("sys_on",True),("sys_off",False)]:
        rec["ans"][tag]=call(inst["context"],inst["question"],on)
    with lock:
        results.append(rec); done[0]+=1
        if done[0]%15==0: lg(f"  {done[0]}/{len(data)}"); json.dump(results,open(OUTF,"w"))
with ThreadPoolExecutor(max_workers=WORKERS) as ex: list(ex.map(work,data))
json.dump({"model":MODEL,"n":len(data),"results":results},open(OUTF,"w"),indent=1)
lg("[done]"); log.close()
