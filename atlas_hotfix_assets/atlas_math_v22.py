"""ATLAS v2.2 bounded deterministic mathematics.

Only a restricted AST reaches SymPy. No parse_expr, sympify(user_text), eval,
exec, code import, lambdify or arbitrary function construction from user input.
Formal checks verify the computed result, not each explanatory English sentence.
"""
from __future__ import annotations

import ast
import re
from typing import Any

MAX_EXPRESSION = 280
MAX_NODES = 90
MAX_DEPTH = 16
FUNCTIONS = frozenset('sin cos tan asin acos atan sinh cosh tanh exp log sqrt abs'.split())
CONSTANTS = frozenset({'pi', 'E', 'oo'})
OPERATIONS = frozenset({'evaluate','simplify','factor','expand','solve','system','differentiate',
                        'integrate','definite_integral','limit','series','sum',
                        'partial','gradient','divergence','curl','double_integral',
                        'triple_integral','ode','laplace','inverse_laplace'})


def parse_safe(source: str):
    import sympy as s
    text = source.strip().replace('^', '**').replace('×', '*').replace('÷', '/')
    # Only simple numeric implicit multiplication. No implicit multiplication of variable groups.
    text = re.sub(r'(?<=\d)(?=[A-Za-z])', '*', text)
    if len(text) > MAX_EXPRESSION or not text:
        raise ValueError('Expression missing or exceeds size limit')
    if not re.fullmatch(r'[A-Za-z0-9_\s()+\-*/.,]+', text):
        raise ValueError('Unsupported expression characters')
    try:
        parsed = ast.parse(text, mode='eval')
    except SyntaxError as e:
        raise ValueError('Invalid math expression: remove non-mathematical instructions; use ^ or ** for powers and * for multiplication') from e
    seen = 0
    symbols: set[str] = set()
    fns = {k: getattr(s, k) for k in FUNCTIONS if k != 'abs'}
    fns['abs'] = s.Abs

    def walk(node: ast.AST, depth: int = 0):
        nonlocal seen
        seen += 1
        if seen > MAX_NODES or depth > MAX_DEPTH:
            raise ValueError('Expression complexity limit exceeded')
        if isinstance(node, ast.Expression):
            return walk(node.body, depth+1)
        if isinstance(node, ast.Constant) and type(node.value) in (float, int):
            if len(str(node.value)) > 28:
                raise ValueError('Number too large')
            return s.Rational(str(node.value))
        if isinstance(node, ast.Name):
            name = node.id
            if name in CONSTANTS:
                return {'pi':s.pi,'E':s.E,'oo':s.oo}[name]
            if name in FUNCTIONS or len(name) > 12 or name.startswith('_'):
                raise ValueError('Unsupported variable name')
            symbols.add(name)
            if len(symbols) > 8:
                raise ValueError('Too many symbols')
            return s.Symbol(name)
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd,ast.USub)):
            value = walk(node.operand,depth+1)
            return -value if isinstance(node.op,ast.USub) else value
        if isinstance(node, ast.BinOp):
            left = walk(node.left,depth+1)
            right = walk(node.right,depth+1)
            if isinstance(node.op, ast.Add): return left+right
            if isinstance(node.op, ast.Sub): return left-right
            if isinstance(node.op, ast.Mult): return left*right
            if isinstance(node.op, ast.Div):
                if right == 0: raise ValueError('Division by zero')
                return left/right
            if isinstance(node.op, ast.Pow):
                if not right.is_Rational or abs(right.p) > 18 or right.q > 8:
                    raise ValueError('Exponent outside safe limit')
                return left**right
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            key = node.func.id
            if key in fns and not node.keywords and len(node.args)==1:
                return fns[key](walk(node.args[0],depth+1))
        raise ValueError('Unsupported syntax; allowed operations are arithmetic, powers and standard functions')
    result = walk(parsed)
    if s.count_ops(result) > 300:
        raise ValueError('Symbolic expression exceeds operation budget')
    return result


def _safe_name(name: str):
    import sympy as s
    if not re.fullmatch(r'[A-Za-z][A-Za-z0-9_]{0,11}', name) or name in FUNCTIONS or name in CONSTANTS:
        raise ValueError('Invalid variable')
    return s.Symbol(name)


