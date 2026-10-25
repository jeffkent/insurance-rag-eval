"""Retrieval: vector (cosine, HNSW) or hybrid (vector + Postgres full-text, reciprocal rank fusion).
Usage: .venv/bin/python -I search.py "question" [--config A|B] [--mode vector|hybrid] [--k 5]"""
import argparse, os, re, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common
from ingest import table

STOP = set("a an and are as at be by for from how in is it of on or that the this to what which who whom with does do did into than then there their they under per".split())
RRF_K = 60
POOL = 50


def fts_query(q):
    words = [w for w in re.findall(r"[A-Za-z0-9]+", q.lower()) if w not in STOP and len(w) > 1]
    return " | ".join(dict.fromkeys(words))


def vector_rows(cur, t, qvec, n):
    cur.execute("set hnsw.ef_search = 100")
    cur.execute(f"select id, doc, page, chunk_index, text, embedding <=> %s::vector as dist from {t} "
                f"order by embedding <=> %s::vector limit %s", (qvec, qvec, n))
    return cur.fetchall()


def fts_rows(cur, t, q, n):
    tq = fts_query(q)
    if not tq:
        return []
    cur.execute(f"select id, doc, page, chunk_index, text, ts_rank_cd(tsv, query) as r from {t}, "
                f"to_tsquery('english', %s) query where tsv @@ query order by r desc limit %s", (tq, n))
    return cur.fetchall()


def search(question, cfg="A", mode="hybrid", k=5, conn=None):
    """Returns (hits, timing). Each hit: dict(doc, page, chunk_index, text, score)."""
    t = table(cfg)
    t0 = time.time()
    vecs, n_tok = common.embed([question], "search_query: ")
    t_embed = time.time() - t0
    own = conn is None
    conn = conn or common.connect()
    try:
        with conn.cursor() as cur:
            t1 = time.time()
            vr = vector_rows(cur, t, common.vec_literal(vecs[0]), POOL if mode == "hybrid" else k)
            if mode == "vector":
                hits = [dict(id=r[0], doc=r[1], page=r[2], chunk_index=r[3], text=r[4], score=1 - float(r[5])) for r in vr]
            else:
                fr = fts_rows(cur, t, question, POOL)
                score, meta = {}, {}
                for rows in (vr, fr):
                    for rank, r in enumerate(rows, 1):
                        score[r[0]] = score.get(r[0], 0) + 1 / (RRF_K + rank)
                        meta[r[0]] = r
                top = sorted(score, key=score.get, reverse=True)[:k]
                hits = [dict(id=i, doc=meta[i][1], page=meta[i][2], chunk_index=meta[i][3], text=meta[i][4], score=score[i]) for i in top]
            t_db = time.time() - t1
    finally:
        if own:
            conn.close()
    return hits, {"embed_s": t_embed, "db_s": t_db, "embed_tokens": n_tok}


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("question")
    ap.add_argument("--config", default="A", choices=["A", "B"])
    ap.add_argument("--mode", default="hybrid", choices=["vector", "hybrid"])
    ap.add_argument("--k", type=int, default=5)
    a = ap.parse_args()
    hits, tm = search(a.question, a.config, a.mode, a.k)
    for i, h in enumerate(hits, 1):
        print(f"{i}. [{h['doc']}, p. {h['page']}] score={h['score']:.4f}\n   {h['text'][:200]}...")
    print(f"embed {tm['embed_s']*1000:.0f} ms, db {tm['db_s']*1000:.0f} ms")
