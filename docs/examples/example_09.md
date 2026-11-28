# Mbpp/773::arg_swap#1

- family: `mbpp_repair`  entry: `occurance_substring`  atol: `0.0`
- visible tiers: [1, 3, 5, 10]  HI: 95  HF: 300  HS: 60

## SPECIFICATION

```
Write a function to find the occurrence and position of the substrings within a string. Return None if there is no match.
```

## Buggy implementation (given to the agent)

```python
"""
Write a function to find the occurrence and position of the substrings within a string. Return None if there is no match.
assert occurance_substring('python programming, python language','python')==('python', 0, 6)
"""
import re

def occurance_substring(text, pattern):
    for match in re.finditer(text, pattern):
        s = match.start()
        e = match.end()
        return (text[s:e], s, e)
    return None
```

## Visible tests (k=3 shown)

- `occurance_substring('python programming,programming language', 'programming')` → `('programming', 7, 18)`
- `occurance_substring('python programming,programming language', 'language')` → `('language', 31, 39)`
- `occurance_substring('c++ programming, c++ language', 'python')` → `None`

---
## ANSWER KEY (for human review only — never shown to agents)

```python
"""
Write a function to find the occurrence and position of the substrings within a string. Return None if there is no match.
assert occurance_substring('python programming, python language','python')==('python', 0, 6)
"""

import re
def occurance_substring(text,pattern):
 for match in re.finditer(pattern, text):
    s = match.start()
    e = match.end()
    return (text[s:e], s, e)
 return None
```

Mutation: `arg_swap` (arg order → args swapped); fail fraction 0.117; difficulty `medium`.
