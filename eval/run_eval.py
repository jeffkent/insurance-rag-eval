"""Retrieval eval for 4 configs (chunking A/B x vector/hybrid), then generation eval for best and worst.
Usage: .venv/bin/python -I eval/run_eval.py"""
import json, os, statistics, sys
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
import common
from search import search
from ask import answer

QS = [json.loads(l) for l in open(os.path.join(HERE, "eval", "questions.jsonl"))]
K = 5
stem = lambda f: os.path.splitext(f)[0]


def is_hit(h, q):
    return h["doc"] == stem(q["expected_doc"]) and h["page"] in q["expected_pages"]


def retrieval(cfg, mode, conn):
    ranks, times = [], []
    for q in (x for x in QS if x["answerable"]):
        hits, tm = search(q["question"], cfg, mode, K, conn)
        times.append(tm["db_s"])
        r = next((i for i, h in enumerate(hits, 1) if is_hit(h, q)), None)
        ranks.append({"id": q["id"], "rank": r})
    n = len(ranks)
    return {"config": cfg, "mode": mode, "n": n,
            "hit@1": sum(1 for r in ranks if r["rank"] == 1) / n,
            "hit@5": sum(1 for r in ranks if r["rank"]) / n,
            "mrr": sum(1 / r["rank"] for r in ranks if r["rank"]) / n,
            "db_ms_mean": 1000 * statistics.mean(times), "ranks": ranks}


def generation(cfg, mode, conn):
    rows = []
    for q in QS:
        try:
            r = answer(q["question"], cfg, mode, K, conn)
        except Exception as e:  # report failures, never hide them
            rows.append({"id": q["id"], "error": str(e)[:200]})
            continue
        refused = "not in the documents" in r["answer"].lower()
        row = {"id": q["id"], "answerable": q["answerable"], "refused": refused, "answer": r["answer"],
               "citations": r["citations"], "retrieve_s": r["retrieve_s"], "generate_s": r["generate_s"],
               "prompt_tokens": r["prompt_tokens"], "output_tokens": r["output_tokens"]}
        if q["answerable"]:
            row["citation_correct"] = any(d == stem(q["expected_doc"]) and p in q["expected_pages"] for d, p in r["citations"])
        else:
            row["refusal_correct"] = refused
        rows.append(row)
    ok = [r for r in rows if "error" not in r]
    ans = [r for r in ok if r["answerable"]]
    ooc = [r for r in ok if not r["answerable"]]
    return {"config": cfg, "mode": mode, "errors": len(rows) - len(ok),
            "citation_correct": f"{sum(r['citation_correct'] for r in ans)}/{len(ans)}",
            "false_refusals": f"{sum(r['refused'] for r in ans)}/{len(ans)}",
            "refusal_correct": f"{sum(r['refusal_correct'] for r in ooc)}/{len(ooc)}",
            "retrieve_ms_mean": 1000 * statistics.mean(r["retrieve_s"] for r in ok),
            "generate_s_mean": statistics.mean(r["generate_s"] for r in ok),
            "prompt_tokens_mean": statistics.mean(r["prompt_tokens"] for r in ok),
            "output_tokens_mean": statistics.mean(r["output_tokens"] for r in ok),
            "prompt_tokens_total": sum(r["prompt_tokens"] for r in ok),
            "output_tokens_total": sum(r["output_tokens"] for r in ok), "rows": rows}


if __name__ == "__main__":
    conn = common.connect()
    ret = [retrieval(c, m, conn) for c in ("A", "B") for m in ("vector", "hybrid")]
    order = sorted(ret, key=lambda r: (r["mrr"], r["hit@5"]), reverse=True)
    best, worst = order[0], order[-1]
    gen = [generation(r["config"], r["mode"], conn) for r in (best, worst)]
    json.dump({"retrieval": ret, "generation": gen, "k": K, "questions": len(QS)},
              open(os.path.join(HERE, "eval", "results.json"), "w"), indent=2)
    L = ["# Eval results", "", f"{len(QS)} questions ({sum(q['answerable'] for q in QS)} answerable, "
         f"{sum(not q['answerable'] for q in QS)} out of corpus). Questions written by the builder. Single run, k = {K}.", "",
         "## Retrieval (answerable questions only)", "",
         "| Chunking | Mode | hit@1 | hit@5 | MRR | DB ms (mean) |", "|---|---|---|---|---|---|"]
    for r in ret:
        L.append(f"| {r['config']} ({'1200 chars, no overlap' if r['config']=='A' else '600 chars, 100 overlap'}) | {r['mode']} | "
                 f"{r['hit@1']:.2f} | {r['hit@5']:.2f} | {r['mrr']:.3f} | {r['db_ms_mean']:.1f} |")
    L += ["", f"Best by MRR: {best['config']}/{best['mode']}. Worst: {worst['config']}/{worst['mode']}.", "",
          "## Generation (glm-5.3:cloud, temperature 0, rule-based scoring)", "",
          "| Retrieval config | Citation correct | False refusals | Refusal correct (out of corpus) | Errors | Retrieve ms | Generate s | Prompt tok (mean) | Output tok (mean) |",
          "|---|---|---|---|---|---|---|---|---|"]
    for g, tag in zip(gen, ("best", "worst")):
        L.append(f"| {g['config']}/{g['mode']} ({tag}) | {g['citation_correct']} | {g['false_refusals']} | {g['refusal_correct']} | {g['errors']} | "
                 f"{g['retrieve_ms_mean']:.0f} | {g['generate_s_mean']:.1f} | {g['prompt_tokens_mean']:.0f} | {g['output_tokens_mean']:.0f} |")
    open(os.path.join(HERE, "eval", "results.md"), "w").write("\n".join(L) + "\n")
    print("\n".join(L))
