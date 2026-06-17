"""
M57 open-generation scorer (runs on A800). Bypasses candidate-pool crowding:
model freely lists repo file paths that co-change with the seed (NO candidate pool).
Stores RAW output per instance; recall computed separately (pe17) by path matching.
Usage: python3 task3_opengen.py <instances.json> <out.json> <model> [cond]
cond: open_nocard (default) | open_staticcard
"""
import json, sys, time, threading
from concurrent.futures import ThreadPoolExecutor
from openai import OpenAI
INST=sys.argv[1]; OUTF=sys.argv[2]; MODEL=sys.argv[3]
COND=sys.argv[4] if len(sys.argv)>4 else "open_nocard"
WORKERS=10
client=OpenAI(base_url="http://localhost:8000/v1", api_key="x", max_retries=0)

def prompt(inst):
    L=[f"You are analyzing a Python repository. A developer is about to change this file:",
       f"FILE: {inst['seed']}","","```python",inst["seed_code"],"```",""]
    if COND.startswith("deg:") or COND.startswith("sweep:") or COND in ("open_staticcard","open_static_cochange","open_static_filler"):
        L+=["Static dependency analysis for this file (from the repo's static analyzer):",
            inst["static_card"],""]
        if COND=="open_static_cochange":
            L+=[inst["cochange_card"],""]
        elif COND=="open_static_filler":
            L+=["Background notes:", inst["filler_cc"], ""]
        elif COND.startswith("deg:"):
            L+=[inst["deg_cards"][COND[4:]],""]
        elif COND.startswith("sweep:"):
            L+=[inst["sweep_cards"][COND[6:]],""]
    L+=["List the repository file paths (relative to repo root, e.g. \"pkg/module.py\") that a "
        "developer would most likely need to change TOGETHER with the file above to complete one "
        "coherent change (bug fix or feature). Think about runtime/dynamic/plugin coupling too, not "
        "only direct imports.","Output ONLY a JSON array of repo-relative file paths (no prose, "
        "do not include the file above)."]
    return "\n".join(L)

def call(p):
    for a in range(6):
        try:
            r=client.chat.completions.create(model=MODEL,messages=[{"role":"user","content":p}],
                temperature=0.0,max_tokens=512,timeout=90)
            return r.choices[0].message.content or ""
        except Exception as e:
            if a==5: return f"__ERR__ {e!r}"
            time.sleep(2*(a+1))

insts=json.load(open(INST)); results=[]; lock=threading.Lock(); done=[0]
log=open(OUTF+".log","w")
def lg(*a):
    s=" ".join(str(x) for x in a); print(s,flush=True); log.write(s+"\n"); log.flush()
lg(f"[start] open-gen instances={len(insts)} model={MODEL} cond={COND}")
def work(inst):
    out=call(prompt(inst))
    rec={"project":inst["project"],"seed":inst["seed"],"raw":out,
         "gold":[{"file":g["file"],"layer":g["layer"]} for g in inst["gold"]],
         "err":out.startswith("__ERR__")}
    with lock:
        results.append(rec); done[0]+=1
        if done[0]%40==0: lg(f"  {done[0]}/{len(insts)}"); json.dump(results,open(OUTF,"w"))
with ThreadPoolExecutor(max_workers=WORKERS) as ex: list(ex.map(work,insts))
json.dump({"model":MODEL,"cond":COND,"n":len(insts),"results":results},open(OUTF,"w"),indent=1)
lg("[done]"); log.close()
