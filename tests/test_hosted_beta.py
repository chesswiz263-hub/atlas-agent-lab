"""Isolated safety tests for the Hosted ATLAS research beta."""
from __future__ import annotations
import importlib.util
import os
from pathlib import Path
import sys
import types

import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

SOURCE = Path(__file__).resolve().parents[1] / 'atlas_hosted_beta.py'


def load_gateway(monkeypatch, tmp_path):
    monkeypatch.setenv('ATLAS_BETA_PASSWORD', 'a-test-password-that-is-long-enough')
    monkeypatch.setenv('ATLAS_COOKIE_SECRET', 'one-extremely-long-test-secret-for-cookie-authentication')
    monkeypatch.setenv('ATLAS_ALLOW_HTTP_LOCAL_TEST', '1')
    original = FastAPI()
    @original.post('/api/science/decompose')
    async def decompose(request: Request):
        return {'answer':'FAKE deterministic answer', 'answer_status':'TEST'}
    @original.post('/api/science/workflow')
    async def workflow(request: Request):
        return {'answer':'FAKE math answer'}
    @original.post('/api/jobs')
    async def jobs():
        return {'status':'unsafe'}
    atlas = types.ModuleType('atlas')
    api = types.ModuleType('atlas.api')
    api.create_app = lambda: original
    monkeypatch.setitem(sys.modules,'atlas',atlas)
    monkeypatch.setitem(sys.modules,'atlas.api',api)
    source = tmp_path / 'atlas_hosted_beta.py'
    source.write_bytes(SOURCE.read_bytes())
    spec = importlib.util.spec_from_file_location('atlas_hosted_beta_isolated', source)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.app

@pytest.fixture
def client(monkeypatch, tmp_path):
    import shutil
    base = tmp_path / 'static'
    base.mkdir(exist_ok=True)
    for src, out in [('index.html','atlas-chat.html'),('atlas-chat.js','atlas-chat.js'),('atlas-chat.css','atlas-chat.css')]:
        shutil.copy2(SOURCE.parent/'atlas_hosted_beta_assets'/src,base/out)
    with TestClient(load_gateway(monkeypatch, tmp_path), base_url='https://testserver') as c:
        yield c

def test_health_no_auth(client):
    assert client.get('/healthz').json()['status']=='ok'
    assert client.get('/auth/session').status_code == 401
    assert client.post('/api/science/decompose',json={'question':'test'}).status_code == 401
    assert client.post('/api/jobs',json={}).status_code == 404

def test_login_and_csrf(client):
    bad=client.post('/auth/login',json={'password':'bad'})
    assert bad.status_code==401
    good=client.post('/auth/login',json={'password':'a-test-password-that-is-long-enough'})
    assert good.status_code==200
    assert 'httponly' in good.headers['set-cookie'].lower()
    assert 'secure' in good.headers['set-cookie'].lower()
    token=client.get('/auth/session').json()['csrf']
    assert len(token)==64
    assert client.post('/api/science/decompose',json={'question':'test'}).status_code==403
    resp=client.post('/api/science/decompose',json={'question':'test'},headers={'X-Atlas-CSRF':token})
    assert resp.status_code==200
    assert resp.json()['answer']=='FAKE deterministic answer'

def test_paid_provider_and_cross_origin_rejected(client):
    assert client.post('/auth/login',json={'password':'a-test-password-that-is-long-enough'}).status_code==200
    csrf=client.get('/auth/session').json()['csrf']
    hdr={'X-Atlas-CSRF':csrf}
    assert client.post('/api/science/decompose',json={'question':'test','provider':'openai'},headers=hdr).status_code==403
    assert client.post('/api/science/decompose',json={'question':'test'},headers={**hdr,'Origin':'https://evil.example'}).status_code==403

def test_bad_secret_or_password(monkeypatch):
    monkeypatch.setenv('ATLAS_BETA_PASSWORD','bad')
    monkeypatch.setenv('ATLAS_COOKIE_SECRET','bad')
    spec = importlib.util.spec_from_file_location('atlas_hosted_beta_bad', SOURCE)
    m = importlib.util.module_from_spec(spec)
    with pytest.raises(RuntimeError):
        spec.loader.exec_module(m)
