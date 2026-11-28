# Mbpp/3::var_swap#2

- family: `mbpp_repair`  entry: `is_not_prime`  atol: `0.0`
- visible tiers: [1, 3, 5, 10]  HI: 98  HF: 207  HS: 60

## SPECIFICATION

```
Write a python function to identify non-prime numbers.
```

## Buggy implementation (given to the agent)

```python
"""
Write a python function to identify non-prime numbers.
assert is_not_prime(2) == False
"""
import math

def is_not_prime(n):
    if n == 1:
        return True
    for i in range(2, int(math.sqrt(n)) + 1):
        if i % i == 0:
            return True
    return False
```

## Visible tests (k=3 shown)

- `is_not_prime(2)` → `False`
- `is_not_prime(10)` → `True`
- `is_not_prime(37)` → `False`

---
## ANSWER KEY (for human review only — never shown to agents)

```python
"""
Write a python function to identify non-prime numbers.
assert is_not_prime(2) == False
"""

import math
def is_not_prime(n):
    if n == 1:
        return True
    for i in range(2, int(math.sqrt(n))+1):
        if n % i == 0:
            return True
    return False
```

Mutation: `var_swap` (n → i); fail fraction 0.092; difficulty `medium`.
