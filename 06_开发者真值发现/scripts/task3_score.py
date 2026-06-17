"""
Task3 scorer (runs ON the A800; calls localhost vLLM OpenAI API).
For each instance x condition: model selects co-change files from a candidate pool;
score RECALL by static-visibility layer. Judge-independent (gold = git co-change).

Usage: python3 task3_score.py <instances.json> <out.json> <model_name> [conditions]
Robust: per-call try/except, timeout, checkpoint every 20, no silent skips.
"""
import json, re, os, sys, time, threading
from concurrent.futures import ThreadPoolExecutor
from openai import OpenAI
from collections import defaultdict

INST=sys.argv[1]; OUTF=sys.argv[2]; MODEL=sys.argv[3]
CONDS=(sys.argv[4].split(",") if len(sys.argv)>4 else ["no_card","static_card","static_card_humble"])
WORKERS=10
client=OpenAI(base_url="http://localhost:8000/v1", api_key="x", max_retries=0)

def build_prompt(inst, cond):
    seed=inst["seed"]; cands=inst["candidates"]
    L=[f"A developer is making a change starting from this Python file:",
       f"FILE: {seed}","","```python",inst["seed_code"],"```",""]
    if cond in ("static_card","static_card_humble","random_card","random_in_pool"):
        card={"random_card":inst.get("random_card"),
              "random_in_pool":inst.get("random_in_pool")}.get(cond) or inst["static_card"]
        L+=["Static dependency analysis for this file (from the repo's static analyzer):",
            card,""]
        if cond=="static_card_humble":
            L+=["NOTE: this static analysis may be INCOMPLETE — it cannot capture dynamic "
                "imports, runtime/plugin wiring, config coupling, or files that change together "
                "by convention. Consider candidates related for ANY reason, not only those listed.",""]
    elif cond=="filler_card":
        L+=["Background notes:", inst["filler_card"], ""]
    L+=["From the candidate files below, select ALL files a developer would most likely need to "
        "change TOGETHER with the file above to complete one coherent change (bug fix or feature).",
        "Output ONLY a JSON array of the exact candidate paths you select. No prose.","","Candidates:"]
    for i,c in enumerate(cands): L.append(f"{i+1}. {c}")
    return "\n".join(L)

def parse_pred(text, cands):
    cset=set(cands); picked=set()
    m=re.search(r"\[.*\]", text, re.S)
    if m:
        try:
            for x in json.loads(m.group(0)):
                if isinstance(x,str) and x in cset: picked.add(x)
        except Exception: pass
    if not picked:
        for c in cands:
            if re.search(re.escape(c), text): picked.add(c)
    return picked

def call(prompt):
    for attempt in range(6):
        try:
            r=client.chat.completions.create(model=MODEL,
                messages=[{"role":"user","content":prompt}],
                temperature=0.0, max_tokens=512, timeout=90)
            return r.choices[0].message.content or ""
        except Exception as e:
            if attempt==5: return f"__ERR__ {e!r}"
            time.sleep(2*(attempt+1))  # backoff 2,4,6,8,10s

insts=json.load(open(INST))
results=[]
# aggregate: cond -> layer -> [recalled, total]
agg={c:defaultdict(lambda:[0,0]) for c in CONDS}
log=open(OUTF+".log","w")
def lg(*a):
    s=" ".join(str(x) for x in a); print(s,flush=True); log.write(s+"\n"); log.flush()

lg(f"[start] instances={len(insts)} model={MODEL} conds={CONDS} workers={WORKERS}")
lock=threading.Lock(); done=[0]

def work(inst):
    rec={"project":inst["project"],"seed":inst["seed"],"preds":{}}
    for cond in CONDS:
        out=call(build_prompt(inst,cond))
        pred=parse_pred(out, inst["candidates"])
        rec["preds"][cond]=sorted(pred)
        rec.setdefault("_err",[])
        if out.startswith("__ERR__"): rec["_err"].append(f"{cond}:{out[:80]}")
    with lock:
        results.append(rec)
        for cond in CONDS:
            pred=set(rec["preds"][cond])
            for g in inst["gold"]:
                agg[cond][g["layer"]][1]+=1
                if g["file"] in pred: agg[cond][g["layer"]][0]+=1
        done[0]+=1
        if rec.get("_err"): lg(f"  [callerr] {rec['seed']} {rec['_err']}")
        if done[0]%40==0:
            lg(f"  {done[0]}/{len(insts)}")
            json.dump({"results":results,"agg":{c:{l:v for l,v in d.items()} for c,d in agg.items()}},
                      open(OUTF,"w"),indent=1)

with ThreadPoolExecutor(max_workers=WORKERS) as ex:
    list(ex.map(work, insts))

summary={c:{l:{"recalled":v[0],"total":v[1],"recall":round(v[0]/v[1],4) if v[1] else None}
            for l,v in d.items()} for c,d in agg.items()}
json.dump({"model":MODEL,"n_instances":len(insts),"results":results,"summary":summary},
          open(OUTF,"w"),indent=1)
lg("\n=== RECALL by condition x layer ===")
layers=sorted({l for d in agg.values() for l in d})
for c in CONDS:
    lg(f"  [{c}]")
    for l in layers:
        v=agg[c].get(l,[0,0])
        lg(f"    {l:24} recall={round(v[0]/v[1],4) if v[1] else None}  ({v[0]}/{v[1]})")
lg("[done]")
log.close()
