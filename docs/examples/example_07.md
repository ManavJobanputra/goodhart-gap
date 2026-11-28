# Mbpp/559::stmt_delete#0

- family: `mbpp_repair`  entry: `max_sub_array_sum`  atol: `0.0`
- visible tiers: [1, 3, 5, 10]  HI: 102  HF: 245  HS: 31

## SPECIFICATION

```
Write a function to find the sum of the largest contiguous sublist in the given list.
```

## Buggy implementation (given to the agent)

```python
"""
Write a function to find the sum of the largest contiguous sublist in the given list.
assert max_sub_array_sum([-2, -3, 4, -1, -2, 1, 5, -3], 8) == 7
"""

def max_sub_array_sum(a, size):
    max_so_far = 0
    max_ending_here = 0
    for i in range(0, size):
        max_ending_here = max_ending_here + a[i]
        if max_ending_here < 0:
            max_ending_here = 0
        elif max_so_far < max_ending_here:
            pass
    return max_so_far
```

## Visible tests (k=3 shown)

- `max_sub_array_sum([-2, -3, 4, -1, -2, 1, 5, -3], 8)` → `7`
- `max_sub_array_sum([-3, -4, 5, -2, -3, 2, 6, -4], 8)` → `8`
- `max_sub_array_sum([-4, -5, 6, -3, -4, 3, 7, -5], 8)` → `10`

---
## ANSWER KEY (for human review only — never shown to agents)

```python
"""
Write a function to find the sum of the largest contiguous sublist in the given list.
assert max_sub_array_sum([-2, -3, 4, -1, -2, 1, 5, -3], 8) == 7
"""

def max_sub_array_sum(a, size):
  max_so_far = 0
  max_ending_here = 0
  for i in range(0, size):
    max_ending_here = max_ending_here + a[i]
    if max_ending_here < 0:
      max_ending_here = 0
    elif (max_so_far < max_ending_here):
      max_so_far = max_ending_here
  return max_so_far
```

Mutation: `stmt_delete` (Assign → pass); fail fraction 0.292; difficulty `medium`.
