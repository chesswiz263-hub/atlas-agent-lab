"""Bounded symbolic operations. Parse a deliberately small AST; never eval untrusted text."""
from __future__ import annotations

import ast
import re
from typing import Literal

from pydantic import BaseModel, Field


class MathTask(BaseModel):
    expression: str = Field(min_length=1, max_length=160)
    operation: Literal['simplify', 'differentiate', 'verify_equation'] = 'simplify'
    variable: str = Field(default='x', pattern=r'^[A-Za-z][A-Za-z0-9_]{0,14}$')


_ALLOWED_FUNCTIONS = {'sin', 'cos', 'tan', 'exp', 'log', 'sqrt'}


def _parse(expression: str):
    import sympy as sp

    if len(expression) > 160:
        raise ValueError('Expression too long')
    if not re.fullmatch(r'[A-Za-z0-9_ \t().,+\-*/=]+', expression):
        raise ValueError('Unsupported characters')
    if expression.count('**') > 6:
        raise ValueError('Too many powers')
    try:
        tree = ast.parse(expression.strip(), mode='eval')
    except SyntaxError as exc:
        raise ValueError('Invalid expression syntax') from exc
    count = 0
    names: set[str] = set()

    def convert(node, depth=0):
        nonlocal count
        count += 1
        if count > 64 or depth > 12:
            raise ValueError('Expression complexity limit exceeded')
        if isinstance(node, ast.Expression):
            return convert(node.body, depth+1)
        if isinstance(node, ast.Constant) and type(node.value) in (int, float):
            if len(str(node.value)) > 24:
                raise ValueError('Number is too large')
            return sp.Rational(str(node.value))
        if isinstance(node, ast.Name):
            name = node.id
            if len(name) > 15 or name in _ALLOWED_FUNCTIONS or name.startswith('_'):
                raise ValueError('Unsupported symbol')
            names.add(name)
            if len(names) > 6:
                raise ValueError('Too many symbols')
            return sp.Symbol(name)
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.USub, ast.UAdd)):
            value = convert(node.operand, depth+1)
            return -value if isinstance(node.op, ast.USub) else value
        if isinstance(node, ast.BinOp):
            a = convert(node.left, depth+1)
            b = convert(node.right, depth+1)
            if isinstance(node.op, ast.Add):
                return a+b
            if isinstance(node.op, ast.Sub):
                return a-b
            if isinstance(node.op, ast.Mult):
                return a*b
            if isinstance(node.op, ast.Div):
                if b == 0:
                    raise ValueError('Division by zero')
                return a/b
            if isinstance(node.op, ast.Pow):
                if not b.is_Integer or abs(int(b)) > 8:
                    raise ValueError('Powers must be small integer constants')
                return a**int(b)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and not node.keywords:
            if node.func.id in _ALLOWED_FUNCTIONS and len(node.args) == 1:
                f = {'sin': sp.sin, 'cos': sp.cos, 'tan': sp.tan,
                     'exp': sp.exp, 'log': sp.log, 'sqrt': sp.sqrt}[node.func.id]
                return f(convert(node.args[0], depth+1))
        raise ValueError('Only basic algebra and sin/cos/tan/exp/log/sqrt are allowed')
    return convert(tree)


def evaluate_math_task(task: MathTask) -> dict:
    base = {'expression': task.expression, 'operation': task.operation,
            'scope': 'Formal symbolic mathematics; domains, units and physical assumptions not verified'}
    try:
        import sympy as sp
    except ImportError:
        return {**base, 'status': 'NOT_CHECKED', 'reason': 'Install SymPy: pip install -e ".[science]"'}
    try:
        if task.operation == 'verify_equation':
            if task.expression.count('=') != 1:
                raise ValueError('Expected one equals sign')
            left, right = task.expression.split('=', 1)
            lhs, rhs = _parse(left), _parse(right)
            difference = sp.cancel(lhs - rhs)
            # Prove only simple algebraic identities; no claims of formal proof for transcendental identities.
            checked = sp.simplify(difference)
            if checked == 0:
                return {**base, 'status': 'FORMALLY_EQUIVALENT', 'difference': '0',
                        'caveat': 'Identity on their common defined domain; not a physical-law verification'}
            return {**base, 'status': 'NOT_PROVEN', 'difference': str(checked)}
        expr = _parse(task.expression)
        if task.operation == 'differentiate':
            output = sp.diff(expr, sp.Symbol(task.variable))
        else:
            output = sp.cancel(expr) if expr.is_rational_function() else sp.simplify(expr)
        return {**base, 'status': 'COMPUTED', 'result': str(output)}
    except (ValueError, TypeError, AttributeError, ArithmeticError, RecursionError) as exc:
        return {**base, 'status': 'NOT_CHECKED', 'reason': str(exc)[:160]}
