"""
M58 binary blind-spot WARNING scorer (runs on A800). For each code snippet, ask the
model a strict yes/no: does this code have a dependency that STATIC analysis would miss
(dynamic import / reflection / runtime binding / plugin)? Stores yes/no + raw.
Runs on field 'code' (original) or 'code_renamed' (memory test) via arg.
Usage: python3 task3_warn.py <dataset.json> <out.json> <model> [code|code_renamed]
"""
import json, sys, time, threading, re
from concurrent.futures import ThreadPoolExecutor
from openai import OpenAI
DS=sys.argv[1]; OUTF=sys.argv[2]; MODEL=sys.argv[3]
FIELD=sys.argv[4] if len(sys.argv)>4 else "code"
WORKERS=10
client=OpenAI(base_url="http://localhost:8000/v1", api_key="x", max_retries=0)

PROMPT=("You are auditing a Python function for STATIC-ANALYSIS BLIND SPOTS.\n"
"A static analyzer (parsing imports/calls) resolves normal `import X` and direct calls, "
"but MISSES dependencies created at runtime: dynamic import, reflection, plugin/registry "
"loading, config-driven dispatch, runtime binding.\n\n"
"Question: does THIS function create or rely on a dependency that a static import/call "
"analyzer would MISS (i.e., a dynamic/runtime/reflection dependency)?\n"
"Answer with a single token: YES or NO.\n\n```python\n{code}\n```\nAnswer (YES/NO):")

def call(code):
    p=PROMPT.format(code=code)
    for a in range(6):
        try:
            r=client.chat.completions.create(model=MODEL,messages=[{"role":"user","content":p}],
                temperature=0.0,max_tokens=8,timeout=60)
            return (r.choices[0].message.content or "").strip()
        except Exception as e:
            if a==5: return f"__ERR__ {e!r}"
            time.sleep(2*(a+1))

def parse_yesno(t):
    tl=t.lower()
    if t.startswith("__ERR__"): return None
    if re.search(r"\byes\b",tl): return 1
    if re.search(r"\bno\b",tl): return 0
    return None

data=json.load(open(DS)); results=[]; lock=threading.Lock(); done=[0]
log=open(OUTF+".log","w")
def lg(*a):
    s=" ".join(str(x) for x in a); print(s,flush=True); log.write(s+"\n"); log.flush()
lg(f"[start] warn n={len(data)} model={MODEL} field={FIELD}")
def work(d):
    raw=call(d[FIELD]); pred=parse_yesno(raw)
    with lock:
        results.append({"id":d["id"],"label":d["label"],"narrow_kw":d["narrow_kw"],
                        "tags":d["tags"],"pred":pred,"raw":raw,"err":raw.startswith("__ERR__")})
        done[0]+=1
        if done[0]%50==0: lg(f"  {done[0]}/{len(data)}"); json.dump(results,open(OUTF,"w"))
with ThreadPoolExecutor(max_workers=WORKERS) as ex: list(ex.map(work,data))
json.dump({"model":MODEL,"field":FIELD,"n":len(data),"results":results},open(OUTF,"w"),indent=1)
lg("[done]"); log.close()
