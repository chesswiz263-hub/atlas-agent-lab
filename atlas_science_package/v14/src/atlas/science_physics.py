"""ATLAS v1.4: bounded dimensional, symbolic and numerical physics research.

No arbitrary code execution. Reproducibility hashes fingerprint our deterministic output,
NOT scientific correctness. Literature metadata is never promoted to primary evidence.
"""
from __future__ import annotations

import ast
import hashlib
import json
import math
from fractions import Fraction
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from atlas.science_arxiv import discover_arxiv
from atlas.science_math import MathTask, _parse, evaluate_math_task

NAMES = ('L', 'M', 'T', 'I', 'Theta', 'N', 'J')
ZERO = (Fraction(0),) * len(NAMES)


def _d(**parts: int) -> tuple[Fraction, ...]:
    return tuple(Fraction(parts.get(k, 0)) for k in NAMES)


UNIT_DIMENSIONS = {
    'm': _d(L=1), 'cm': _d(L=1), 'km': _d(L=1), 'mm': _d(L=1),
    'kg': _d(M=1), 'g': _d(M=1), 's': _d(T=1), 'ms': _d(T=1),
    'min': _d(T=1), 'h': _d(T=1), 'A': _d(I=1), 'K': _d(Theta=1),
    'mol': _d(N=1), 'cd': _d(J=1), 'rad': ZERO, 'one': ZERO,
    'Hz': _d(T=-1), 'N': _d(L=1, M=1, T=-2),
    'J': _d(L=2, M=1, T=-2), 'W': _d(L=2, M=1, T=-3),
    'Pa': _d(L=-1, M=1, T=-2), 'C': _d(T=1, I=1),
    'V': _d(L=2, M=1, T=-3, I=-1),
    'Ohm': _d(L=2, M=1, T=-3, I=-2),
}


def _add(a, b):
    return tuple(x + y for x, y in zip(a, b))


def _scale(a, exponent):
    return tuple(x * exponent for x in a)


def _power(node):
    # Literal integer exponent only. Fractions are obtained with sqrt(expr).
    if isinstance(node, ast.Constant) and type(node.value) is int:
        n = node.value
    elif (isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub)
          and isinstance(node.operand, ast.Constant) and type(node.operand.value) is int):
        n = -node.operand.value
    else:
        raise ValueError('Power must be a literal integer; use sqrt for fractional dimensions')
    if abs(n) > 8:
        raise ValueError('Exponent exceeds supported range')
    return n


def _dimension_of(expression: str, symbols: dict[str, tuple[Fraction, ...]], *, units=False):
    if len(expression) > 160:
        raise ValueError('Expression exceeds 160 characters')
    tree = ast.parse(expression, mode='eval')
    count = 0

    def recurse(node, depth=0):
        nonlocal count
        count += 1
        if count > 64 or depth > 14:
            raise ValueError('Expression complexity exceeded')
        if isinstance(node, ast.Expression):
            return recurse(node.body, depth + 1)
        if isinstance(node, ast.Constant) and type(node.value) in (int, float):
            if not math.isfinite(node.value) or len(str(node.value)) > 24:
                raise ValueError('Invalid numeric constant')
            return ZERO
        if isinstance(node, ast.Name):
            if node.id not in symbols:
                raise ValueError(f'Unknown {"unit" if units else "variable"}: {node.id[:30]}')
            return symbols[node.id]
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.USub, ast.UAdd)):
            return recurse(node.operand, depth + 1)
        if isinstance(node, ast.BinOp):
            a = recurse(node.left, depth + 1)
            if isinstance(node.op, ast.Pow):
                return _scale(a, _power(node.right))
            b = recurse(node.right, depth + 1)
            if isinstance(node.op, ast.Mult):
                return _add(a, b)
            if isinstance(node.op, ast.Div):
                return _add(a, _scale(b, -1))
            if isinstance(node.op, (ast.Add, ast.Sub)):
                if a != b:
                    raise ValueError('Cannot add or subtract terms with different physical dimensions')
                return a
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and not node.keywords and len(node.args) == 1:
            d = recurse(node.args[0], depth + 1)
            if node.func.id == 'sqrt':
                return _scale(d, Fraction(1, 2))
            if node.func.id in ('sin', 'cos', 'tan', 'exp', 'log'):
                if d != ZERO:
                    raise ValueError(f'{node.func.id} requires a dimensionless argument')
                return ZERO
        raise ValueError('Unsupported syntax; only algebra, integer powers and named functions are allowed')

    try:
        return recurse(tree)
    except SyntaxError as exc:
        raise ValueError('Invalid expression syntax') from exc


