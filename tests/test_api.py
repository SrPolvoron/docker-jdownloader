import base64
import sqlite3
from fastapi.testclient import TestClient
from app.main import app


def auth_headers():
    encoded = base64.b64encode(b'testadmin:test-password-at-least-sixteen-chars').decode()
    return {'Authorization': 'Basic ' + encoded, 'X-JFStack-Request': '1',
            'Content-Type': 'application/json'}


def test_auth_and_enqueue():
    with TestClient(app) as client:
        assert client.get('/').status_code == 401
        assert client.get('/', headers=auth_headers()).status_code == 200
        assert client.post('/api/jobs', json={'links':'https://example.org/abc'}).status_code == 403
        res = client.post('/api/jobs', headers=auth_headers(), json={
            'links': 'https://mega.nz/file/abc\nhttps://mega.nz/file/abc'})
        assert res.status_code == 201
        assert len(res.json()['jobs']) == 1
        assert client.post('/api/jobs', headers=auth_headers(), json={
            'links': 'http://127.0.0.1/private'}).status_code == 201
        # Strict public-target validation happens before network or JD handoff.


def test_bad_batch():
    with TestClient(app) as client:
        response = client.post('/api/jobs', headers=auth_headers(), json={'links':'file:///etc/passwd'})
        assert response.status_code == 422
        assert client.post('/api/jobs', headers=auth_headers(), json={'links':'abc'}).status_code == 422
        assert client.post('/api/jobs', headers={**auth_headers(), 'Origin':'https://evil.test'}, json={
            'links':'https://example.org'}).status_code == 403
