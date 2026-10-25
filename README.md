# insurance-rag-eval

A small retrieval-augmented generation (RAG) pipeline over 9 public regulator documents about AI governance in insurance, with a measured eval instead of a single demo query. It compares two chunking setups and vector vs hybrid search on 20 questions, and checks that every answer cites a document and page or says the answer is not in the documents.

Postgres + pgvector, local embeddings through Ollama, plain Python. No LangChain or LlamaIndex. I built it with AI coding agents under my direction; the questions, results and limits below are reported as measured.

## Architecture

1. `ingest.py` reads each PDF/HTML page, keeps the page number, and cuts the text into chunks.
2. Chunks are embedded with `nomic-embed-text` (local, via Ollama) using the `search_document:` prefix.
3. Postgres 18 with pgvector 0.8.7 stores text, a 768-d vector, and a `tsvector` column. One table per chunking config.
4. `search.py` runs vector search (cosine, HNSW index) or hybrid search (vector + full-text, merged by reciprocal rank fusion, k=60).
5. `ask.py` sends the top 5 passages to `glm-5.3:cloud` (through Ollama) with a system prompt that forces `[doc, p. N]` citations and "not in the documents" when the answer is absent.
6. `eval/run_eval.py` scores retrieval for four configs, then scores generation for the best and worst.

Plain Python (`psycopg`, `pypdf`, `requests`). No LangChain or LlamaIndex.

## Corpus

Nine documents from NY DFS, Colorado DOI, EIOPA, Bank of England and FCA. Titles, dates and URLs are in `docs/SOURCES.md`. The documents are not stored in this repo; `fetch_docs.sh` downloads them from the publishers. The NAIC documents could not be fetched (HTTP 403), so they are not in the corpus.

## Run it

Needs Postgres 16+ with the [pgvector](https://github.com/pgvector/pgvector) extension, Python 3.11+, and [Ollama](https://ollama.com) with `nomic-embed-text` pulled. Generation uses `glm-5.3:cloud` through Ollama by default; set `GEN_MODEL` to use another Ollama model.

```bash
./fetch_docs.sh                                   # downloads the 9 documents into docs/
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt

initdb -D pgdata -U rag --auth=trust
pg_ctl -D pgdata -o "-p 5544 -c listen_addresses=127.0.0.1" -l pg.log -w start
createdb -h 127.0.0.1 -p 5544 -U rag ragdemo
psql -h 127.0.0.1 -p 5544 -U rag ragdemo -c "create extension vector"

.venv/bin/python ingest.py                        # builds both chunking configs (about 9 min on an M-series Mac)
.venv/bin/python search.py "question" --config A --mode hybrid
.venv/bin/python ask.py "What is the maximum length of the Colorado compliance report?" --config A --mode hybrid
.venv/bin/python eval/run_eval.py                 # writes eval/results.md and eval/results.json
pg_ctl -D pgdata stop
```

Environment overrides: `RAG_DSN` (Postgres connection string), `OLLAMA_URL`, `GEN_MODEL`. Embedding and retrieval run fully local; generation with a `:cloud` model needs network access.

## Results

20 questions: 17 answerable, 3 out of corpus. Single run, k = 5, temperature 0.

Retrieval (answerable questions). A hit is any top-5 chunk from the expected document on an expected page.

| Chunking | Mode | hit@1 | hit@5 | MRR |
|---|---|---|---|---|
| A: 1200 chars, no overlap | vector | 0.47 | 0.76 | 0.608 |
| A: 1200 chars, no overlap | hybrid | 0.53 | 0.76 | 0.627 |
| B: 600 chars, 100 overlap | vector | 0.47 | 0.71 | 0.549 |
| B: 600 chars, 100 overlap | hybrid | 0.53 | 0.71 | 0.608 |

Generation, rule-based scoring (citation matches an expected doc+page; refusal means the answer contains "not in the documents"):

| Retrieval config | Citation correct | False refusals | Refusals on out-of-corpus | Mean generate time | Mean prompt tokens |
|---|---|---|---|---|---|
| A / hybrid (best by MRR) | 12 / 17 | 2 / 17 | 3 / 3 | 2.9 s | 1390 |
| B / vector (worst by MRR) | 9 / 17 | 7 / 17 | 3 / 3 | 2.9 s | 790 |

Full per-question output is in `eval/results.json`. Ingest stats are in `eval/ingest_stats.json`.

## What changed between configs, and why it matters

- Hybrid beat vector on hit@1 (0.53 vs 0.47) at both chunk sizes. Many questions hinge on exact terms such as "ECDIS", "LIME" or a percentage. Full-text matching helps there. Hybrid adds about 7 ms of database time per query.
- Larger chunks (A) beat smaller chunks (B) on hit@5 (0.76 vs 0.71). Small chunks can lose the context that makes a passage match.
- Chunk size changed answer quality more than retrieval scores suggest. With B/vector the model refused 7 of 17 answerable questions, because 600-character passages often did not hold the whole answer. With A/hybrid it refused 2 of 17.
- The retrieval gaps are small on 17 questions (one question is about 0.06). Treat the ranking of the four configs as a hint, not a result.

## Cost and latency

- Embeddings are local: no per-token cost. Ingest used 143,787 embedding tokens for config A (about 190 s) and 172,101 for config B (about 370 s). Building the HNSW and GIN indexes took under 0.5 s each.
- Query path: embedding about 40 ms, database 3 to 14 ms, generation about 3 s. Generation dominates.
- Generation tokens for the 20-question eval: A/hybrid 27,800 prompt and 4,660 output; B/vector 15,797 prompt and 4,362 output. Output tokens include any reasoning the model returns; I did not separate them.
- `ask.py` prints a dollar cost only if you set `PRICE_IN_PER_M` and `PRICE_OUT_PER_M`. I did not find a published price for `glm-5.3:cloud` and did not invent one.

## Known limits

- Small corpus: 9 documents, about 190 pages, 724 or 1,500 chunks. Vector search at this size would work without an index. The HNSW index shows the pattern, not a scaling test.
- The builder (Claude), not an independent labeler, wrote the 20 questions after reading the documents. Expected pages are looked up from a verbatim phrase in the extracted text (`eval/build_questions.py`), not typed by hand. Questions that quote one phrase can have other correct pages that the check does not count.
- Page numbers are PDF page indexes. The two Bank of England/FCA HTML pages are a single page each, so page matching is trivially satisfied for them.
- The FCA research note repeats statistics from the Bank of England survey. A correct passage from the "wrong" document counts as a miss.
- Chunks are cut within a page, so chunks never span pages and the mean chunk is shorter than the nominal size (A: 983 chars, B: 554).
- Single run, temperature 0, one generation model. No confidence intervals. Cloud model output can change between runs.
- Citation scoring is rule-based: it checks that a cited doc+page is expected, not that the answer is right. Refusal scoring looks for a fixed phrase.
- No reranker, no query rewriting, no prompt tuning. I did not tune anything against the eval questions.
- Text extraction uses `pypdf` with no OCR. Some hyphenation and spacing artifacts remain.
