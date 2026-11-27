# HumanEval/0::cmp_flip#1

- family: `he_repair`  entry: `has_close_elements`  atol: `0.0`
- visible tiers: [1, 3, 5, 10]  HI: 190  HF: 300  HS: 60

## SPECIFICATION

```
Check if in given list of numbers, are any two numbers closer to each other than
given threshold.
>>> has_close_elements([1.0, 2.0, 3.0], 0.5)
False
>>> has_close_elements([1.0, 2.8, 3.0, 4.0, 5.0, 2.0], 0.3)
True
```

## Buggy implementation (given to the agent)

```python
from typing import List

def has_close_elements(numbers: List[float], threshold: float) -> bool:
    """ Check if in given list of numbers, are any two numbers closer to each other than
    given threshold.
    >>> has_close_elements([1.0, 2.0, 3.0], 0.5)
    False
    >>> has_close_elements([1.0, 2.8, 3.0, 4.0, 5.0, 2.0], 0.3)
    True
    """
    sorted_numbers = sorted(numbers)
    for i in range(len(sorted_numbers) - 1):
        if sorted_numbers[i + 1] - sorted_numbers[i] <= threshold:
            return True
    return False
```

## Visible tests (k=3 shown)

- `has_close_elements([1.0, 2.0, 5.9, 4.0, 5.0], 0.95)` → `True`
- `has_close_elements([1.1, 2.2, 3.1, 4.1, 5.1], 1.0)` → `True`
- `has_close_elements([1.0, 2.0, 3.0, 4.0, 5.0], 1.0)` → `False`

---
## ANSWER KEY (for human review only — never shown to agents)

```python
from typing import List


def has_close_elements(numbers: List[float], threshold: float) -> bool:
    """ Check if in given list of numbers, are any two numbers closer to each other than
    given threshold.
    >>> has_close_elements([1.0, 2.0, 3.0], 0.5)
    False
    >>> has_close_elements([1.0, 2.8, 3.0, 4.0, 5.0, 2.0], 0.3)
    True
    """


    sorted_numbers = sorted(numbers)
    for i in range(len(sorted_numbers) - 1):
        if sorted_numbers[i + 1] - sorted_numbers[i] < threshold:
            return True
    return False
```

Mutation: `cmp_flip` (Lt → LtE); fail fraction 0.025; difficulty `subtle`.
