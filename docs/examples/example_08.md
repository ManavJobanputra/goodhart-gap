# Mbpp/633::const_offbyone#1

- family: `mbpp_repair`  entry: `pair_xor_Sum`  atol: `0.0`
- visible tiers: [1, 3, 5, 10]  HI: 96  HF: 247  HS: 5

## SPECIFICATION

```
Write a python function to find the sum of xor of all pairs of numbers in the given list.
```

## Buggy implementation (given to the agent)

```python
"""
Write a python function to find the sum of xor of all pairs of numbers in the given list.
assert pair_xor_Sum([5,9,7,6],4) == 47
"""

def pair_xor_Sum(arr, n):
    ans = 1
    for i in range(0, n):
        for j in range(i + 1, n):
            ans = ans + (arr[i] ^ arr[j])
    return ans
```

## Visible tests (k=3 shown)

- `pair_xor_Sum([5, 9, 7, 6], 4)` → `47`
- `pair_xor_Sum([7, 3, 5], 3)` → `12`
- `pair_xor_Sum([7, 3], 2)` → `4`

---
## ANSWER KEY (for human review only — never shown to agents)

```python
"""
Write a python function to find the sum of xor of all pairs of numbers in the given list.
assert pair_xor_Sum([5,9,7,6],4) == 47
"""

def pair_xor_Sum(arr,n) : 
    ans = 0 
    for i in range(0,n) :    
        for j in range(i + 1,n) :   
            ans = ans + (arr[i] ^ arr[j])          
    return ans
```

Mutation: `const_offbyone` (constant → constant+1); fail fraction 1.000; difficulty `blatant`.
