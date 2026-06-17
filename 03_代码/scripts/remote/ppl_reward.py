"""M24:RLCoder式ppl-reward。对每(query,candidate),算Qwen-14B对target的perplexity。
ppl低=候选好(RLCoder reward)。健康检查:argmin-ppl 是否=静态正确卡片(static_idx)。
用法:python3 ppl_reward.py rl_queries.jsonl rl_ppl.json <model>
"""
import json, sys, math, urllib.request
URL="http://localhost:8000/v1/completions"
def lp(prompt, model):
    body=json.dumps({"model":model,"prompt":prompt,"max_tokens":0,"echo":True,"logprobs":0,"temperature":0}).encode()
    for _ in range(4):
        try:
            req=urllib.request.Request(URL,data=body,headers={"Content-Type":"application/json"})
            with urllib.request.urlopen(req,timeout=120) as r:
                d=json.loads(r.read().decode())
                return d["choices"][0]["logprobs"]["token_logprobs"]
        except Exception as e:
            last=e
    return None
def main():
    qs=[json.loads(l) for l in open(sys.argv[1],encoding="utf-8") if l.strip()]
    out=sys.argv[2]; model=sys.argv[3]
    res=[]; hit=0
    for qi,q in enumerate(qs):
        prefix=lambda c: c["text"]+"\n\n问题:"+q["query"]+"\n答:"
        ppls=[]
        for c in q["candidates"]:
            pre=prefix(c); full=pre+q["target"]
            lpre=lp(pre,model); lfull=lp(full,model)
            if lpre is None or lfull is None: ppls.append(1e9); continue
            tgt=[x for x in lfull[len(lpre):] if x is not None]
            ppl=math.exp(-sum(tgt)/len(tgt)) if tgt else 1e9
            ppls.append(ppl)
        amin=min(range(len(ppls)),key=lambda i:ppls[i])
        ok=(amin==q["static_idx"])
        hit+=ok
        res.append({"qid":q["qid"],"ppls":ppls,"argmin":amin,"static_idx":q["static_idx"],"ppl_picks_static":ok})
        print(f"  [{qi+1}/{len(qs)}] {q['qid']} argmin={amin} static={q['static_idx']} {'HIT' if ok else 'miss'}",flush=True)
    agree=hit/len(qs)
    json.dump({"n":len(qs),"ppl_picks_static_rate":agree,"results":res},open(out,"w",encoding="utf-8"),ensure_ascii=False,indent=1)
    print(f"DONE ppl-reward。argmin-ppl=静态正确卡片 一致率 = {hit}/{len(qs)} = {agree:.1%}")
if __name__=="__main__": main()
