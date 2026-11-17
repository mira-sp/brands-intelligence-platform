# backend/tests/test_auth.py
import pytest


def test_public_endpoints(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.headers["x-content-type-options"] == "nosniff"
    assert client.get("/").status_code == 200


@pytest.mark.parametrize("path", ["/api/brands", "/api/mentions", "/api/demo/sample-data", "/auth/me",
                                  "/visibility/brands/x/summary"])
def test_requires_login(client, path):
    assert client.get(path).status_code == 401


def test_ml_requires_login(client):
    assert client.post("/ml/analyze/sentiment", json={"text": "hi"}).status_code == 401


def test_login_failures(client):
    assert client.post("/auth/token", data={"username": "admin@example.com", "password": "wrong-password!!"}).status_code == 401
    assert client.post("/auth/token", data={"username": "nobody@example.com", "password": "whatever-12345"}).status_code == 401


def test_token_and_api_key(client, admin_headers):
    assert client.get("/auth/me", headers=admin_headers).json()["role"] == "admin"
    assert client.get("/api/brands", headers=admin_headers).status_code == 200
    assert client.get("/api/brands", headers={"X-API-Key": "test-service-key-123456"}).status_code == 200
    assert client.get("/api/brands", headers={"X-API-Key": "wrong"}).status_code == 401
    assert client.get("/api/brands", headers={"Authorization": "Bearer garbage"}).status_code == 401


def test_roles_and_deactivation(client, admin_headers):
    r = client.post("/auth/users", headers=admin_headers, json={"email": "v@example.com", "password": "short"})
    assert r.status_code == 422
    r = client.post("/auth/users", headers=admin_headers,
                    json={"email": "viewer@example.com", "password": "viewer-password-1", "role": "viewer"})
    assert r.status_code == 201, r.text
    viewer_id = r.json()["id"]

    token = client.post("/auth/token", data={"username": "viewer@example.com", "password": "viewer-password-1"}).json()["access_token"]
    viewer = {"Authorization": f"Bearer {token}"}
    assert client.post("/auth/users", headers=viewer,
                       json={"email": "x@example.com", "password": "viewer-password-1"}).status_code == 403

    assert client.post(f"/auth/users/{viewer_id}/deactivate", headers=admin_headers).status_code == 200
    assert client.get("/auth/me", headers=viewer).status_code == 401


def test_input_limits(client, admin_headers):
    r = client.post("/ml/analyze/sentiment", headers=admin_headers, json={"text": "a" * 20001})
    assert r.status_code == 413
    assert client.get("/crisis-alerts?threshold=5", headers=admin_headers).status_code == 422
