"""
mathops.py
-----------
A collection of advanced mathematical utility functions
used to demonstrate Copilot-driven test generation.
"""

from typing import List, Tuple, Union
import math
import statistics

Number = Union[int, float]


# 🧮 Basic Arithmetic
def add(a: Number, b: Number) -> Number:
    """Return the sum of two numbers."""
    return a + b


def divide(a: Number, b: Number) -> float:
    """Divide two numbers. Raises ZeroDivisionError if b == 0."""
    if b == 0:
        raise ZeroDivisionError("Division by zero is not allowed.")
    return a / b


def power(base: Number, exponent: int) -> Number:
    """Compute base raised to the power of exponent."""
    return base ** exponent


# 🧠 Factorial with recursion
def factorial(n: int) -> int:
    """Compute factorial of a non-negative integer using recursion."""
    if n < 0:
        raise ValueError("Negative numbers not allowed.")
    return 1 if n in (0, 1) else n * factorial(n - 1)


# 🔢 Fibonacci with memoization
_fib_cache = {0: 0, 1: 1}

def fibonacci(n: int) -> int:
    """Return the nth Fibonacci number using memoization."""
    if n < 0:
        raise ValueError("Negative index not allowed.")
    if n not in _fib_cache:
        _fib_cache[n] = fibonacci(n - 1) + fibonacci(n - 2)
    return _fib_cache[n]


# 📊 Statistics
def mean(values: List[Number]) -> float:
    """Return the arithmetic mean of a list of numbers."""
    if not values:
        raise ValueError("List is empty.")
    return statistics.mean(values)


def variance(values: List[Number]) -> float:
    """Return sample variance of a list of numbers."""
    if len(values) < 2:
        raise ValueError("At least two values required for variance.")
    return statistics.variance(values)


# 🧮 Matrix operations
def matrix_multiply(A: List[List[Number]], B: List[List[Number]]) -> List[List[Number]]:
    """Multiply two matrices A (m×n) and B (n×p)."""
    if not A or not B:
        raise ValueError("Matrices must not be empty.")

    rows_a, cols_a = len(A), len(A[0])
    rows_b, cols_b = len(B), len(B[0])

    if cols_a != rows_b:
        raise ValueError("Incompatible dimensions for matrix multiplication.")

    result = [[0 for _ in range(cols_b)] for _ in range(rows_a)]

    for i in range(rows_a):
        for j in range(cols_b):
            for k in range(cols_a):
                result[i][j] += A[i][k] * B[k][j]

    return result


# 📈 Quadratic equation solver
def quadratic_roots(a: Number, b: Number, c: Number) -> Tuple[complex, complex]:
    """
    Solve quadratic equation ax² + bx + c = 0.
    Returns a tuple of two roots (which may be complex).
    """
    if a == 0:
        raise ValueError("Coefficient 'a' cannot be zero for a quadratic equation.")

    discriminant = b ** 2 - 4 * a * c
    sqrt_disc = math.sqrt(abs(discriminant))

    if discriminant >= 0:
        root1 = (-b + sqrt_disc) / (2 * a)
        root2 = (-b - sqrt_disc) / (2 * a)
    else:
        # complex roots
        root1 = complex(-b / (2 * a), sqrt_disc / (2 * a))
        root2 = complex(-b / (2 * a), -sqrt_disc / (2 * a))

    return root1, root2


# ⚙️ Utility: normalize a list of numbers
def normalize(values: List[Number]) -> List[float]:
    """Normalize a list of numbers to the 0–1 range."""
    if not values:
        raise ValueError("List is empty.")
    min_val, max_val = min(values), max(values)
    if min_val == max_val:
        return [0.0 for _ in values]
    return [(v - min_val) / (max_val - min_val) for v in values]