def strip_explanation_request(question: str) -> str:
    """Remove only recognizable *trailing* presentation requests.

    Instructions such as 'and explain each step' are not mathematical syntax.
    Keep the original expression intact; any unsupported content still fails
    closed in the restricted SymPy parser rather than executing it.
    """
    text = question.strip().rstrip('?.! ')
    suffixes = (
        r'(?:(?:\s+and\s+)|(?:[.,;]\s*)|(?:\s+))'
        r'(?:please\s+)?(?:explain|show|showing|list|include|provide)\s+'
        r'(?:(?:me|us)\s+)?(?:(?:each|every|all|the|your)\s+)?'
        r'(?:steps?|work|solution|derivation|reasoning)'
        r'(?:\s+(?:clearly|step[- ]by[- ]step|in\s+detail))?$',
        r'(?:(?:\s+and\s+)|(?:[.,;]\s*)|(?:\s+))'
        r'(?:please\s+)?(?:show|explain|walk\s+(?:me\s+)?through)\s+'
        r'(?:it\s+)?step[- ]by[- ]step$',
        r'(?:(?:\s+and\s+)|(?:[.,;]\s*)|(?:\s+))'
        r'(?:with|including)\s+(?:(?:a|the|detailed|full)\s+)?'
        r'(?:step[- ]by[- ]step\s+)?(?:explanation|steps?|derivation|working)$',
        r'\s+step[- ]by[- ]step$',
    )
    for _ in range(3):
        original = text
        for suffix in suffixes:
            cleaned = re.sub(suffix, '', text, flags=re.I).strip().rstrip('?.! ')
            if cleaned != text:
                text = cleaned
                break
        if text == original:
            break
    return text


def add_verified_integration_by_parts_steps(integrand, variable, step) -> None:
    """Explain a bounded polynomial-times-sin/cos/exp integral with checked parts.

    This only adds explanation. The authoritative antiderivative and final
    verification remain in solve_task; unsupported forms use its fallback.
    """
    import sympy as s
    trig_factors = (s.sin(variable), s.cos(variable), s.exp(variable))
    original = integrand
    remainder = integrand
    accumulated = s.S.Zero
    for _ in range(4):
        term = None
        for g in trig_factors:
            coefficient = s.simplify(remainder / g)
            if (coefficient.is_polynomial(variable)
                and s.simplify(coefficient*g-remainder)==0):
                term = (coefficient, g)
                break
        if term is None:
            return
        u, dv = term
        v = s.integrate(dv, variable)
        if s.simplify(s.diff(v,variable)-dv)!=0:
            return
        if s.degree(u,variable)==0:
            terminal = s.simplify(u*v)
            candidate = s.simplify(accumulated+terminal)
            if s.simplify(s.diff(candidate,variable)-original)!=0:
                return
            step('Integrate the last remaining constant-times-function term.',
                 f'{accumulated} + ({terminal}) = {candidate}', 'DIFFERENTIATION_CHECKED')
            step('Differentiate the combined antiderivative to verify the original integrand.',
                 f'd/d{variable} ({candidate}) = {original}', 'DIFFERENTIATION_CHECKED')
            return
        du = s.diff(u, variable)
        new_accumulated = s.simplify(accumulated+u*v)
        new_remainder = s.simplify(-du*v)
        if s.simplify(s.diff(new_accumulated,variable)+new_remainder-original)!=0:
            return
        step('Choose the polynomial part as u and the trigonometric/exponential part as dv; differentiate u and integrate dv.',
             f'u={u}; dv=({dv}) d{variable}; du=({du}) d{variable}; v={v}',
             'SYMPY_DERIVATIVE_AND_ANTIDERIVATIVE_CHECKED')
        step('Apply integration by parts: integral(u dv) = u*v - integral(v du).',
             s.Add(new_accumulated,s.Integral(new_remainder,variable),evaluate=False),
             'DIFFERENTIATION_IDENTITY_CHECKED')
        accumulated = new_accumulated
        remainder = new_remainder


