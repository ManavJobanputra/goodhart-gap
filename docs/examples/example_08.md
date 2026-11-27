# Mbpp/638::arith_swap#0

- family: `mbpp_repair`  entry: `wind_chill`  atol: `0.0`
- visible tiers: [1, 3, 5, 10]  HI: 95  HF: 260  HS: 60

## SPECIFICATION

```
Write a function to calculate the wind chill index rounded to the next integer given the wind velocity in km/h and a temperature in celsius.
```

## Buggy implementation (given to the agent)

```python
"""
Write a function to calculate the wind chill index rounded to the next integer given the wind velocity in km/h and a temperature in celsius.
assert wind_chill(120,35)==40
"""
import math

def wind_chill(v, t):
    windchill = 13.12 - 0.6215 * t - 11.37 * math.pow(v, 0.16) + 0.3965 * t * math.pow(v, 0.16)
    return int(round(windchill, 0))
```

## Visible tests (k=3 shown)

- `wind_chill(120, 35)` → `40`
- `wind_chill(40, 20)` → `19`
- `wind_chill(10, 8)` → `6`

---
## ANSWER KEY (for human review only — never shown to agents)

```python
"""
Write a function to calculate the wind chill index rounded to the next integer given the wind velocity in km/h and a temperature in celsius.
assert wind_chill(120,35)==40
"""

import math
def wind_chill(v,t):
 windchill = 13.12 + 0.6215*t -  11.37*math.pow(v, 0.16) + 0.3965*t*math.pow(v, 0.16)
 return int(round(windchill, 0))
```

Mutation: `arith_swap` (Add → Sub); fail fraction 0.958; difficulty `blatant`.
