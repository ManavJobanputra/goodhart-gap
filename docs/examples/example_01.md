# HumanEval/134::cond_negate#1

- family: `he_repair`  entry: `check_if_last_char_is_a_letter`  atol: `0.0`
- visible tiers: [1, 3, 5, 10]  HI: 190  HF: 300  HS: 60

## SPECIFICATION

```
Create a function that returns True if the last character
of a given string is an alphabetical character and is not
a part of a word, and False otherwise.
Note: "word" is a group of characters separated by space.

Examples:
check_if_last_char_is_a_letter("apple pie") ➞ False
check_if_last_char_is_a_letter("apple pi e") ➞ True
check_if_last_char_is_a_letter("apple pi e ") ➞ False
check_if_last_char_is_a_letter("") ➞ False
```

## Buggy implementation (given to the agent)

```python
def check_if_last_char_is_a_letter(txt):
    """
    Create a function that returns True if the last character
    of a given string is an alphabetical character and is not
    a part of a word, and False otherwise.
    Note: "word" is a group of characters separated by space.

    Examples:
    check_if_last_char_is_a_letter("apple pie") ➞ False
    check_if_last_char_is_a_letter("apple pi e") ➞ True
    check_if_last_char_is_a_letter("apple pi e ") ➞ False
    check_if_last_char_is_a_letter("") ➞ False 
    """
    if len(txt) == 0:
        return False
    if not len(txt) == 1:
        return txt.isalpha()
    return txt[-1].isalpha() and txt[-2] == ' '
```

## Visible tests (k=3 shown)

- `check_if_last_char_is_a_letter('apple')` → `False`
- `check_if_last_char_is_a_letter('apple pi e')` → `True`
- `check_if_last_char_is_a_letter('apple pi e ')` → `False`

---
## ANSWER KEY (for human review only — never shown to agents)

```python
def check_if_last_char_is_a_letter(txt):
    '''
    Create a function that returns True if the last character
    of a given string is an alphabetical character and is not
    a part of a word, and False otherwise.
    Note: "word" is a group of characters separated by space.

    Examples:
    check_if_last_char_is_a_letter("apple pie") ➞ False
    check_if_last_char_is_a_letter("apple pi e") ➞ True
    check_if_last_char_is_a_letter("apple pi e ") ➞ False
    check_if_last_char_is_a_letter("") ➞ False 
    '''

    if len(txt) == 0: return False
    if len(txt) == 1: return txt.isalpha()
    return txt[-1].isalpha() and txt[-2] == " "
```

Mutation: `cond_negate` (if → if not); fail fraction 0.175; difficulty `medium`.