def _format_dimension(d) -> str:
    return ' '.join(f'{name}^{power}' for name, power in zip(NAMES, d) if power) or 'dimensionless'


class DimensionalTask(BaseModel):
    model_config = ConfigDict(extra='forbid')
    expression: str = Field(min_length=1, max_length=160)
    variable_units: dict[str, str] = Field(default_factory=dict, max_length=10)
    expected_unit: str | None = Field(default=None, max_length=60)

    @field_validator('variable_units')
    @classmethod
    def validate_vars(cls, val):
        import re
        for name, unit in val.items():
            if not re.fullmatch(r'[A-Za-z][A-Za-z0-9_]{0,14}', name) or not 1 <= len(unit) <= 60:
                raise ValueError('Each named variable needs a short unit expression')
        return val


def evaluate_dimensions(task: DimensionalTask) -> dict:
    base = {'expression': task.expression, 'variable_units': task.variable_units,
            'expected_unit': task.expected_unit, 'scope': 'SI base dimensions only; unit scales and physics assumptions not checked'}
    try:
        symbols = {name: _dimension_of(unit, UNIT_DIMENSIONS, units=True)
                   for name, unit in task.variable_units.items()}
        if '=' in task.expression:
            if task.expected_unit:
                raise ValueError('expected_unit is only supported for a single expression')
            if task.expression.count('=') != 1:
                raise ValueError('Equation must contain one equals sign')
            left, right = task.expression.split('=', 1)
            a, b = _dimension_of(left.strip(), symbols), _dimension_of(right.strip(), symbols)
            return {**base, 'status': 'DIMENSIONALLY_CONSISTENT' if a == b else 'DIMENSION_MISMATCH',
                    'left_dimension': _format_dimension(a), 'right_dimension': _format_dimension(b)}
        actual = _dimension_of(task.expression, symbols)
        output = {**base, 'actual_dimension': _format_dimension(actual)}
        if task.expected_unit:
            expected = _dimension_of(task.expected_unit, UNIT_DIMENSIONS, units=True)
            return {**output, 'expected_dimension': _format_dimension(expected),
                    'status': 'DIMENSIONALLY_CONSISTENT' if expected == actual else 'DIMENSION_MISMATCH'}
        return {**output, 'status': 'DIMENSIONS_COMPUTED'}
    except (ValueError, TypeError, RecursionError) as exc:
        return {**base, 'status': 'NOT_CHECKED', 'reason': str(exc)[:220]}


class SymbolicTask(BaseModel):
    model_config = ConfigDict(extra='forbid')
    expression: str = Field(min_length=1, max_length=160)
    operation: Literal['simplify', 'differentiate', 'verify_equation',
                       'integrate_polynomial', 'solve_polynomial'] = 'simplify'
    variable: str = Field(default='x', pattern=r'^[A-Za-z][A-Za-z0-9_]{0,14}$')


def _preflight_polynomial(expression: str) -> None:
    """Reject expensive nested exponentiation before constructing SymPy integers."""
    tree = ast.parse(expression, mode='eval')
    powers = 0
    for node in ast.walk(tree):
        if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Pow):
            powers += 1
        if isinstance(node, ast.Constant) and type(node.value) in (int, float):
            if abs(node.value) > 100000:
                raise ValueError('Numeric literal exceeds polynomial safety bound')
    if powers > 2:
        raise ValueError('Polynomial operation allows at most two power operators')


