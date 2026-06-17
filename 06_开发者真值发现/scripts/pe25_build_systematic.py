"""
M63 Task1 (CPU): build degraded co-change cards over a FULL effective-coverage sweep
(0..1, NO max-1 floor) under TWO edge-selection regimes:
  - RANDOM: keep random c-fraction of invisible-gold partners (optimistic; M61 style)
  - SYSTEMATIC: keep TOP c-fraction by co-change support (= keep easy-to-mine, DROP the
    hardest-to-mine low-support edges first) — simulates real co-change mining bias.
Mineability proxy = evo co-change SUPPORT (#commits both files co-changed). Cards carry
ONLY kept invisible-gold partners, so cov=0 -> empty co-change card -> static floor.
HONEST: gold itself required support>=5 (evo primary), so truly-never-co-changed runtime
edges are EXCLUDED from gold -> both regimes understate the hardest real edges (flag).
co-change != dependency.
"""
import json, os, glob, hashlib
T3=r"D:\claude\59\pilot_devtruth\task3"; OUT=r"D:\claude\59\pilot_devtruth\out"
def hk(s): return hashlib.md5(s.encode()).hexdigest()

# evo support per pair
evo=json.load(open(sorted(glob.glob(os.path.join(OUT,"pe1_edges_primary_*.json")))[-1]))
support={}
for e in evo:
    support[(e["project"],frozenset((e["a"],e["b"])))]=e.get("support",0)

CARD_HDR=("Co-change history (files that historically change together with this file, "
          "from git history — may include runtime/dynamic coupling static analysis misses):\n")
COVS=[0.0,0.25,0.5,0.75,1.0]
insts=json.load(open(os.path.join(T3,"instances_mech.json")))  # has static_card, gold+layers
out=[]
for i in insts:
    seed=i["seed"]; proj=i["project"]
    inv=[g["file"] for g in i["gold"] if g["layer"].startswith("invisible")]
    # support per invisible partner (for systematic ordering); missing->0 (hardest)
    sup={f:support.get((proj,frozenset((seed,f))),0) for f in inv}
    by_support=sorted(inv, key=lambda f:(-sup[f], hk(seed+f)))   # high support first = easy to mine
    by_random =sorted(inv, key=lambda f:hk(seed+"rnd"+f))
    cards={}
    for c in COVS:
        k=int(round(len(inv)*c))
        keep_sys=set(by_support[:k]); keep_rnd=set(by_random[:k])
        def mk(keep):
            return (CARD_HDR+", ".join(sorted(keep, key=lambda f:hk(seed+"o"+f)))) if keep else "(no co-change history)"
        cards[f"sys_{int(c*100)}"]=mk(keep_sys)
        cards[f"rnd_{int(c*100)}"]=mk(keep_rnd)
    o={**i, "sweep_cards":cards, "n_inv":len(inv)}
    out.append(o)
json.dump(out, open(os.path.join(T3,"instances_sysdecay.json"),"w"), indent=1)
# report: at each cov, mean kept; and the support distribution (how much harder systematic drops)
import statistics
print(f"instances={len(out)}; invisible-gold edges total={sum(o['n_inv'] for o in out)}")
allsup=[support.get((o['project'],frozenset((o['seed'],g['file']))),0) for o in out for g in o['gold'] if g['layer'].startswith('invisible')]
print(f"invisible-gold support: min={min(allsup)} median={statistics.median(allsup)} max={max(allsup)} (all>=5 by gold construction)")
print(f"=> systematic drops the low-support tail first; truly-never-co-changed edges are NOT in gold (excluded by support>=5) -- both regimes understate hardest real edges.")
print("conditions:", [f"{r}_{int(c*100)}" for c in COVS for r in ("rnd","sys")])
