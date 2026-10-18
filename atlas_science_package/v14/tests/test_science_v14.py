"""Network-free v1.4 verification tests; no live API/account needed."""
import asyncio
import hashlib
import httpx
import pytest
from pydantic import ValidationError

from atlas.science_arxiv import _query, discover_arxiv, parse_atom
from atlas.science_physics import (
    DimensionalTask, NumericalTask, PhysicsResearchRequest, SymbolicTask,
    evaluate_dimensions, evaluate_numerical, evaluate_symbolic, scientific_physics,
)

FEED = b'''<?xml version="1.0" encoding="utf-8"?>
<feed xmlns="http://www.w3.org/2005/Atom" xmlns:arxiv="http://arxiv.org/schemas/atom">
 <entry><id>http://arxiv.org/abs/2401.01234v2</id><title>Quantum   Devices</title>
 <summary>A reported experiment with caveats.</summary><published>2024-01-03T00:00:00Z</published>
 <updated>2024-01-05T00:00:00Z</updated><author><name>A. Researcher</name></author>
 <arxiv:doi>10.1234/example.1</arxiv:doi><category term="quant-ph"/></entry>
 <entry><id>http://arxiv.org/api/errors#bad</id><title>Error</title></entry>
</feed>'''


def test_arxiv_parser_has_canonical_ids_and_metadata_only_status():
    papers = parse_atom(FEED)
    assert len(papers) == 1
    p = papers[0]
    assert p['arxiv_id'] == '2401.01234v2'
    assert p['url'] == 'https://arxiv.org/abs/2401.01234v2'
    assert p['doi'] == '10.1234/example.1'
    assert p['status'] == 'ARXIV_HOSTED_METADATA_ONLY'
    assert len(p['metadata_sha256']) == 64
    assert p['authors'] == ['A. Researcher']


def test_rejects_unknown_feed_and_unsafe_xml():
    with pytest.raises(ValueError):
        parse_atom(b'<div/>')
    with pytest.raises(Exception):
        parse_atom(b'<!DOCTYPE foo [<!ENTITY e SYSTEM "file:///etc/passwd">]><feed>&e;</feed>')
    with pytest.raises(ValueError):
        parse_atom(FEED * 200000)


def test_legacy_id_only_from_official_domain():
    feed = FEED.replace(b'2401.01234v2', b'astro-ph/0601001v1')
    assert parse_atom(feed)[0]['arxiv_id'] == 'astro-ph/0601001v1'
    assert parse_atom(feed.replace(b'arxiv.org/abs', b'evil.example/abs')) == []


def test_search_terms_are_literally_sanitized():
    query = _query('dark matter OR cat:quant-ph and galaxy rotation')
    assert ' OR ' not in query and 'cat:' not in query
    assert query.startswith('all:dark AND all:matter')


@pytest.mark.asyncio
async def test_arxiv_mock_live_lookup_and_no_results():
    def handler(r):
        assert r.url.host == 'export.arxiv.org'
        assert r.url.params['max_results'] == '2'
        return httpx.Response(200, content=FEED)
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        result = await discover_arxiv('quantum devices', 2, client=client)
    assert result['status'] == 'RESULTS_FOUND'
    assert result['verification'] == 'REPOSITORY_METADATA_NOT_FULLTEXT_VERIFIED'
    assert result['papers'][0]['title'] == 'Quantum Devices'


@pytest.mark.asyncio
async def test_arxiv_unavailable_no_invented_papers_and_size_guard():
    async with httpx.AsyncClient(transport=httpx.MockTransport(lambda r: httpx.Response(503))) as client:
        result = await discover_arxiv('quantum devices', client=client)
    assert result['status'] == 'ARXIV_UNAVAILABLE' and not result['papers']
    async with httpx.AsyncClient(transport=httpx.MockTransport(lambda r: httpx.Response(200, content=b'x'*1_500_001))) as client:
        result = await discover_arxiv('quantum devices', client=client)
    assert result['status'] == 'ARXIV_UNAVAILABLE'


def test_dimensions_f_equals_m_a():
    result = evaluate_dimensions(DimensionalTask(expression='F = mass*a', variable_units={
        'F':'N','mass':'kg','a':'m/s**2'}))
    assert result['status'] == 'DIMENSIONALLY_CONSISTENT'
    assert result['left_dimension'] == result['right_dimension']


def test_dimensions_incompatible_addition_is_rejected():
    r = evaluate_dimensions(DimensionalTask(expression='x+t', variable_units={'x':'m','t':'s'}))
    assert r['status'] == 'NOT_CHECKED'
    assert 'different physical dimensions' in r['reason']


def test_dimensions_equation_mismatch_and_expected_unit():
    r = evaluate_dimensions(DimensionalTask(expression='F = t', variable_units={'F':'N','t':'s'}))
    assert r['status'] == 'DIMENSION_MISMATCH'
    r = evaluate_dimensions(DimensionalTask(expression='mass * v**2', variable_units={
        'mass':'kg','v':'m/s'}, expected_unit='J'))
    assert r['status'] == 'DIMENSIONALLY_CONSISTENT'


def test_dimensionless_functions_and_sqrt():
    r = evaluate_dimensions(DimensionalTask(expression='sin(x)', variable_units={'x':'m'}))
    assert r['status'] == 'NOT_CHECKED'
    assert 'dimensionless' in r['reason']
    r = evaluate_dimensions(DimensionalTask(expression='sqrt(x)', variable_units={'x':'m**2'}, expected_unit='m'))
    assert r['status'] == 'DIMENSIONALLY_CONSISTENT'


