"""Retrieve top passages, ask glm-5.3:cloud via Ollama, print answer, citations, latency and tokens.
Usage: .venv/bin/python -I ask.py "question" [--config A|B] [--mode vector|hybrid]
Optional cost: set PRICE_IN_PER_M and PRICE_OUT_PER_M (USD per million tokens) to see a cost line."""
import argparse, os, re, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import requests
import common
from search import search

SYSTEM = ("You answer questions about insurance AI regulation. Answer only from the numbered passages. "
          "Cite every claim as [doc, p. N] using the doc and page shown in the passage header. "
          "If the passages do not contain the answer, reply exactly: not in the documents. "
          "Keep the answer short.")


def build_prompt(question, hits):
    ctx = "\n\n".join(f"Passage {i} [{h['doc']}, p. {h['page']}]\n{h['text']}" for i, h in enumerate(hits, 1))
    return f"{ctx}\n\nQuestion: {question}"


def parse_citations(answer):
    """Return set of (doc, page) from citations like [doc, p. 5] or [doc, pp. 5, 6]."""
    out = set()
    for body in re.findall(r"\[([^\[\]]+)\]", answer):
        m = re.match(r"\s*([^,]+?)\s*,\s*pp?\.\s*(.+)$", body)
        if m:
            for pg in re.findall(r"\d+", m.group(2)):
                out.add((m.group(1).strip(), int(pg)))
    return out


def answer(question, cfg="A", mode="hybrid", k=5, conn=None):
    t0 = time.time()
    hits, tm = search(question, cfg, mode, k, conn)
    t_ret = time.time() - t0
    t1 = time.time()
    r = requests.post(f"{common.OLLAMA}/api/chat", json={
        "model": common.GEN_MODEL, "stream": False, "options": {"temperature": 0},
        "messages": [{"role": "system", "content": SYSTEM}, {"role": "user", "content": build_prompt(question, hits)}]},
        timeout=300)
    r.raise_for_status()
    j = r.json()
    t_gen = time.time() - t1
    text = (j.get("message", {}).get("content") or "").strip()
    return {"question": question, "answer": text, "hits": hits, "citations": sorted(parse_citations(text)),
            "retrieve_s": t_ret, "embed_s": tm["embed_s"], "generate_s": t_gen,
            "prompt_tokens": j.get("prompt_eval_count", 0), "output_tokens": j.get("eval_count", 0),
            "query_embed_tokens": tm["embed_tokens"]}


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("question")
    ap.add_argument("--config", default="A", choices=["A", "B"])
    ap.add_argument("--mode", default="hybrid", choices=["vector", "hybrid"])
    a = ap.parse_args()
    r = answer(a.question, a.config, a.mode)
    print("ANSWER:\n" + r["answer"] + "\n")
    print("RETRIEVED:")
    for i, h in enumerate(r["hits"], 1):
        print(f"  {i}. [{h['doc']}, p. {h['page']}]")
    print("CITED:", ", ".join(f"[{d}, p. {p}]" for d, p in r["citations"]) or "none")
    print(f"LATENCY: retrieve {r['retrieve_s']*1000:.0f} ms (query embedding {r['embed_s']*1000:.0f} ms), generate {r['generate_s']:.1f} s")
    print(f"TOKENS: prompt {r['prompt_tokens']}, output {r['output_tokens']}, query-embed {r['query_embed_tokens']}")
    pi, po = os.environ.get("PRICE_IN_PER_M"), os.environ.get("PRICE_OUT_PER_M")
    if pi and po:
        print(f"COST: ${(r['prompt_tokens']*float(pi)+r['output_tokens']*float(po))/1e6:.6f}")
    else:
        print("COST: not computed (set PRICE_IN_PER_M and PRICE_OUT_PER_M; embeddings are local and free)")
