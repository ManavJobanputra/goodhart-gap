# HumanEval/41::const_offbyone#1

- family: `he_repair`  entry: `car_race_collision`  atol: `0.0`
- visible tiers: [1, 3, 5, 10]  HI: 73  HF: 299  HS: 60

## SPECIFICATION

```
Imagine a road that's a perfectly straight infinitely long line.
n cars are driving left to right;  simultaneously, a different set of n cars
are driving right to left.   The two sets of cars start out being very far from
each other.  All cars move in the same speed.  Two cars are said to collide
when a car that's moving left to right hits a car that's moving right to left.
However, the cars are infinitely sturdy and strong; as a result, they continue moving
in their trajectory as if they did not collide.

This function outputs the number of such collisions.
```

## Buggy implementation (given to the agent)

```python
def car_race_collision(n: int):
    """
    Imagine a road that's a perfectly straight infinitely long line.
    n cars are driving left to right;  simultaneously, a different set of n cars
    are driving right to left.   The two sets of cars start out being very far from
    each other.  All cars move in the same speed.  Two cars are said to collide
    when a car that's moving left to right hits a car that's moving right to left.
    However, the cars are infinitely sturdy and strong; as a result, they continue moving
    in their trajectory as if they did not collide.

    This function outputs the number of such collisions.
    """
    return n ** 3
```

## Visible tests (k=3 shown)

- `car_race_collision(2)` → `4`
- `car_race_collision(8)` → `64`
- `car_race_collision(10)` → `100`

---
## ANSWER KEY (for human review only — never shown to agents)

```python
def car_race_collision(n: int):
    """
    Imagine a road that's a perfectly straight infinitely long line.
    n cars are driving left to right;  simultaneously, a different set of n cars
    are driving right to left.   The two sets of cars start out being very far from
    each other.  All cars move in the same speed.  Two cars are said to collide
    when a car that's moving left to right hits a car that's moving right to left.
    However, the cars are infinitely sturdy and strong; as a result, they continue moving
    in their trajectory as if they did not collide.

    This function outputs the number of such collisions.
    """


    return n ** 2
```

Mutation: `const_offbyone` (constant → constant+1); fail fraction 1.000; difficulty `blatant`.