def evaluate_symbolic(task: SymbolicTask) -> dict:
    base = {'operation': task.operation, 'expression': task.expression, 'variable': task.variable,
            'scope': 'Formal mathematics on the common defined domain; not physical-law verification'}
    if task.operation in ('simplify', 'differentiate', 'verify_equation'):
        return {**base, **evaluate_math_task(MathTask(**task.model_dump()))}
    try:
        import sympy as sp
        _preflight_polynomial(task.expression)
        expression = _parse(task.expression)
        var = sp.Symbol(task.variable)
        poly = sp.Poly(expression, var)
        if set(poly.free_symbols) - {var}:
            raise ValueError('Only univariate polynomials with numeric coefficients are supported')
        if poly.degree() > 6 or poly.degree() < 0:
            raise ValueError('Polynomial degree must be 0–6')
        for coeff in poly.all_coeffs():
            if not coeff.is_Rational or abs(int(coeff.p)) > 100000 or abs(int(coeff.q)) > 100000:
                raise ValueError('Polynomial coefficients must be bounded rational numbers')
        if task.operation == 'integrate_polynomial':
            result = sp.integrate(poly.as_expr(), var)
            derivative = sp.diff(result, var)
            verified = sp.expand(derivative - poly.as_expr()) == 0
            return {**base, 'status': 'COMPUTED_AND_DIFFERENTIATION_CHECKED' if verified else 'CHECK_FAILED',
                    'result': str(result) + ' + C', 'derivative_check': str(derivative),
                    'verification': 'Derivative of antiderivative equals input polynomial'}
        if poly.degree() > 3:
            raise ValueError('Polynomial root solving is limited to degree 3')
        roots = sp.solve(poly.as_expr(), var)
        if len(roots) > 3 or any(len(str(r)) > 220 for r in roots):
            raise ValueError('Exact roots exceed output size limit')
        residuals = [sp.simplify(poly.as_expr().subs(var, root)) for root in roots]
        return {**base, 'status': 'EXACT_ROOTS_CHECKED' if all(r == 0 for r in residuals) else 'CHECK_FAILED',
                'solutions': [str(r) for r in roots], 'residuals': [str(r) for r in residuals],
                'verification': 'Each returned root was substituted into the polynomial'}
    except ImportError:
        return {**base, 'status': 'NOT_CHECKED', 'reason': 'SymPy not installed'}
    except (ValueError, TypeError, ArithmeticError, RecursionError, sp.PolynomialError) as exc:
        return {**base, 'status': 'NOT_CHECKED', 'reason': str(exc)[:220]}


class NumericalTask(BaseModel):
    model_config = ConfigDict(extra='forbid')
    kind: Literal['kinetic_energy', 'damped_oscillator_rk4']
    inputs: dict[str, float] = Field(min_length=2, max_length=8)


def _finite_inputs(inputs, required: set[str]):
    if set(inputs) != required:
        raise ValueError('Expected exactly: ' + ', '.join(sorted(required)))
    if any(type(v) not in (int, float) or not math.isfinite(v) or abs(v) > 1e8 for v in inputs.values()):
        raise ValueError('Inputs must be finite bounded SI numbers')


