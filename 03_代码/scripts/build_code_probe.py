"""M15:构造通用代码能力探针(HumanEval 风格,~12 题),用于监控 DAPT 后的灾难性遗忘。
每题:prompt(函数签名+docstring) + test(assert 测试)。pass@1 = 生成代码能否通过 assert。
与 werkzeug/依赖问答无关——纯通用 Python 编码,测的是"通用代码能力是否退化"。

用法:python scripts/build_code_probe.py  → data/code_probe.jsonl
"""

import json
import sys

from _common import PROJECT_ROOT

sys.stdout.reconfigure(encoding="utf-8")

PROBES = [
    ("def is_palindrome(s: str) -> bool:\n    \"\"\"返回 s 是否为回文(忽略大小写,只看字母数字)。\"\"\"\n",
     "assert is_palindrome('A man a plan a canal Panama')\nassert not is_palindrome('hello')\nassert is_palindrome('')"),
    ("def fib(n: int) -> int:\n    \"\"\"返回第 n 个斐波那契数,fib(0)=0, fib(1)=1。\"\"\"\n",
     "assert fib(0)==0 and fib(1)==1\nassert fib(10)==55"),
    ("def two_sum(nums, target):\n    \"\"\"返回两个相加等于 target 的元素下标列表 [i,j],i<j。保证有解。\"\"\"\n",
     "assert sorted(two_sum([2,7,11,15],9))==[0,1]\nassert sorted(two_sum([3,2,4],6))==[1,2]"),
    ("def gcd(a: int, b: int) -> int:\n    \"\"\"返回 a 和 b 的最大公约数。\"\"\"\n",
     "assert gcd(12,8)==4\nassert gcd(17,5)==1\nassert gcd(0,5)==5"),
    ("def flatten(lst):\n    \"\"\"把任意嵌套的列表展平成一维列表。\"\"\"\n",
     "assert flatten([1,[2,[3,4]],5])==[1,2,3,4,5]\nassert flatten([])==[]"),
    ("def count_words(s: str) -> dict:\n    \"\"\"返回字符串中每个单词(按空白切分)出现次数的字典。\"\"\"\n",
     "assert count_words('a b a c a')=={'a':3,'b':1,'c':1}"),
    ("def is_prime(n: int) -> bool:\n    \"\"\"返回 n 是否为素数。\"\"\"\n",
     "assert is_prime(2) and is_prime(13)\nassert not is_prime(1) and not is_prime(15)"),
    ("def reverse_words(s: str) -> str:\n    \"\"\"翻转句子中单词的顺序,单词内部不变,单词间单空格。\"\"\"\n",
     "assert reverse_words('the sky is blue')=='blue is sky the'"),
    ("def merge_sorted(a, b):\n    \"\"\"合并两个升序列表为一个升序列表。\"\"\"\n",
     "assert merge_sorted([1,3,5],[2,4,6])==[1,2,3,4,5,6]\nassert merge_sorted([],[1])==[1]"),
    ("def char_freq_sorted(s: str):\n    \"\"\"返回字符按出现频次降序排列的列表(频次相同按字符升序)。\"\"\"\n",
     "assert char_freq_sorted('aabbbc')==['b','a','c']"),
    ("def roman_to_int(s: str) -> int:\n    \"\"\"罗马数字转整数(I,V,X,L,C,D,M)。\"\"\"\n",
     "assert roman_to_int('III')==3\nassert roman_to_int('MCMXCIV')==1994"),
    ("def max_subarray(nums):\n    \"\"\"返回连续子数组的最大和(Kadane)。\"\"\"\n",
     "assert max_subarray([-2,1,-3,4,-1,2,1,-5,4])==6\nassert max_subarray([-1])==-1"),
]


def main():
    out = PROJECT_ROOT / "data" / "code_probe.jsonl"
    with open(out, "w", encoding="utf-8") as fh:
        for i, (prompt, test) in enumerate(PROBES):
            fh.write(json.dumps({"id": f"P{i:02d}", "prompt": prompt, "test": test}, ensure_ascii=False) + "\n")
    print(f"{len(PROBES)} 题通用代码探针 -> {out}")


if __name__ == "__main__":
    main()
