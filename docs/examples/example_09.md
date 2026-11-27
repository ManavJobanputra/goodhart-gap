# Mbpp/757::const_offbyone#0

- family: `mbpp_repair`  entry: `count_reverse_pairs`  atol: `0.0`
- visible tiers: [1, 3, 5, 10]  HI: 103  HF: 300  HS: 60

## SPECIFICATION

```
Write a function to count the pairs of reverse strings in the given string list.
```

## Buggy implementation (given to the agent)

```python
"""
Write a function to count the pairs of reverse strings in the given string list. 
assert count_reverse_pairs(["julia", "best", "tseb", "for", "ailuj"])== 2
"""

def count_reverse_pairs(test_list):
    return sum((test_list[i + 2:].count(s[::-1]) for i, s in enumerate(test_list)))
```

## Visible tests (k=3 shown)

- `count_reverse_pairs(['julia', 'best', 'tseb', 'for', 'ailuj'])` → `2`
- `count_reverse_pairs(['geeks', 'best', 'for', 'skeeg'])` → `1`
- `count_reverse_pairs(['makes', 'best', 'sekam', 'for', 'rof'])` → `2`

---
## ANSWER KEY (for human review only — never shown to agents)

```python
"""
Write a function to count the pairs of reverse strings in the given string list. 
assert count_reverse_pairs(["julia", "best", "tseb", "for", "ailuj"])== 2
"""

def count_reverse_pairs(test_list):
  return sum(test_list[i+1:].count(s[::-1]) for i, s in enumerate(test_list))
```

Mutation: `const_offbyone` (constant → constant+1); fail fraction 0.308; difficulty `blatant`.
