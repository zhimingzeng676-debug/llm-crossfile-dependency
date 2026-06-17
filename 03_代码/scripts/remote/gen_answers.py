"""在远端 GPU 机上跑:读 prompts JSON,逐条调本机 vLLM(localhost,不过隧道),
写 answers JSON。纯标准库,无需装任何依赖。

用法(远端):python3 gen_answers.py <prompts.json> <answers.json> <model_name>
"""

import json
import sys
import time
import urllib.error
import urllib.request

URL = "http://localhost:8000/v1/chat/completions"


TEMP = float(sys.argv[4]) if len(sys.argv) > 4 else 0.0


def call(prompt, model, timeout=120):
    body = json.dumps({
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": TEMP,
        "max_tokens": 1024,
    }).encode("utf-8")
    for attempt in range(5):
        try:
            req = urllib.request.Request(URL, data=body, headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            return data["choices"][0]["message"]["content"]
        except Exception as e:
            if attempt < 4:
                time.sleep(2 * (attempt + 1))
                continue
            return f"(GEN_ERROR after retries: {e})"


def main():
    prompts_path, answers_path, model = sys.argv[1], sys.argv[2], sys.argv[3]
    prompts = json.load(open(prompts_path, encoding="utf-8"))
    answers = []
    t0 = time.time()
    for i, p in enumerate(prompts):
        ans = call(p["prompt"], model)
        answers.append({"id": p["id"], "answer": ans})
        if (i + 1) % 10 == 0:
            print(f"  {i + 1}/{len(prompts)} done ({time.time() - t0:.0f}s)", flush=True)
    json.dump(answers, open(answers_path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"DONE {len(answers)} answers -> {answers_path} ({time.time() - t0:.0f}s)")


if __name__ == "__main__":
    main()
