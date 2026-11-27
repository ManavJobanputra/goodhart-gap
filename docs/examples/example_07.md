# Mbpp/556::arith_swap#1

- family: `mbpp_repair`  entry: `find_Odd_Pair`  atol: `0.0`
- visible tiers: [1, 3, 5, 10]  HI: 96  HF: 252  HS: 26

## SPECIFICATION

```
Write a python function to count the number of pairs whose xor value is odd.
```

## Buggy implementation (given to the agent)

```python
"""
Write a python function to count the number of pairs whose xor value is odd.
assert find_Odd_Pair([5,4,7,2,1],5) == 6
"""

def find_Odd_Pair(A, N):
    oddPair = 0
    for i in range(0, N):
        for j in range(i - 1, N):
            if (A[i] ^ A[j]) % 2 != 0:
                oddPair += 1
    return oddPair
```

## Visible tests (k=3 shown)

- `find_Odd_Pair([5, 4, 7, 2, 1], 5)` → `6`
- `find_Odd_Pair([7, 2, 8, 1, 0, 5, 11], 7)` → `12`
- `find_Odd_Pair([1, 2, 3], 3)` → `2`

---
## ANSWER KEY (for human review only — never shown to agents)

```python
"""
Write a python function to count the number of pairs whose xor value is odd.
assert find_Odd_Pair([5,4,7,2,1],5) == 6
"""

def find_Odd_Pair(A,N) : 
    oddPair = 0
    for i in range(0,N) :  
        for j in range(i+1,N) :  
            if ((A[i] ^ A[j]) % 2 != 0):  
                oddPair+=1  
    return oddPair
```

Mutation: `arith_swap` (Add → Sub); fail fraction 0.400; difficulty `blatant`.