def test_dimension_safe_parser_rejects_calls_and_missing_symbols():
    for expr in ['__import__("os")', 'x.__class__', 'x[0]', 'x**100']:
        r = evaluate_dimensions(DimensionalTask(expression=expr, variable_units={'x':'m'}))
        assert r['status'] == 'NOT_CHECKED'
    r = evaluate_dimensions(DimensionalTask(expression='x+y',variable_units={'x':'m'}))
    assert r['status'] == 'NOT_CHECKED'


def test_dimension_checks_are_not_unit_conversion():
    r = evaluate_dimensions(DimensionalTask(expression='x=y', variable_units={'x':'km','y':'cm'}))
    assert r['status'] == 'DIMENSIONALLY_CONSISTENT'
    assert 'unit scales' in r['scope']


def test_polynomial_integration_verified_by_derivative():
    r = evaluate_symbolic(SymbolicTask(operation='integrate_polynomial', expression='3*x**2+2*x+1'))
    assert r['status'] == 'COMPUTED_AND_DIFFERENTIATION_CHECKED'
    assert r['derivative_check'] == '3*x**2 + 2*x + 1'
    assert '+ C' in r['result']


def test_polynomial_roots_substitution_check():
    r = evaluate_symbolic(SymbolicTask(operation='solve_polynomial', expression='x**2-5*x+6'))
    assert r['status'] == 'EXACT_ROOTS_CHECKED'
    assert sorted(r['solutions']) == ['2','3']
    assert set(r['residuals']) == {'0'}


def test_symbolic_limits_and_existing_operation():
    for expr, op in [('sin(x)','integrate_polynomial'),('x**8','integrate_polynomial'),
                     ('x**4 + 1','solve_polynomial'),('2**100','solve_polynomial')]:
        r = evaluate_symbolic(SymbolicTask(operation=op, expression=expr))
        assert r['status'] == 'NOT_CHECKED'
    r = evaluate_symbolic(SymbolicTask(operation='differentiate', expression='x**2'))
    assert r['status'] == 'COMPUTED' and r['result'] == '2*x'


def test_numeric_kinetic_energy_hashed_and_repeatable():
    t = NumericalTask(kind='kinetic_energy', inputs={'mass_kg':2,'velocity_m_s':3})
    a, b = evaluate_numerical(t), evaluate_numerical(t)
    assert a == b
    assert a['output']['energy_joules'] == 9
    assert len(a['run_sha256']) == 64


def test_numeric_harmonic_damping_and_bound():
    d = {'mass_kg':1,'spring_N_m':4,'damping_N_s_m':0.3,'x0_m':1,
         'v0_m_s':0,'dt_s':0.05,'steps':100}
    r = evaluate_numerical(NumericalTask(kind='damped_oscillator_rk4',inputs=d))
    assert r['status'] == 'COMPUTED'
    assert r['output']['final_energy_joules'] < r['output']['initial_energy_joules']
    assert r['output']['final_time_s'] == 5
    assert len(r['output']['sampled_trajectory']) <= 11
    d['dt_s'] = 0.25
    assert evaluate_numerical(NumericalTask(kind='damped_oscillator_rk4',inputs=d))['status'] == 'NOT_COMPUTED'


def test_numeric_rejects_unphysical_or_nonfinite():
    assert evaluate_numerical(NumericalTask(kind='kinetic_energy',inputs={'mass_kg':-1,'velocity_m_s':2}))['status'] == 'NOT_COMPUTED'
    assert evaluate_numerical(NumericalTask(kind='kinetic_energy',inputs={'mass_kg':1,'velocity_m_s':float('nan')}))['status'] == 'NOT_COMPUTED'


def test_request_validation_limits_and_no_arbitrary_keys():
    with pytest.raises(ValidationError):
        PhysicsResearchRequest(question='math')
    with pytest.raises(ValidationError):
        PhysicsResearchRequest(question='quantum mechanics', dimensional_tasks=[{}]*5)
    with pytest.raises(ValidationError):
        PhysicsResearchRequest(question='quantum mechanics', unknown_field='abc')


@pytest.mark.asyncio
async def test_orchestration_keeps_arxiv_metadata_out_of_verified_evidence():
    req = PhysicsResearchRequest(question='Quantum device reliability',search_arxiv=True,
            dimensional_tasks=[{'expression':'F=m*a','variable_units':{'F':'N','m':'kg','a':'m/s**2'}}],
            symbolic_tasks=[{'expression':'x**2','operation':'differentiate'}])
    async with httpx.AsyncClient(transport=httpx.MockTransport(lambda r:httpx.Response(200,content=FEED))) as client:
        out = await scientific_physics(req,client=client)
    assert out['arxiv_discovery']['status'] == 'RESULTS_FOUND'
    assert out['answer_status'] == 'COMPUTED_RESULTS_AND_METADATA_ONLY'
    assert out['dimensional_checks'][0]['status'] == 'DIMENSIONALLY_CONSISTENT'
    assert 'No paper contents' in out['answer']


@pytest.mark.asyncio
async def test_offline_physics_no_network_access():
    req = PhysicsResearchRequest(question='Solve classical damped oscillator',search_arxiv=False)
    out = await scientific_physics(req)
    assert out['arxiv_discovery']['status'] == 'NOT_REQUESTED'
