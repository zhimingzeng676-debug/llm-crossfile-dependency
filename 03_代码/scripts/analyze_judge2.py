"""M9 第三层分析:同一批答案下,粗判定(judge1=比例式)vs 细判定(judge2=多维0-5)
各自测到的 CoT 增益。若细判定下 CoT 增益显著放大 → 原增益被粗判定吃掉了(评测分辨率问题);
若两者一致 → 排除该变量,增益的大小是真实的。

用法:python scripts/analyze_judge2.py
"""

import json
import sys
from pathlib import Path

from scipy import stats

sys.stdout.reconfigure(encoding="utf-8")
R = Path(__file__).resolve().parent.parent / "results"


def run_overalls(name, key):
    d = json.load(open(R / f"judge2_{name}.json", encoding="utf-8"))
    return [sum(c[key] for c in run) / len(run) for run in d["runs"]]


def hard_overalls(name, key):
    d = json.load(open(R / f"judge2_{name}.json", encoding="utf-8"))
    out = []
    for run in d["runs"]:
        hs = [c[key] for c in run if c["difficulty"] == "hard"]
        if hs:
            out.append(sum(hs) / len(hs))
    return out


def mean(xs):
    return sum(xs) / len(xs)


def gain(plain_name, cot_name, key, fn=run_overalls):
    p, c = fn(plain_name, key), fn(cot_name, key)
    t, pv = stats.ttest_ind(c, p, equal_var=False)
    return mean(p), mean(c), mean(c) - mean(p), pv


def main():
    print("=" * 72)
    print("M9 第三层:细粒度裁判是否揭示被粗判定吃掉的 CoT 增益")
    print("=" * 72)
    for label, key in [("judge1 比例式(实体命中)", "score1"),
                       ("judge2 细粒度多维(实体+关系+推理,0-5归一)", "score2")]:
        mp, mc, d, pv = gain("full_general", "pe_cot", key)
        hp, hc, hd, hpv = gain("full_general", "pe_cot", key, fn=hard_overalls)
        sig = "✅显著" if pv < 0.05 else "❌噪声内"
        hsig = "✅显著" if hpv < 0.05 else "❌噪声内"
        print(f"\n[{label}]")
        print(f"  overall: plain={mp:.4f}  +CoT={mc:.4f}  ΔCoT={d:+.4f}  p={pv:.4f}  {sig}")
        print(f"  hard   : plain={hp:.4f}  +CoT={hc:.4f}  ΔCoT={hd:+.4f}  p={hpv:.4f}  {hsig}")


if __name__ == "__main__":
    main()
