# Mbpp/109::const_offbyone#0

- family: `mbpp_repair`  entry: `odd_Equivalent`  atol: `0.0`
- visible tiers: [1, 3, 5, 10]  HI: 95  HF: 269  HS: 6

## SPECIFICATION

```
Write a python function to find the number of numbers with an odd value when rotating a binary string the given number of times.
```

## Buggy implementation (given to the agent)

```python
"""
Write a python function to find the number of numbers with an odd value when rotating a binary string the given number of times.
assert odd_Equivalent("011001",6) == 3
"""

def odd_Equivalent(s, n):
    count = 1
    for i in range(0, n):
        if s[i] == '1':
            count = count + 1
    return count
```

## Visible tests (k=3 shown)

- `odd_Equivalent('011001', 6)` → `3`
- `odd_Equivalent('11011', 5)` → `4`
- `odd_Equivalent('1010', 4)` → `2`

---
## ANSWER KEY (for human review only — never shown to agents)

```python
"""
Write a python function to find the number of numbers with an odd value when rotating a binary string the given number of times.
assert odd_Equivalent("011001",6) == 3
"""

def odd_Equivalent(s,n): 
    count=0
    for i in range(0,n): 
        if (s[i] == '1'): 
            count = count + 1
    return count
```

Mutation: `const_offbyone` (constant → constant+1); fail fraction 1.000; difficulty `blatant`.
