"""
M57 Task2 (CPU): decompose open-gen invisible recall into mundane signals vs residual.
For each invisible gold edge the model RECALLED (open-gen, basename caliber):
  - text_clue: does gold's module-stem/basename appear ANYWHERE in seed_code text
    (incl strings/comments/docstrings the static parser's edge didn't capture)?  => "read text"
  - filename_sim: filename token overlap seed<->gold > 0  => filename semantics
  - residual: neither => candidate memory / true intuition (needs rename test to split)
co-change != dependency. Honest: likely most is text-clue/filename, residual small.
"""
import json, os, re
T3=r"D:\claude\59\pilot_devtruth\task3"
insts={(i["project"],i["seed"]):i for i in json.load(open(os.path.join(T3,"instances_mech.json")))}
d=json.load(open(os.path.join(T3,"scores_opengen_nocard.json")))
results=d["results"] if isinstance(d,dict) else d

def toks(p):
    b=os.path.basename(p); b=b[:-3] if b.endswith(".py") else b
    return set(t for t in re.split(r"[_\W]+",b.lower()) if t)
def fsim(a,b): return bool(toks(a)&toks(b))
def stem(p):
    b=os.path.basename(p); return b[:-3] if b.endswith(".py") else b
def pred_base(raw):
    paths=set()
    m=re.search(r"\[.*\]",raw,re.S)
    if m:
        try:
            for x in json.loads(m.group(0)):
                if isinstance(x,str): paths.add(os.path.basename(x.strip()))
        except Exception: pass
    for t in re.findall(r"[\w./\\-]+\.py",raw): paths.add(os.path.basename(t))
    return paths

def text_clue(seed_code, gold):
    st=stem(gold)
    if len(st)<3: return False
    # module stem or dotted path appears as a token anywhere in seed text
    return re.search(r"\b"+re.escape(st)+r"\b", seed_code, re.I) is not None

buckets={"text_clue":0,"filename_only":0,"residual":0}
recalled=0; total_inv=0
res_examples=[]
for r in results:
    if r.get("err"): continue
    key=(r["project"],r["seed"]); inst=insts.get(key)
    if not inst: continue
    pb=pred_base(r["raw"]); seed=inst["seed"]; code=inst["seed_code"]
    for g in r["gold"]:
        if not g["layer"].startswith("invisible"): continue
        total_inv+=1
        if stem(g["file"])  in {s[:-3] if s.endswith('.py') else s for s in pb} or os.path.basename(g["file"]) in pb:
            recalled+=1
            tc=text_clue(code,g["file"]); fs=fsim(seed,g["file"])
            if tc: buckets["text_clue"]+=1
            elif fs: buckets["filename_only"]+=1
            else:
                buckets["residual"]+=1
                if len(res_examples)<12: res_examples.append((r["project"],seed,g["file"],g["layer"]))

print(f"=== open-gen invisible recall signal decomposition (basename caliber) ===")
print(f"  invisible gold total={total_inv}  recalled={recalled} ({recalled/total_inv:.3f})")
print(f"  of {recalled} recalled invisible edges:")
for k in ["text_clue","filename_only","residual"]:
    print(f"    {k:14} {buckets[k]} ({buckets[k]/recalled*100:.1f}%)")
print("\n  text_clue = gold module-stem appears in seed code text (read text, not intuition)")
print("  filename_only = no text clue but filename token overlap (filename semantics)")
print("  residual = neither => candidate memory/true-intuition (needs rename test to split)")
print("\n  --- residual examples (filename-dissimilar + no text clue) ---")
for p,s,g,l in res_examples: print(f"    [{p}] {s} -> {g} ({l})")
