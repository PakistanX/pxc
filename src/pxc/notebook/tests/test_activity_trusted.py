from fastapi.testclient import TestClient


def _signup(client: TestClient, email: str) -> None:
    response = client.post(
        "/api/auth/signup",
        json={"email": email, "password": "password123"},
    )
    assert response.status_code == 201


def _create_activity(client: TestClient) -> str:
    course = client.post("/api/courses", json={"title": "C"}).json()
    page = client.post(f"/api/courses/{course['id']}/pages", json={"title": "P"}).json()
    activity = client.post(
        f"/api/pages/{page['id']}/activities", json={"activity_type": "markdown"}
    ).json()
    return str(activity["id"])


def test_new_activity_defaults_to_untrusted(client: TestClient) -> None:
    _signup(client, "a@example.com")
    activity_id = _create_activity(client)
    fetched = client.get(f"/api/activities/{activity_id}/edit").json()
    assert fetched["trusted"] is False


def test_owner_can_toggle_trusted(client: TestClient) -> None:
    _signup(client, "a@example.com")
    activity_id = _create_activity(client)

    response = client.patch(f"/api/activities/{activity_id}", json={"trusted": True})
    assert response.status_code == 200
    assert response.json() == {"id": activity_id, "trusted": True}

    fetched = client.get(f"/api/activities/{activity_id}/edit").json()
    assert fetched["trusted"] is True

    response = client.patch(f"/api/activities/{activity_id}", json={"trusted": False})
    assert response.status_code == 200
    assert response.json()["trusted"] is False


def test_non_owner_cannot_toggle_trusted(client: TestClient) -> None:
    _signup(client, "a@example.com")
    activity_id = _create_activity(client)
    client.cookies.clear()
    _signup(client, "b@example.com")

    response = client.patch(f"/api/activities/{activity_id}", json={"trusted": True})
    assert response.status_code == 404


def test_unauthenticated_cannot_toggle_trusted(client: TestClient) -> None:
    _signup(client, "a@example.com")
    activity_id = _create_activity(client)
    client.cookies.clear()

    response = client.patch(f"/api/activities/{activity_id}", json={"trusted": True})
    assert response.status_code == 401
