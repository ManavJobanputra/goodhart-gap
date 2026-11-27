# Mbpp/75::arith_swap#0

- family: `mbpp_repair`  entry: `find_tuples`  atol: `0.0`
- visible tiers: [1, 3, 5, 10]  HI: 99  HF: 298  HS: 60

## SPECIFICATION

```
Write a function to find tuples which have all elements divisible by k from the given list of tuples.
```

## Buggy implementation (given to the agent)

```python
"""
Write a function to find tuples which have all elements divisible by k from the given list of tuples.
assert find_tuples([(6, 24, 12), (7, 9, 6), (12, 18, 21)], 6) == [(6, 24, 12)]
"""

def find_tuples(test_list, K):
    res = [sub for sub in test_list if all((ele // K == 0 for ele in sub))]
    return res
```

## Visible tests (k=3 shown)

- `find_tuples([[6, 24, 12], [7, 9, 6], [12, 18, 21]], 6)` → `[(6, 24, 12)]`
- `find_tuples([[5, 25, 30], [4, 2, 3], [7, 8, 9]], 5)` → `[(5, 25, 30)]`
- `find_tuples([[7, 9, 16], [8, 16, 4], [19, 17, 18]], 4)` → `[(8, 16, 4)]`

---
## ANSWER KEY (for human review only — never shown to agents)

```python
"""
Write a function to find tuples which have all elements divisible by k from the given list of tuples.
assert find_tuples([(6, 24, 12), (7, 9, 6), (12, 18, 21)], 6) == [(6, 24, 12)]
"""

def find_tuples(test_list, K):
  res = [sub for sub in test_list if all(ele % K == 0 for ele in sub)]
  return res
```

Mutation: `arith_swap` (Mod → FloorDiv); fail fraction 0.533; difficulty `blatant`.
