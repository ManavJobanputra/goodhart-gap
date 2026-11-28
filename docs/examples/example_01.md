# HumanEval/133::const_offbyone#1

- family: `he_repair`  entry: `sum_squares`  atol: `0.0`
- visible tiers: [1, 3, 5, 10]  HI: 190  HF: 300  HS: 60

## SPECIFICATION

```
You are given a list of numbers.
You need to return the sum of squared numbers in the given list,
round each element in the list to the upper int(Ceiling) first.
Examples:
For lst = [1,2,3] the output should be 14
For lst = [1,4,9] the output should be 98
For lst = [1,3,5,7] the output should be 84
For lst = [1.4,4.2,0] the output should be 29
For lst = [-2.4,1,1] the output should be 6
```

## Buggy implementation (given to the agent)

```python
def sum_squares(lst):
    """You are given a list of numbers.
    You need to return the sum of squared numbers in the given list,
    round each element in the list to the upper int(Ceiling) first.
    Examples:
    For lst = [1,2,3] the output should be 14
    For lst = [1,4,9] the output should be 98
    For lst = [1,3,5,7] the output should be 84
    For lst = [1.4,4.2,0] the output should be 29
    For lst = [-2.4,1,1] the output should be 6
    

    """
    import math
    return sum(map(lambda x: math.ceil(x) ** 3, lst))
```

## Visible tests (k=3 shown)

- `sum_squares([1, 3, 5, 7])` → `84`
- `sum_squares([100, 1, 15, 2])` → `10230`
- `sum_squares([10000, 10000])` → `200000000`

---
## ANSWER KEY (for human review only — never shown to agents)

```python
def sum_squares(lst):
    """You are given a list of numbers.
    You need to return the sum of squared numbers in the given list,
    round each element in the list to the upper int(Ceiling) first.
    Examples:
    For lst = [1,2,3] the output should be 14
    For lst = [1,4,9] the output should be 98
    For lst = [1,3,5,7] the output should be 84
    For lst = [1.4,4.2,0] the output should be 29
    For lst = [-2.4,1,1] the output should be 6
    

    """

    import math
    return sum(map(lambda x: math.ceil(x) ** 2, lst))
```

Mutation: `const_offbyone` (constant → constant+1); fail fraction 0.992; difficulty `blatant`.
