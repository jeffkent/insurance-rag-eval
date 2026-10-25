# Eval results

20 questions (17 answerable, 3 out of corpus). Questions written by the builder. Single run, k = 5.

## Retrieval (answerable questions only)

| Chunking | Mode | hit@1 | hit@5 | MRR | DB ms (mean) |
|---|---|---|---|---|---|
| A (1200 chars, no overlap) | vector | 0.47 | 0.76 | 0.608 | 3.5 |
| A (1200 chars, no overlap) | hybrid | 0.53 | 0.76 | 0.627 | 10.4 |
| B (600 chars, 100 overlap) | vector | 0.47 | 0.71 | 0.549 | 5.4 |
| B (600 chars, 100 overlap) | hybrid | 0.53 | 0.71 | 0.608 | 13.6 |

Best by MRR: A/hybrid. Worst: B/vector.

## Generation (glm-5.3:cloud, temperature 0, rule-based scoring)

| Retrieval config | Citation correct | False refusals | Refusal correct (out of corpus) | Errors | Retrieve ms | Generate s | Prompt tok (mean) | Output tok (mean) |
|---|---|---|---|---|---|---|---|---|
| A/hybrid (best) | 12/17 | 2/17 | 3/3 | 0 | 56 | 2.9 | 1390 | 233 |
| B/vector (worst) | 9/17 | 7/17 | 3/3 | 0 | 451 | 2.9 | 790 | 218 |
