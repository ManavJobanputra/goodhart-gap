# Mbpp/261::return_default#0

- family: `mbpp_repair`  entry: `division_elements`  atol: `0.0`
- visible tiers: [1, 3, 5, 10]  HI: 94  HF: 284  HS: 60

## SPECIFICATION

```
Write a function that takes in two tuples and performs mathematical division operation element-wise across the given tuples.
```

## Buggy implementation (given to the agent)

```python
"""
Write a function that takes in two tuples and performs mathematical division operation element-wise across the given tuples.
assert division_elements((10, 4, 6, 9),(5, 2, 3, 3)) == (2, 2, 2, 3)
"""

def division_elements(test_tup1, test_tup2):
    return 0
```

## Visible tests (k=3 shown)

- `division_elements((10, 4, 6, 9), (5, 2, 3, 3))` → `(2.0, 2.0, 2.0, 3.0)`
- `division_elements((12, 6, 8, 16), (6, 3, 4, 4))` → `(2.0, 2.0, 2.0, 4.0)`
- `division_elements((20, 14, 36, 18), (5, 7, 6, 9))` → `(4.0, 2.0, 6.0, 2.0)`

---
## ANSWER KEY (for human review only — never shown to agents)

```python
"""
Write a function that takes in two tuples and performs mathematical division operation element-wise across the given tuples.
assert division_elements((10, 4, 6, 9),(5, 2, 3, 3)) == (2, 2, 2, 3)
"""

def division_elements(test_tup1, test_tup2):
  return tuple(ele1 / ele2 for ele1, ele2 in zip(test_tup1, test_tup2))
```

Mutation: `return_default` (return expr → return 0); fail fraction 1.000; difficulty `blatant`.