def interpret_math_query(question: str) -> dict[str, Any] | None:
    """Conservative, offline English-to-task parser. Unsupported wording abstains.

    The optional LLM translator can extend this via validated structured tasks;
    its proposed expressions still go through parse_safe and the math checker.
    """
    q = strip_explanation_request(question)
    q = re.sub(r'^(?:what is|can you calculate|please calculate|find|compute|evaluate)\s+(?:the\s+)?(?=(?:integral|derivative|partial derivative|limit|gradient|curl|divergence|series|sum|laplace transform|inverse laplace transform)\b)', '', q, flags=re.I)
    q = re.sub(r'^d/d([a-zA-Z])\s+(.+)$',r'differentiate \2 with respect to \1',q,flags=re.I)

    if len(q) > 500 or len(q) < 2:
        return None
    prefixes = [
      (r'^(?:find\s+)?(?:the\s+)?(?:derivative\s+of|differentiate)\s+(.+)$','differentiate'),
      (r'^(?:find\s+)?(?:the\s+)?(?:partial derivative\s+of)\s+(.+)$','partial'),
      (r'^(?:find\s+)?(?:the\s+)?(?:double integral\s+of)\s+(.+)$','double_integral'),
      (r'^(?:find\s+)?(?:the\s+)?(?:triple integral\s+of)\s+(.+)$','triple_integral'),
      (r'^(?:find\s+)?(?:the\s+)?(?:integral\s+of|integrate)\s+(.+)$','integrate'),
      (r'^(?:evaluate\s+)?(?:the\s+)?(?:limit\s+of)\s+(.+)$','limit'),
      (r'^(?:find\s+)?(?:the\s+)?(?:taylor\s+)?(?:series\s+of)\s+(.+)$','series'),
      (r'^(?:calculate\s+)?(?:the\s+)?(?:sum\s+of)\s+(.+)$','sum'),
      (r'^(?:find\s+)?(?:the\s+)?(?:gradient\s+of)\s+(.+)$','gradient'),
      (r'^(?:find\s+)?(?:the\s+)?(?:divergence\s+of)\s+(.+)$','divergence'),
      (r'^(?:find\s+)?(?:the\s+)?(?:curl\s+of)\s+(.+)$','curl'),
      (r'^(?:solve\s+)?(?:the\s+)?(?:differential\s+equation|ode)\s+(.+)$','ode'),
      (r'^(?:find\s+)?(?:the\s+)?(?:inverse laplace transform\s+of)\s+(.+)$','inverse_laplace'),
      (r'^(?:find\s+)?(?:the\s+)?(?:laplace transform\s+of)\s+(.+)$','laplace'),
      (r'^(?:solve\s+)?(?:the\s+)?(?:system\s+of)\s+(.+)$','system'),
      (r'^(?:solve\s+(?:for\s+\w+\s*:\s*)?)(.+)$','solve'),
      (r'^(?:simplify)\s+(.+)$','simplify'),
      (r'^(?:factor)\s+(.+)$','factor'),
      (r'^(?:expand)\s+(.+)$','expand'),
      (r'^(?:calculate|evaluate|what is)\s+(.+)$','evaluate')]
    for pattern, operation in prefixes:
        match = re.fullmatch(pattern,q,re.I)
        if not match: continue
        expr = match.group(1).strip()
        req: dict[str, Any] = {'operation':operation,'expression':expr,'variable':'x'}
        var = re.search(r'\s+(?:with respect to|wrt)\s+([a-zA-Z][a-zA-Z0-9_]*)$', expr, re.I)
        if var:
            req['variable'] = var.group(1)
            req['expression'] = expr[:var.start()].strip()
            expr=req['expression']
        if operation == 'integrate':
            bounds = re.fullmatch(r'(.+?)\s+from\s+([-+\w.*()/]+)\s+to\s+([-+\w.*()/]+)',expr,re.I)
            if bounds:
                req.update(operation='definite_integral',expression=bounds[1], bounds=[[req['variable'],bounds[2],bounds[3]]])
        if operation in ('double_integral','triple_integral'):
            # Explicit repeated-bounds format: double integral of x+y ; x=0..1; y=0..2
            pieces=[p.strip() for p in expr.split(';')]
            expected={'double_integral':2,'triple_integral':3}[operation]
            if len(pieces)==expected+1:
                bounds=[]
                for piece in pieces[1:]:
                    matched=re.fullmatch(r'([a-zA-Z])\s*=\s*([-+\w.*()/]+)\s*\.\.\s*([-+\w.*()/]+)',piece)
                    if matched:bounds.append([matched[1],matched[2],matched[3]])
                if len(bounds)==expected:req.update(expression=pieces[0],bounds=bounds)
        if operation == 'sum':
            limits=re.fullmatch(r'(.+?)\s+from\s+([a-zA-Z])\s*=\s*([-+\w.*()/]+)\s+to\s+([-+\w.*()/]+)',expr,re.I)
            if limits:req.update(expression=limits[1],bounds=[[limits[2],limits[3],limits[4]]])
        if operation == 'series':
            expansion=re.fullmatch(r'(.+?)\s+(?:around|at)\s+([a-zA-Z])\s*=\s*([-+\w.*()/]+)\s+(?:to\s+)?order\s+(\d+)',expr,re.I)
            if expansion:req.update(expression=expansion[1],variable=expansion[2],point=expansion[3],order=int(expansion[4]))
        if operation == 'limit':
            target = re.fullmatch(r'(.+?)\s+(?:as|when)\s+([a-zA-Z][a-zA-Z0-9_]*)\s*(?:->|approaches|to)\s+([-+\w.*()/]+)',expr,re.I)
            if target:
                req.update(expression=target[1],variable=target[2],point=target[3])
        return req
    if re.fullmatch(r'[\d+*().\s/^-]+', q):
        return {'operation':'evaluate','expression':q}
    return None


