"""ATLAS v2.4.1: independent restricted, bounded math worker for two explicit tasks.

Does not use sympify on user text. Only validated arithmetic expressions reach
atlas_math_v23.parse_safe. Unsupported forms abort rather than guess.
"""
from __future__ import annotations
import json
import re
import sys
from typing import Any

MAX_QUERY = 280


def solve_extension(task: dict[str, Any]) -> dict[str, Any]:
    import sympy as s
    import importlib.util
    from pathlib import Path
    trusted_math_file = Path(__file__).with_name('atlas_math_v23.py')
    spec = importlib.util.spec_from_file_location('_atlas_v23_math_checked', trusted_math_file)
    if spec is None or spec.loader is None:
        raise ValueError('ATLAS v2.3 math parser unavailable')
    verified_math = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(verified_math)
    parse_safe = verified_math.parse_safe
    from sympy.printing.mathml import mathml as sympy_mathml
    import html
    def _safe_math_latex(expr):
        return s.latex(expr)[:1600]
    def _safe_xml_math(expr):
        try:
            output=sympy_mathml(expr, printer='presentation')
            def numeric(m):
                decoded=html.unescape(m.group(0))
                if decoded==m.group(0): return '&amp;'+m.group(1)+';'
                return ''.join('&#'+str(ord(c))+';' for c in decoded)
            return re.sub(r'&([A-Za-z][A-Za-z0-9]+);',numeric,output)[:4200]
        except Exception:
            return '' 
    if not isinstance(task, dict) or len(json.dumps(task)) > 1500:
        raise ValueError('Invalid or oversized math task')
    operation = task.get('operation')
    expr = task.get('expression', '')
    if not isinstance(expr, str) or len(expr) > MAX_QUERY:
        raise ValueError('Invalid mathematical expression')
    x, y = s.symbols('x y', real=True)
    steps = []
    notes = []

    def step(explanation, f, verification='DERIVED'):
        steps.append({
            'explanation': explanation,
            'expression': str(f)[:700],
            'latex': _safe_math_latex(f) if isinstance(f, (s.Basic, s.MatrixBase)) else '',
            'mathml': _safe_xml_math(f) if isinstance(f, (s.Basic, s.MatrixBase)) else '',
            'verification': verification,
        })

    if operation == 'stationary_points_2d':
        if set(task) != {'operation','expression'}:
            raise ValueError('Only an explicit two-variable function is supported')
        f = parse_safe(expr)
        # Standardize parser symbols without evaluating arbitrary user source.
        fx, fy = s.Symbol('x'), s.Symbol('y')
        if f.free_symbols - {fx,fy} or not f.has(fx,fy):
            raise ValueError('Specify a function of exactly x and y')
        # Bound complexity and avoid underdetermined continuum of critical points.
        if not f.is_polynomial(fx,fy) or s.total_degree(f)>6:
            raise ValueError('Stationary point classification currently supports two-variable polynomials up to degree 6')
        gx, gy = s.diff(f,fx), s.diff(f,fy)
        step('Compute both partial derivatives to form the gradient',s.Matrix([gx,gy]),'SYMPY_DERIVATIVE')
        solutions = s.solve([gx,gy],[fx,fy],dict=True)
        if not isinstance(solutions,list) or not solutions or len(solutions)>12:
            raise ValueError('The gradient system is not a finite supported set of critical points')
        fxx, fyy, fxy = s.diff(f, fx,2), s.diff(f,fy,2), s.diff(f,fx,fy)
        hessian = s.Matrix([[fxx,fxy],[fxy,fyy]])
        step('Construct the Hessian matrix of second partial derivatives',hessian,'SYMPY_DERIVATIVE')
        classifications=[]
        for sol in solutions:
            a,b = sol.get(fx),sol.get(fy)
            if a is None or b is None or a.is_real is False or b.is_real is False:
                raise ValueError('Critical point has an unresolved or nonreal coordinate')
            if a.is_real is None or b.is_real is None:
                raise ValueError('Critical point reality is ambiguous')
            if not (s.simplify(gx.subs(sol))==0 and s.simplify(gy.subs(sol))==0):
                raise ValueError('Stationary point did not pass the gradient substitution check')
            D = s.simplify(hessian.det().subs(sol))
            xx = s.simplify(fxx.subs(sol))
            if D.is_positive is True and xx.is_positive is True: label='local minimum'
            elif D.is_positive is True and xx.is_negative is True: label='local maximum'
            elif D.is_negative is True: label='saddle point'
            else: label='inconclusive (Hessian test)'
            classifications.append({'x':str(a),'y':str(b),'D':str(D),'fxx':str(xx),'classification':label})
            step(f'At ({a}, {b}), Hessian determinant D={D} and f_xx={xx}: {label}',s.Eq(s.Symbol('D'),D), 'SUBSTITUTION_CHECKED')
        result_text='; '.join('('+z['x']+', '+z['y']+'): '+z['classification'] for z in classifications)
        result_latex=r'\begin{aligned}'+r'\\'.join(
            '('+s.latex(sol[fx])+','+s.latex(sol[fy])+r') & : \text{'+z['classification']+'}'
            for sol,z in zip(solutions,classifications))+r'\end{aligned}'
        result_xml='<mrow>'+''.join(
            '<mrow>'+_safe_xml_math(s.Tuple(sol[fx],sol[fy]))+
            '<mspace width="1em"/><mtext>'+z['classification']+'</mtext></mrow>'
            for sol,z in zip(solutions,classifications))+'</mrow>'
        notes.append('Stationary-point classifications use the second-derivative test; inconclusive cases require further analysis.')
        return dict(status='CHECKED',operation='stationary_points_2d',input=expr, result=result_text,
            result_latex=result_latex,result_mathml=result_xml,steps=steps,
            verification='GRADIENT_SUBSTITUTION_AND_HESSIAN_CLASSIFICATION',notes=notes)

    if operation == 'ode_ivp_2nd':
        if set(task) != {'operation','expression','initial_y','initial_dy'}:
            raise ValueError('An explicit equation and two initial values are required')
        # Only constant coefficient y''+a*y'+b*y=c, all coefficients numeric safe.
        # Restrict notation deliberately; no arbitrary sympification.
        if expr.count('=') != 1 or not re.fullmatch(r"[A-Za-z0-9_'\s+\-*/().^=]+",expr):
            raise ValueError('Specify a second-order linear constant-coefficient ODE')
        L,R = expr.split('=',1)
        def side(src):
            src=re.sub(r"\by\s*'\s*'",'D2',src)
            src=re.sub(r"\by\s*'",'D1',src)
            src=re.sub(r'\by\b','Y0',src)
            return parse_safe(src)
        raw=s.expand(side(L)-side(R))
        d2,d1,v = s.symbols('D2 D1 Y0')
        if raw.free_symbols - {d2,d1,v}:
            raise ValueError('Only constant coefficients and y, y-prime, y-double-prime are supported')
        aa,bb,cc = (s.simplify(s.diff(raw,t)) for t in (d2,d1,v))
        if any(k.free_symbols for k in (aa,bb,cc)) or aa==0:
            raise ValueError('Second-order linear ODE with nonzero leading coefficient required')
        const=s.simplify(raw-aa*d2-bb*d1-cc*v)
        if const.free_symbols or any(raw.has(t**2) for t in (d2,d1,v)):
            raise ValueError('Nonlinear or variable coefficient ODE not supported')
        if s.simplify(raw - aa*d2-bb*d1-cc*v-const)!=0:
            raise ValueError('Nonlinear ODE not supported')
        # Importantly parse only numeric initial values.
        y0,yp0 = parse_safe(str(task['initial_y'])),parse_safe(str(task['initial_dy']))
        if y0.free_symbols or yp0.free_symbols:
            raise ValueError('Only numeric initial conditions supported')
        t=s.Symbol('x',real=True); fn=s.Function('y'); yy=fn(t)
        equation=s.Eq(aa*s.diff(yy,t,2)+bb*s.diff(yy,t)+cc*yy+const,0)
        step('Write the ODE using y and its derivatives',equation,'ODE_SETUP')
        step('Form the characteristic equation for the homogeneous part',s.Eq(aa*x**2+bb*x+cc,0),'CHARACTERISTIC_POLYNOMIAL')
        ics={yy.subs(t,0):y0,s.Subs(s.diff(yy,t),t,0):yp0}
        result=s.dsolve(equation,yy,ics=ics)
        if not isinstance(result,s.Equality):
            raise ValueError('Initial-value problem did not produce a unique explicit solution')
        rhs=s.simplify(result.rhs)
        residual=s.simplify(aa*s.diff(rhs,t,2)+bb*s.diff(rhs,t)+cc*rhs+const)
        valid=residual==0 and s.simplify(rhs.subs(t,0)-y0)==0 and s.simplify(s.diff(rhs,t).subs(t,0)-yp0)==0
        if not valid:raise ValueError('Solution did not satisfy equation and initial conditions')
        step('Solve using the given initial conditions',result,'SYMPY_DSOLVE')
        step('Substitute the result into the differential equation and initial conditions',s.Eq(s.Symbol('residual'),residual),'SUBSTITUTION_CHECKED')
        notes.append('Second-order linear constant-coefficient IVPs only; all conditions checked by substitution.')
        return dict(status='CHECKED',operation='ode',input=expr, result=str(result),
            result_latex=_safe_math_latex(result),result_mathml=_safe_xml_math(result),steps=steps,
            verification='ODE_AND_INITIAL_CONDITIONS_SUBSTITUTION_CHECKED',notes=notes)

    raise ValueError('Math operation not supported by this extension')


if __name__ == '__main__':
    try:
        try:
            import resource
            resource.setrlimit(resource.RLIMIT_CPU,(7,8))
            resource.setrlimit(resource.RLIMIT_AS,(480*1024*1024,480*1024*1024))
        except (ImportError,ValueError,OSError):
            pass
        incoming=json.loads(sys.stdin.read(1700))
        print(json.dumps({'ok':True,'result':solve_extension(incoming)},ensure_ascii=False,allow_nan=False))
    except Exception as exc:
        print(json.dumps({'ok':False,'error':str(exc)[:240]}))
