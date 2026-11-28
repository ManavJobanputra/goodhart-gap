# HumanEval/7::return_default#2

- family: `he_repair`  entry: `filter_by_substring`  atol: `0.0`
- visible tiers: [1, 3, 5, 10]  HI: 172  HF: 300  HS: 60

## SPECIFICATION

```
Filter an input list of strings only for ones that contain given substring
>>> filter_by_substring([], 'a')
[]
>>> filter_by_substring(['abc', 'bacd', 'cde', 'array'], 'a')
['abc', 'bacd', 'array']
```

## Buggy implementation (given to the agent)

```python
from typing import List

def filter_by_substring(strings: List[str], substring: str) -> List[str]:
    """ Filter an input list of strings only for ones that contain given substring
    >>> filter_by_substring([], 'a')
    []
    >>> filter_by_substring(['abc', 'bacd', 'cde', 'array'], 'a')
    ['abc', 'bacd', 'array']
    """
    return 0
```

## Visible tests (k=3 shown)

- `filter_by_substring(['xxx', 'asd', 'xxy', 'john doe', 'xxxAAA', 'xxx'], 'xxx')` → `['xxx', 'xxxAAA', 'xxx']`
- `filter_by_substring(['xxx', 'asd', 'aaaxxy', 'john doe', 'xxxAAA', 'xxx'], 'xx')` → `['xxx', 'aaaxxy', 'xxxAAA', 'xxx']`
- `filter_by_substring(['grunt', 'trumpet', 'prune', 'gruesome'], 'run')` → `['grunt', 'prune']`

---
## ANSWER KEY (for human review only — never shown to agents)

```python
from typing import List


def filter_by_substring(strings: List[str], substring: str) -> List[str]:
    """ Filter an input list of strings only for ones that contain given substring
    >>> filter_by_substring([], 'a')
    []
    >>> filter_by_substring(['abc', 'bacd', 'cde', 'array'], 'a')
    ['abc', 'bacd', 'array']
    """

    return list(filter(lambda s: substring in s, strings))
```

Mutation: `return_default` (return expr → return 0); fail fraction 1.000; difficulty `blatant`.