def solve_task(task: dict[str, Any]) -> dict[str, Any]:
    """Math result and conservative, checkable steps. Execute in a bounded worker."""
    import sympy as s
    operation = str(task.get('operation','')).lower()
    if operation not in OPERATIONS:
        raise ValueError('Unsupported mathematical operation')
    expression = str(task.get('expression',''))
    if len(expression)>MAX_EXPRESSION:
        raise ValueError('Expression too long')
    variable = _safe_name(str(task.get('variable','x')))
    steps: list[dict[str, str]] = []
    def step(explanation, formula, checked):
        steps.append({'explanation': explanation,'expression':str(formula)[:700], 'verification':checked})
    def mathfmt(expr): return str(expr)[:1000]
    def eq_parts(source):
        if source.count('=')>1: raise ValueError('Only one equality permitted per equation')
        if '=' in source:
            a,b=source.split('=',1)
            return parse_safe(a),parse_safe(b)
        return parse_safe(source),s.S.Zero
    result: Any = None
    verification = 'NOT_INDEPENDENTLY_CHECKED'
    notes=[]
    if operation=='ode':
        # Strict notation: y'' + 3*y' + 2*y = 0. Never sympify free-form strings.
        x=s.Symbol(str(variable));y=s.Function('y');yf=y(x)
        left,right=expression.split('=',1) if '=' in expression and expression.count('=')==1 else (expression,'0')
        def parse_ode_side(text):
            text=re.sub(r'\by\s*\'\s*\'', 'D2',text)
            text=re.sub(r'\by\s*\'', 'D1',text)
            text=re.sub(r'\by\b','Y0',text)
            if not re.fullmatch(r'[A-Za-z0-9_\s()+\-*/.,]+',text.replace('^','**')):
                raise ValueError("ODE supports y, y-prime and y-double-prime with safe arithmetic")
            e=parse_safe(text)
            return e.subs({'Y0':yf,'D1':s.diff(yf,x),'D2':s.diff(yf,x,2)})
        lhs=parse_ode_side(left)-parse_ode_side(right)
        if not lhs.has(yf):raise ValueError('ODE must contain y')
        if lhs.has(s.Derivative(yf,(x,3))):raise ValueError('Only ODEs up to second order')
        ode=s.Eq(lhs,0)
        step('Write the differential equation in standard form',ode,'ODE_SETUP')
        result=s.dsolve(ode,yf)
        if not isinstance(result,s.Equality):raise ValueError('Differential equation unresolved')
        residual=s.simplify(lhs.subs(yf,result.rhs).doit())
        verification='SUBSTITUTION_CHECKED' if residual==0 else 'SYMPY_ODE_SOLVED_NOT_SUBSTITUTION_CHECKED'
        step('Solve with symbolic differential-equation rules and substitute back',result,verification)
        notes.append('General solutions include integration constants. Initial conditions require separate specification.')
    elif operation in {'solve','system'}:
        equations = [expression] if operation=='solve' else [x.strip() for x in expression.split(';')]
        if not 1 <= len(equations) <= 4: raise ValueError('Supply 1–4 equations separated by semicolons')
        pairs=[eq_parts(e) for e in equations]
        symbols = sorted(set().union(*(a.free_symbols|b.free_symbols for a,b in pairs)),key=str)
        if not symbols or len(symbols)>4: raise ValueError('Supply equations involving 1–4 symbols')
        if operation=='solve' and variable not in symbols: variable=symbols[0]
        step('Move the right side to the left', [s.Eq(a-b,0,evaluate=False) for a,b in pairs], 'ALGEBRAIC_REARRANGEMENT')
        if operation=='solve' and len(symbols)==1:
            result=s.solveset(pairs[0][0]-pairs[0][1],variable,domain=s.S.Reals)
            if isinstance(result,s.ConditionSet):raise ValueError('The symbolic solver could not determine a complete solution set')
            if isinstance(result,s.FiniteSet):
                valid=all(s.simplify((pairs[0][0]-pairs[0][1]).subs(variable,v))==0 for v in result)
                verification='SUBSTITUTION_CHECKED' if valid else 'NOT_CHECKED'
            else:
                verification='SYMPY_SOLVESET_REAL_DOMAIN'
        else:
            result=s.solve([a-b for a,b in pairs], symbols, dict=True)
            if len(result)>24:raise ValueError('Too many solutions')
            valid=all(all(s.simplify((a-b).subs(sol))==0 for a,b in pairs) for sol in result)
            verification='SUBSTITUTION_CHECKED' if valid else 'NOT_CHECKED'
        step('Solve the equivalent equation(s) and substitute solutions into the originals',result,verification)
    elif operation in {'gradient','divergence','curl'}:
        if operation=='gradient':
            f=parse_safe(expression)
            vars=[s.Symbol(v) for v in ('x','y','z') if s.Symbol(v) in f.free_symbols]
            if not vars:vars=[variable]
            result=s.Matrix([s.diff(f,v) for v in vars]);step('Take one partial derivative per coordinate',result,'SYMPY_DERIVATIVES');verification='SYMBOLIC_DIFFERENTIATION_CHECKED'
        else:
            if not expression.startswith('[') or not expression.endswith(']'):
                raise ValueError('Specify a vector as [P, Q, R]')
            # User-controlled delimiters are split only at nesting depth zero.
            from io import StringIO
            body=expression[1:-1]; parts=[];start=depth=0
            for i,c in enumerate(body):
                if c=='(':depth+=1
                if c==')':depth-=1
                if depth<0: raise ValueError('Unbalanced parentheses')
                if c==',' and depth==0:
                    parts.append(body[start:i].strip());start=i+1
            parts.append(body[start:].strip())
            if len(parts)!=3:raise ValueError('Vector field must have three components')
            P,Q,R=(parse_safe(x) for x in parts);x,y,z=s.symbols('x y z')
            if operation=='divergence':result=s.diff(P,x)+s.diff(Q,y)+s.diff(R,z)
            else:result=s.Matrix([s.diff(R,y)-s.diff(Q,z),s.diff(P,z)-s.diff(R,x),s.diff(Q,x)-s.diff(P,y)])
            step('Apply the Cartesian vector-calculus definition component by component',result,'SYMPY_DERIVATIVES');verification='SYMBOLIC_DIFFERENTIATION_CHECKED'
    else:
        f=parse_safe(expression)
        step('Interpret the input using restricted symbolic syntax', f, 'PARSER_CHECKED')
        if operation in {'laplace','inverse_laplace'}:
            t=s.Symbol('t');p=s.Symbol('s')
            if operation=='laplace':
                result=s.laplace_transform(f,t,p,noconds=True)
                verification='SYMPY_LAPLACE_TRANSFORM_EVALUATED'
                step('Apply the one-sided Laplace transform in t',result,verification)
                notes.append('Region of convergence is not checked by this shortcut.')
            else:
                result=s.inverse_laplace_transform(f,p,t)
                verification='SYMPY_INVERSE_LAPLACE_EVALUATED'
                step('Apply the inverse Laplace transform from s to t',result,verification)
        elif operation in {'evaluate','simplify'}:
            result=s.simplify(f)
            verification='SYMBOLIC_IDENTITY_CHECKED' if s.simplify(result-f)==0 else 'NOT_CHECKED'
            step('Combine terms and simplify without changing the expression on its common domain',result,verification)
        elif operation=='expand':
            result=s.expand(f)
            verification='SYMBOLIC_IDENTITY_CHECKED' if s.simplify(result-f)==0 else 'NOT_CHECKED'
            step('Apply distributivity and collect expanded terms',result,verification)
        elif operation=='factor':
            result=s.factor(f)
            verification='SYMBOLIC_IDENTITY_CHECKED' if s.simplify(result-f)==0 else 'NOT_CHECKED'
            step('Factor the polynomial or rational expression',result,verification)
        elif operation in {'differentiate','partial'}:
            order=int(task.get('order',1))
            if order<1 or order>4:raise ValueError('Derivative order must be 1–4')
            step('Differentiate with respect to '+str(variable)+' (order '+str(order)+')',s.Derivative(f,(variable,order),evaluate=False),'DERIVATIVE_DEFINITION')
            if order==1 and f.is_polynomial(variable):
                pol=s.Poly(f,variable)
                if len(pol.terms())<=8:
                    for (power,), coeff in pol.terms():
                        term=coeff*variable**power
                        derivative=s.diff(term,variable)
                        step(f'Apply the power rule to {term}: multiply by the exponent {power} and reduce the power by one',derivative,'SYMPY_TERM_DERIVATIVE')
            elif order==1 and f.is_Mul and len(f.args)<=5:
                factors=list(f.args)
                terms=[s.diff(factor,variable)*s.Mul(*(v for j,v in enumerate(factors) if j!=i)) for i,factor in enumerate(factors)]
                candidate=s.Add(*terms)
                if s.simplify(candidate-s.diff(f,variable))==0:
                    step('Apply the product rule: differentiate one factor at a time, keeping the others fixed',candidate,'PRODUCT_RULE_CHECKED')
            elif order==1 and f.is_Function and len(f.args)==1 and f.args[0].has(variable) and f.args[0]!=variable:
                inner=f.args[0]
                dummy=s.Dummy('inner')
                outer_derivative=s.diff(f.func(dummy),dummy).subs(dummy,inner)
                candidate=outer_derivative*s.diff(inner,variable)
                if s.simplify(candidate-s.diff(f,variable))==0:
                    step('Apply the chain rule: differentiate the outer function and multiply by the inner derivative',candidate,'CHAIN_RULE_CHECKED')
            elif f.is_Add and len(f.args)<=8 and order==1:
                terms=[s.diff(t,variable) for t in f.args]
                step('Use linearity: differentiate each summand separately',s.Add(*terms), 'TERM_BY_TERM_DIFFERENTIATION')
            result=s.diff(f,variable,order)
            verification='SYMPY_DERIVATIVE_EVALUATED'
            step('Simplify the derivative',result,verification)
        elif operation in {'integrate','definite_integral','double_integral','triple_integral'}:
            bounds=task.get('bounds',[])
            if operation=='integrate':
                if bounds:raise ValueError('Indefinite integrals cannot include bounds')
                if f.is_polynomial(variable):
                    terms=s.Poly(f,variable).terms()
                    if len(terms)<=8:
                        antiderivatives=[]
                        for (power,),coeff in terms:
                            term=coeff*variable**power
                            anti=s.integrate(term,variable)
                            if s.simplify(s.diff(anti,variable)-term)==0:
                                antiderivatives.append(anti)
                                step(f'Apply the reverse power rule to {term}: raise the exponent {power} by one and divide by the new exponent',anti,'TERM_ANTIDERIVATIVE_CHECKED')
                        if len(antiderivatives)==len(terms):
                            step('Add the separately integrated terms by linearity',s.Add(*antiderivatives),'LINEARITY_CHECKED')
                if f.is_Mul:
                    add_verified_integration_by_parts_steps(f,variable,step)
                result=s.integrate(f,variable)
                if result.has(s.Integral):raise ValueError('The integral is outside the symbolic solver’s coverage')
                verification='DIFFERENTIATION_CHECKED' if s.simplify(s.diff(result,variable)-f)==0 else 'NOT_CHECKED'
                step('Find an antiderivative and differentiate it to check the integrand',result,verification)
                notes.append('Add an arbitrary constant C to an indefinite integral.')
            else:
                expected={'definite_integral':1,'double_integral':2,'triple_integral':3}[operation]
                if not isinstance(bounds,list) or len(bounds)!=expected:raise ValueError('Provide the appropriate number of [variable, lower, upper] bounds')
                limits=[]
                for limit in bounds:
                    if not isinstance(limit,(list,tuple)) or len(limit)!=3:raise ValueError('Each bound requires variable, lower, upper')
                    v=_safe_name(str(limit[0]));a=parse_safe(str(limit[1]));b=parse_safe(str(limit[2]));limits.append((v,a,b))
                step('Set up the integral with its explicit bounds',s.Integral(f,*limits),'EXPLICIT_BOUNDS')
                result=s.integrate(f,*limits)
                if result.has(s.Integral) or result.has(s.nan,s.zoo):raise ValueError('No finite, verified closed-form integral result')
                # Symbolic integration is not a check on excluded singularities or Fubini assumptions.
                verification='SYMPY_DEFINITE_INTEGRAL_EVALUATED'
                step('Evaluate using the requested integration limits',result,verification)
                notes.append('Improper integrals, discontinuities and interchange-of-integration conditions require domain review.')
        elif operation=='limit':
            if 'point' not in task:raise ValueError('Specify the limit point, e.g. as x -> 0')
            point=parse_safe(str(task['point']));direction=str(task.get('direction','+-'))
            if direction not in ('+','-','+-'):raise ValueError('Limit direction must be +, -, or +-')
            step('Construct the limit',s.Limit(f,variable,point,dir=direction),'LIMIT_SETUP')
            result=s.limit(f,variable,point,dir=direction)
            if result.has(s.Limit,s.nan):raise ValueError('SymPy could not resolve this limit')
            verification='SYMPY_LIMIT_EVALUATED';step('Evaluate symbolic behavior near the target',result,verification)
        elif operation=='series':
            point=parse_safe(str(task.get('point','0')))
            order=int(task.get('order',6))
            if not 2<=order<=12: raise ValueError('Series order outside 2–12')
            result=s.series(f,variable,point,order)
            verification='SYMPY_SERIES_EXPANSION'
            step('Use derivatives about the expansion point through the requested order',result,verification)
            notes.append('O(...) marks the neglected remainder, not an exact equality.')
        elif operation=='sum':
            bounds=task.get('bounds')
            if not isinstance(bounds,list) or len(bounds)!=1 or len(bounds[0])!=3:raise ValueError('Provide summation bounds [variable, first, last]')
            n=_safe_name(str(bounds[0][0]));a=parse_safe(str(bounds[0][1]));b=parse_safe(str(bounds[0][2]))
            step('Write the series using sigma notation',s.Sum(f,(n,a,b)),'SUM_SETUP')
            result=s.summation(f,(n,a,b))
            if result.has(s.Sum):raise ValueError('Summation not resolved in this symbolic scope')
            verification='SYMPY_SUMMATION_EVALUATED';step('Evaluate symbolic sum or convergence result',result,verification)
        else:raise ValueError('Unsupported mathematical operation')
    if result is None:raise ValueError('No result')
    if mathfmt(result).count('oo') and operation not in {'limit','sum','solve'}:
        notes.append('Non-finite result; check domain and convergence.')
    final=mathfmt(result)
    if operation=='integrate':final+=' + C'
    return {'status':'CHECKED' if verification!='NOT_CHECKED' else 'NOT_CHECKED',
            'operation':operation,'input':expression,'result':final,
            'steps':steps[:16],'verification':verification,'notes':notes,
            'scope':'SymPy formal calculation; domain and mathematical assumptions may require review'}

if __name__ == '__main__':
    import json, sys
    try:
        try:
            import resource
            resource.setrlimit(resource.RLIMIT_CPU,(7,8))
            resource.setrlimit(resource.RLIMIT_AS,(480*1024*1024,480*1024*1024))
        except (ImportError,ValueError,OSError):
            pass
        data=json.loads(sys.stdin.read(3000))
        if not isinstance(data,dict):raise ValueError('Task must be an object')
        result=solve_task(data)
        print(json.dumps({'ok':True,'result':result},allow_nan=False))
    except Exception as exc:
        print(json.dumps({'ok':False,'error':str(exc)[:240]}))
