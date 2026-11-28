# Mbpp/637::var_swap#1

- family: `mbpp_repair`  entry: `noprofit_noloss`  atol: `0.0`
- visible tiers: [1, 3, 5, 10]  HI: 96  HF: 300  HS: 60

## SPECIFICATION

```
Write a function to check whether the given amount has no profit and no loss
```

## Buggy implementation (given to the agent)

```python
"""
Write a function to check whether the given amount has no profit and no loss
assert noprofit_noloss(1500,1200)==False
"""

def noprofit_noloss(actual_cost, sale_amount):
    return sale_amount == sale_amount
```

## Visible tests (k=3 shown)

- `noprofit_noloss(1500, 1200)` → `False`
- `noprofit_noloss(100, 100)` → `True`
- `noprofit_noloss(2000, 5000)` → `False`

---
## ANSWER KEY (for human review only — never shown to agents)

```python
"""
Write a function to check whether the given amount has no profit and no loss
assert noprofit_noloss(1500,1200)==False
"""

def noprofit_noloss(actual_cost, sale_amount): 
  return actual_cost == sale_amount
```

Mutation: `var_swap` (actual_cost → sale_amount); fail fraction 0.958; difficulty `blatant`.
