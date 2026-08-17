from httpx import AsyncClient


async def test_health_accepts_backend_prefix(client: AsyncClient) -> None:
    prefixed = await client.get("/backend/health")
    bare = await client.get("/health")
    assert prefixed.status_code == 200
    assert bare.status_code == 200
    assert prefixed.json()["status"] == "ok"
    assert prefixed.json()["status"] == bare.json()["status"]


async def test_login_accepts_backend_prefix(client: AsyncClient) -> None:
    response = await client.post(
        "/backend/auth/login",
        json={"username": "admin", "password": "admin-pass"},
    )
    assert response.status_code == 200
    assert response.json()["user"]["username"] == "admin"
