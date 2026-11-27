# Mbpp/245::cmp_flip#1

- family: `mbpp_repair`  entry: `max_sum`  atol: `0.0`
- visible tiers: [1, 3, 5, 10]  HI: 94  HF: 300  HS: 60

## SPECIFICATION

```
Write a function that takes an array and finds the maximum sum of a bitonic subsequence for the given array, where a sequence is bitonic if it is first increasing and then decreasing.
```

## Buggy implementation (given to the agent)

```python
"""
Write a function that takes an array and finds the maximum sum of a bitonic subsequence for the given array, where a sequence is bitonic if it is first increasing and then decreasing.
assert max_sum([1, 15, 51, 45, 33, 100, 12, 18, 9]) == 194
"""

def max_sum(arr):
    MSIBS = arr[:]
    for i in range(len(arr)):
        for j in range(0, i):
            if arr[i] >= arr[j] and MSIBS[i] < MSIBS[j] + arr[i]:
                MSIBS[i] = MSIBS[j] + arr[i]
    MSDBS = arr[:]
    for i in range(1, len(arr) + 1):
        for j in range(1, i):
            if arr[-i] > arr[-j] and MSDBS[-i] < MSDBS[-j] + arr[-i]:
                MSDBS[-i] = MSDBS[-j] + arr[-i]
    max_sum = float('-Inf')
    for i, j, k in zip(MSIBS, MSDBS, arr):
        max_sum = max(max_sum, i + j - k)
    return max_sum
```

## Visible tests (k=3 shown)

- `max_sum([1, 15, 51, 45, 33, 100, 12, 18, 9])` → `194`
- `max_sum([2, 3, 14, 16, 21, 23, 29, 30])` → `138`
- `max_sum([6, 9, 6, 7, 6, 5, 9, 4, 4, 3, 3, 1, 6, 9, 9])` → `41`

---
## ANSWER KEY (for human review only — never shown to agents)

```python
"""
Write a function that takes an array and finds the maximum sum of a bitonic subsequence for the given array, where a sequence is bitonic if it is first increasing and then decreasing.
assert max_sum([1, 15, 51, 45, 33, 100, 12, 18, 9]) == 194
"""

def max_sum(arr): 
	MSIBS = arr[:] 
	for i in range(len(arr)): 
		for j in range(0, i): 
			if arr[i] > arr[j] and MSIBS[i] < MSIBS[j] + arr[i]: 
				MSIBS[i] = MSIBS[j] + arr[i] 
	MSDBS = arr[:] 
	for i in range(1, len(arr) + 1): 
		for j in range(1, i): 
			if arr[-i] > arr[-j] and MSDBS[-i] < MSDBS[-j] + arr[-i]: 
				MSDBS[-i] = MSDBS[-j] + arr[-i] 
	max_sum = float("-Inf") 
	for i, j, k in zip(MSIBS, MSDBS, arr): 
		max_sum = max(max_sum, i + j - k) 
	return max_sum
```

Mutation: `cmp_flip` (Gt → GtE); fail fraction 0.158; difficulty `medium`.
