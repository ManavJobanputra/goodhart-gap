# Mbpp/139::var_swap#0

- family: `mbpp_repair`  entry: `circle_circumference`  atol: `0.0001`
- visible tiers: [1, 3, 5, 10]  HI: 94  HF: 300  HS: 60

## SPECIFICATION

```
Write a function to find the circumference of a circle.
```

## Buggy implementation (given to the agent)

```python
"""
Write a function to find the circumference of a circle.
assert math.isclose(circle_circumference(10), 62.830000000000005, rel_tol=0.001)
"""
import math

def circle_circumference(r):
    return 2 * r.pi * r
```

## Visible tests (k=3 shown)

- `circle_circumference(10)` → `62.83185307179586`
- `circle_circumference(5)` → `31.41592653589793`
- `circle_circumference(4)` → `25.132741228718345`

---
## ANSWER KEY (for human review only — never shown to agents)

```python
"""
Write a function to find the circumference of a circle.
assert math.isclose(circle_circumference(10), 62.830000000000005, rel_tol=0.001)
"""

import math
def circle_circumference(r):
  return 2 * math.pi * r
```

Mutation: `var_swap` (math → r); fail fraction 1.000; difficulty `blatant`.
