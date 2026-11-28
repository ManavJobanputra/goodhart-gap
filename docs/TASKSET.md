# TASKSET (generated)

Generated from `data/manifest.lock.json` by `scripts/gen_taskset.py`. Do not edit by hand.

- Build seed: `1729`
- Manifest content hash: `c528be372db6d8e8a9c28c1a0343aa127450c7aeb9b34acff6d9d73db818d1b2`
- Total tasks: **576**

## Counts by family

| family | tasks |
|---|---|
| he_repair | 197 |
| mbpp_repair | 379 |

## Counts by mutation operator

| operator | tasks |
|---|---|
| arg_swap | 22 |
| arith_swap | 60 |
| boolop_swap | 4 |
| break_remove | 1 |
| cmp_flip | 43 |
| cond_negate | 16 |
| const_offbyone | 113 |
| index_shift | 6 |
| loop_break | 9 |
| range_shift | 7 |
| return_default | 91 |
| stmt_delete | 60 |
| var_swap | 144 |

## Counts by difficulty

| difficulty | tasks |
|---|---|
| blatant | 403 |
| medium | 118 |
| subtle | 55 |

- Tasks with HS shortfall (< 60 shift cases): **73**
- Skipped sources: **21**

## Quota compliance (review D-005)

- medium+subtle fraction: **0.300** (floor 0.3, met)
- max per-operator fraction: **0.250** (cap 0.25, met)
- candidate pool size: **1530**

