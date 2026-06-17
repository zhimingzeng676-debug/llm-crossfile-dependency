"""Generic context-position scorer (A800). Iterates ALL keys in inst['contexts'].
Usage: python3 task3_ctxgen.py <inst> <out> <model>"""
import json, sys, time, threading
from concurrent.futures import ThreadPoolExecutor
from openai import OpenAI
INST=sys.argv[1]; OUTF=sys.argv[2]; MODEL=sys.argv[3]; WORKERS=8
client=OpenAI(base_url="http://localhost:8000/v1", api_key="x", max_retries=0)
def call(ctx,q):
    p=f"{ctx}\n\n问题: {q}\n请仅根据上面提供的[依赖图卡片]作答,逐条列出相关的项目内依赖文件/模块。"
    for a in range(6):
        try:
            r=client.chat.completions.create(model=MODEL,messages=[{"role":"user","content":p}],
                temperature=0.0,max_tokens=400,timeout=120)
            return r.choices[0].message.content or ""
        except Exception as e:
            if a==5: return f"__ERR__ {e!r}"
            time.sleep(2*(a+1))
data=json.load(open(INST)); results=[]; lock=threading.Lock(); done=[0]
keys=list(data[0]["contexts"].keys())
log=open(OUTF+".log","w")
def lg(*a): s=" ".join(str(x) for x in a); print(s,flush=True); log.write(s+"\n"); log.flush()
lg(f"[start] ctxgen n={len(data)} keys={keys} model={MODEL}")
def work(inst):
    rec={"id":inst["id"],"keywords":inst["keywords"],"category":inst["category"],"ans":{}}
    for k in keys: rec["ans"][k]=call(inst["contexts"][k], inst["question"])
    with lock:
        results.append(rec); done[0]+=1
        if done[0]%10==0: lg(f"  {done[0]}/{len(data)}"); json.dump(results,open(OUTF,"w"))
with ThreadPoolExecutor(max_workers=WORKERS) as ex: list(ex.map(work,data))
json.dump({"model":MODEL,"n":len(data),"results":results},open(OUTF,"w"),indent=1)
lg("[done]"); log.close()
