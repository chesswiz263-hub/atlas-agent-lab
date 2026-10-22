"""Validate actual versioned gateway security with a stubbed science app."""
import importlib.machinery
import importlib.util
from pathlib import Path
import sys
import types
from fastapi import FastAPI
from fastapi.testclient import TestClient

ROOT=Path(__file__).resolve().parents[1]


def test_hosted_auth_csrf_routes(monkeypatch,tmp_path):
    # Reference gateway module imports a v1.9 atlas.api only after starting.
    fake_atlas=types.ModuleType('atlas');fake_atlas.__path__=[]
    fake_api=types.ModuleType('atlas.api')
    def fake_create_app():
        app=FastAPI()
        @app.post('/api/science/decompose')
        async def decompose():return {'ok':True}
        @app.post('/api/science/workflow')
        async def workflow():return {'ok':True}
        return app
    fake_api.create_app=fake_create_app
    monkeypatch.setitem(sys.modules,'atlas',fake_atlas)
    monkeypatch.setitem(sys.modules,'atlas.api',fake_api)
    monkeypatch.setenv('ATLAS_BETA_PASSWORD','a-password-at-least-sixteen-long')
    monkeypatch.setenv('ATLAS_COOKIE_SECRET','s'*48)
    loader=importlib.machinery.SourceFileLoader('atlas_gateway_v25_test',str(ROOT/'atlas_hosted_beta_v25.reference.py'))
    spec=importlib.util.spec_from_loader(loader.name,loader)
    module=importlib.util.module_from_spec(spec)
    # Gateway resolves BASE beside the reference source; supply required static files there.
    static=ROOT/'static'
    static.mkdir(exist_ok=True)
    for ext in ('html','js','css'):
        dest=static/f'atlas-chat-v25.{ext}'
        if not dest.exists():dest.write_bytes((ROOT/'v25_assets'/dest.name).read_bytes())
    loader.exec_module(module)
    with TestClient(module.app,base_url='https://testserver') as c:
        assert c.post('/api/atlas/chat',json={'question':'integrate x^2'}).status_code==401
        login=c.post('/auth/login',json={'password':'a-password-at-least-sixteen-long'})
        assert login.status_code==200
        csrf=c.get('/auth/session').json()['csrf']
        assert len(csrf)==64
        assert c.post('/api/atlas/chat',json={'question':'integrate x^2'}).status_code==403
        response=c.post('/api/atlas/chat',json={'question':'Integrate x^2'},headers={'x-atlas-csrf':csrf})
        assert response.status_code==200
        assert response.json()['answer_status'].startswith('FORMAL_MATH_')
