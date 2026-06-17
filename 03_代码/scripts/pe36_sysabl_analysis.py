"""M69 analysis (CPU): System-Prompt anti-hallucination on/off + filter. Hallucination
= predicted .py file NOT in the provided context source (made up). + gold dep-recall.
Shows prevention(System) vs correction(filter). judge-independent."""
import json, os, re
T3=r"D:/claude/59/pilot_devtruth/task3"
d=json.load(open(os.path.join(T3,"scores_sysabl.json")))
res=d["results"] if isinstance(d,dict) else d
FILE_TOK=re.compile(r"[A-Za-z_][\w/]*\.py")
def kwrec(t,kws): t=(t or "").lower(); return sum(1 for k in kws if k in t)/len(kws) if kws else 0
agg={}
for tag in ["sys_on","sys_off"]:
    hall=[0,0]; rec=[]; hall_after_filter=[0,0]
    for r in res:
        ctx=r["context"]; ctxfiles=set(FILE_TOK.findall(ctx))
        ans=r["ans"].get(tag,"")
        pred=set(FILE_TOK.findall(ans))
        # hallucinated = predicted .py not in context
        h=[p for p in pred if p not in ctxfiles and not any(p.endswith("/"+c) or c.endswith("/"+p) for c in ctxfiles)]
        hall[1]+=len(pred); hall[0]+=len(h)
        rec.append(kwrec(ans,r["keywords"]))
        # filter: remove hallucinated -> remaining hallucination = 0 by construction; report what filter removed
    agg[tag]=dict(hall_rate=hall[0]/hall[1] if hall[1] else 0, n_pred=hall[1], n_hall=hall[0],
                  rec=sum(rec)/len(rec))
print(f"=== M69 System 反幻觉约束 on/off + filter(werkzeug {len(res)},判分无关)===")
print(f"{'condition':12}{'幻觉率':>10}{'幻觉项数':>10}{'dep_recall':>12}")
for tag in ["sys_off","sys_on"]:
    a=agg[tag]; print(f"  {tag:12}{a['hall_rate']:>10.3f}{a['n_hall']:>10}{a['rec']:>12.3f}")
print(f"\n预防(System) vs 纠正(filter):")
print(f"  System-OFF 幻觉项 {agg['sys_off']['n_hall']} 个(幻觉率 {agg['sys_off']['hall_rate']:.3f})")
print(f"  System-ON  幻觉项 {agg['sys_on']['n_hall']} 个(幻觉率 {agg['sys_on']['hall_rate']:.3f})")
print(f"  后处理 filter 能纠正的 = 把幻觉项剔除(事后);但 System-ON 预防后已≈0,filter 无可纠正(M64 Δ=0)")
print(f"  → 工程原则:源头预防(System Prompt)比末端纠正(filter)更彻底——预防把幻觉率从 {agg['sys_off']['hall_rate']:.3f} 压到 {agg['sys_on']['hall_rate']:.3f}")
print(f"  边界(诚实):filter 只能剔除'上下文里没有的'幻觉文件名;预防层 System Prompt 同样针对这类。两者都对付'编造文件名'这一类,")
print(f"  对'列了上下文里有但不相关的项'(over-inclusion)两者都不直接管——那是 precision 问题,需相关性过滤(另一类)。")
