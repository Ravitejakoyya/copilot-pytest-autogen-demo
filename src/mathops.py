def add(a, b):
    return a + b

def divide(a, b):
    if b == 0:
        raise ValueError("Cannot divide by zero")
    return a / b


def multiply(a, b):
    return a * b

def factorial(n: int) -> int:
    """Compute factorial of n recursively."""
    if n < 0:
        raise ValueError("Negative number not allowed")
    return 1 if n in (0, 1) else n * factorial(n - 1)

def fibonacci(n: int) -> int:
    """Return nth Fibonacci number."""
    if n < 0:
        raise ValueError("Negative index not allowed")
    a, b = 0, 1
    for _ in range(n):
        a, b = b, a + b
    return a