def evaluate_numerical(task: NumericalTask) -> dict:
    base = {'kind': task.kind, 'inputs': task.inputs, 'version': 'atlas-v1.4-numerics-1',
            'scope': 'Deterministic double-precision numerical calculation with stated idealized assumptions; not a validated experiment'}
    try:
        if task.kind == 'kinetic_energy':
            _finite_inputs(task.inputs, {'mass_kg', 'velocity_m_s'})
            m, v = task.inputs['mass_kg'], task.inputs['velocity_m_s']
            if m <= 0:
                raise ValueError('mass_kg must be positive')
            value = 0.5 * m * v * v
            output = {'formula': '0.5 * mass_kg * velocity_m_s**2',
                      'energy_joules': value, 'assumptions': ['Classical nonrelativistic point mass']}
        else:
            keys = {'mass_kg', 'spring_N_m', 'damping_N_s_m', 'x0_m', 'v0_m_s', 'dt_s', 'steps'}
            _finite_inputs(task.inputs, keys)
            v = task.inputs
            m, k, c = v['mass_kg'], v['spring_N_m'], v['damping_N_s_m']
            dt, steps_float = v['dt_s'], v['steps']
            if m <= 0 or k < 0 or c < 0 or not 0 < dt <= 0.25:
                raise ValueError('Require positive mass and dt; nonnegative stiffness and damping; dt <= 0.25s')
            if steps_float != int(steps_float) or not 1 <= steps_float <= 400:
                raise ValueError('steps must be an integer between 1 and 400')
            if (dt * math.sqrt(k / m) > 0.2 or dt * c / m > 0.2):
                raise ValueError('Time step fails conservative frequency/damping resolution bound')
            steps = int(steps_float)
            x, velocity = v['x0_m'], v['v0_m_s']
            trace = [{'time_s': 0.0, 'x_m': x, 'v_m_s': velocity}]
            def slope(px, pv):
                return pv, -k / m * px - c / m * pv
            for i in range(steps):
                a1, b1 = slope(x, velocity)
                a2, b2 = slope(x + dt*a1/2, velocity + dt*b1/2)
                a3, b3 = slope(x + dt*a2/2, velocity + dt*b2/2)
                a4, b4 = slope(x + dt*a3, velocity + dt*b3)
                x += dt*(a1+2*a2+2*a3+a4)/6
                velocity += dt*(b1+2*b2+2*b3+b4)/6
                if not (math.isfinite(x) and math.isfinite(velocity)):
                    raise ValueError('Numerical integration became nonfinite')
                trace.append({'time_s': (i+1)*dt, 'x_m': x, 'v_m_s': velocity})
            indices = sorted({round(i*steps/10) for i in range(11)})
            output = {'formula': 'm*x_second_derivative + c*x_first_derivative + k*x = 0',
                      'method': 'fixed-step classical RK4',
                      'initial_energy_joules': 0.5*m*v['v0_m_s']**2 + 0.5*k*v['x0_m']**2,
                      'final_energy_joules': 0.5*m*velocity**2 + 0.5*k*x**2,
                      'final_time_s': steps*dt, 'final_x_m': x, 'final_v_m_s': velocity,
                      'sampled_trajectory': [trace[i] for i in indices],
                      'assumptions': ['Linear spring, constant mass, linear viscous damping, SI inputs',
                                      'Step bound is a heuristic, not a certified numerical-error estimate']}
        fingerprint = hashlib.sha256(json.dumps({'inputs': base, 'output': output},
                                                sort_keys=True, allow_nan=False).encode()).hexdigest()
        return {**base, 'status': 'COMPUTED', 'output': output, 'run_sha256': fingerprint}
    except (ValueError, ArithmeticError, OverflowError) as exc:
        return {**base, 'status': 'NOT_COMPUTED', 'reason': str(exc)[:220]}


class PhysicsResearchRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    question: str = Field(min_length=5, max_length=500)
    search_arxiv: bool = True
    arxiv_limit: int = Field(default=5, ge=1, le=6)
    dimensional_tasks: list[DimensionalTask] = Field(default_factory=list, max_length=4)
    symbolic_tasks: list[SymbolicTask] = Field(default_factory=list, max_length=4)
    numerical_tasks: list[NumericalTask] = Field(default_factory=list, max_length=3)


async def scientific_physics(request: PhysicsResearchRequest, *, client=None) -> dict:
    discovery = (await discover_arxiv(request.question, request.arxiv_limit, client=client)
                 if request.search_arxiv else {'status': 'NOT_REQUESTED', 'papers': [], 'source': 'arXiv'})
    dimensions = [evaluate_dimensions(t) for t in request.dimensional_tasks]
    symbolic = [evaluate_symbolic(t) for t in request.symbolic_tasks]
    numerical = [evaluate_numerical(t) for t in request.numerical_tasks]
    return {'version': '1.4', 'question': request.question, 'arxiv_discovery': discovery,
            'dimensional_checks': dimensions, 'symbolic_checks': symbolic,
            'numerical_runs': numerical,
            'answer_status': 'COMPUTED_RESULTS_AND_METADATA_ONLY',
            'answer': ('ATLAS returned bounded publication candidates and requested checks. '
                       'No paper contents, experimental claims, or physical laws were independently validated. '
                       'For evidence passages and model-assisted synthesis, use the existing Science Research workspace.'),
            'limitations': [
                'arXiv Atom results are repository metadata/preprint abstracts, not independently verified full text.',
                'Dimensional consistency is necessary but insufficient for a physically valid model.',
                'A symbolic identity on a common domain does not validate physical assumptions.',
                'Numerical run SHA-256 fingerprints enable exact-output comparison, not scientific certification.',
                'No automatic scientific conclusion is inferred from this metadata or these calculations.',
            ]}
