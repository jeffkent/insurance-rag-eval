"""Extract text per page, chunk (config A or B), embed with nomic-embed-text, store in Postgres.
Usage: .venv/bin/python -I ingest.py [--config A|B|all]"""
import argparse, json, os, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common


def table(cfg):
    return f"chunks_{cfg.lower()}"


def setup(cur, cfg):
    t = table(cfg)
    cur.execute("create extension if not exists vector")
    cur.execute(f"drop table if exists {t}")
    cur.execute(f"""create table {t} (
        id serial primary key, doc text not null, page int not null, chunk_index int not null,
        text text not null, embedding vector(768) not null,
        tsv tsvector generated always as (to_tsvector('english', text)) stored)""")


def ingest(cfg):
    c = common.CONFIGS[cfg]
    t = table(cfg)
    rows = []
    for path in common.doc_files():
        doc = os.path.splitext(os.path.basename(path))[0]
        idx = 0
        for page, text in common.extract_pages(path):
            for piece in common.chunk_text(text, c["size"], c["overlap"]):
                rows.append((doc, page, idx, piece))
                idx += 1
    print(f"config {cfg}: {len(rows)} chunks from {len(common.doc_files())} docs")
    t0, tokens, vecs = time.time(), 0, []
    for i in range(0, len(rows), 32):
        batch = rows[i:i + 32]
        v, n = common.embed([r[3] for r in batch], "search_document: ")
        vecs += v
        tokens += n
    embed_s = time.time() - t0
    with common.connect() as conn, conn.cursor() as cur:
        setup(cur, cfg)
        cur.executemany(
            f"insert into {t} (doc, page, chunk_index, text, embedding) values (%s,%s,%s,%s,%s::vector)",
            [(d, p, i, x, common.vec_literal(v)) for (d, p, i, x), v in zip(rows, vecs)])
        t1 = time.time()
        cur.execute(f"create index on {t} using hnsw (embedding vector_cosine_ops)")
        cur.execute(f"create index on {t} using gin (tsv)")
        index_s = time.time() - t1
    stats = {"config": cfg, "chunks": len(rows), "embed_prompt_tokens": tokens,
             "embed_seconds": round(embed_s, 1), "index_seconds": round(index_s, 2),
             "avg_chunk_chars": round(sum(len(r[3]) for r in rows) / len(rows))}
    print(json.dumps(stats))
    return stats


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="all", choices=["A", "B", "all"])
    a = ap.parse_args()
    out = [ingest(k) for k in (["A", "B"] if a.config == "all" else [a.config])]
    os.makedirs(os.path.join(common.HERE, "eval"), exist_ok=True)
    p = os.path.join(common.HERE, "eval", "ingest_stats.json")
    old = json.load(open(p)) if os.path.exists(p) else {}
    for s in out:
        old[s["config"]] = s
    json.dump(old, open(p, "w"), indent=2)
