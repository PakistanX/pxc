from fastapi.testclient import TestClient


def _signup(client: TestClient, email: str) -> None:
    response = client.post(
        "/api/auth/signup",
        json={"email": email, "password": "password123"},
    )
    assert response.status_code == 201


def _create_course_with_activity(client: TestClient) -> tuple[str, str, str]:
    course = client.post("/api/courses", json={"title": "Course A"}).json()
    page = client.post(
        f"/api/courses/{course['id']}/pages", json={"title": "Page 1"}
    ).json()
    activity = client.post(
        f"/api/pages/{page['id']}/activities",
        json={"activity_type": "markdown"},
    ).json()
    return course["id"], page["id"], activity["id"]


def test_list_courses_only_returns_own(client: TestClient) -> None:
    _signup(client, "a@example.com")
    client.post("/api/courses", json={"title": "A's course"})
    client.cookies.clear()
    _signup(client, "b@example.com")
    response = client.get("/api/courses")
    assert response.status_code == 200
    assert response.json() == []


def test_list_shared_courses_returns_others(client: TestClient) -> None:
    _signup(client, "a@example.com")
    course = client.post("/api/courses", json={"title": "A's course"}).json()
    client.cookies.clear()
    _signup(client, "b@example.com")
    response = client.get("/api/shared-courses")
    assert response.status_code == 200
    shared = response.json()
    assert len(shared) == 1
    assert shared[0]["id"] == course["id"]
    assert shared[0]["owner_name"] == "a"


def test_shared_courses_excludes_own(client: TestClient) -> None:
    _signup(client, "a@example.com")
    client.post("/api/courses", json={"title": "A's course"})
    response = client.get("/api/shared-courses")
    assert response.status_code == 200
    assert response.json() == []


def test_non_owner_can_view_course(client: TestClient) -> None:
    _signup(client, "a@example.com")
    course_id, page_id, _ = _create_course_with_activity(client)
    client.cookies.clear()
    _signup(client, "b@example.com")

    course_resp = client.get(f"/api/courses/{course_id}")
    assert course_resp.status_code == 200
    course = course_resp.json()
    assert course["is_owner"] is False
    assert course["owner_name"] == "a"

    page_resp = client.get(f"/api/pages/{page_id}")
    assert page_resp.status_code == 200
    page = page_resp.json()
    assert page["is_owner"] is False
    # Non-owners get no activity-types palette.
    assert page["activity_types"] == []
    # Activities are reported in play permission for non-owners.
    assert all(a["permission"] == "play" for a in page["activities"])


def test_owner_sees_is_owner_true(client: TestClient) -> None:
    _signup(client, "a@example.com")
    course_id, page_id, _ = _create_course_with_activity(client)
    assert client.get(f"/api/courses/{course_id}").json()["is_owner"] is True
    assert client.get(f"/api/pages/{page_id}").json()["is_owner"] is True


def test_non_owner_can_play_activity(client: TestClient) -> None:
    _signup(client, "a@example.com")
    _course_id, _page_id, activity_id = _create_course_with_activity(client)
    client.cookies.clear()
    _signup(client, "b@example.com")

    play = client.post(
        f"/api/activity/{activity_id}/play/actions",
        json={"name": "config.save", "value": {"markdown_content": "hi"}},
    )
    # play permission is allowed; markdown's config.save may itself be edit-only,
    # so we only assert the endpoint is reachable (200 or 400 — never 403/404).
    assert play.status_code in (200, 400)


def test_non_owner_cannot_request_edit_permission(client: TestClient) -> None:
    _signup(client, "a@example.com")
    _course_id, _page_id, activity_id = _create_course_with_activity(client)
    client.cookies.clear()
    _signup(client, "b@example.com")

    # /edit/actions, /edit/ws, and GET /api/activities/{id}/edit are all 403.
    assert (
        client.post(
            f"/api/activity/{activity_id}/edit/actions",
            json={"name": "config.save", "value": {"markdown_content": "x"}},
        ).status_code
        == 403
    )
    assert client.get(f"/api/activities/{activity_id}/edit").status_code == 403
    # play remains accessible.
    assert client.get(f"/api/activities/{activity_id}/play").status_code == 200


def test_non_owner_can_load_activity_asset(client: TestClient) -> None:
    _signup(client, "a@example.com")
    _course_id, _page_id, activity_id = _create_course_with_activity(client)
    client.cookies.clear()
    _signup(client, "b@example.com")

    response = client.get(f"/a/{activity_id}/ui.js")
    assert response.status_code == 200


def test_non_owner_cannot_mutate_course(client: TestClient) -> None:
    _signup(client, "a@example.com")
    course_id, page_id, activity_id = _create_course_with_activity(client)
    client.cookies.clear()
    _signup(client, "b@example.com")

    assert (
        client.patch(f"/api/courses/{course_id}", json={"title": "x"}).status_code
        == 404
    )
    assert client.delete(f"/api/courses/{course_id}").status_code == 404
    assert (
        client.post(f"/api/courses/{course_id}/pages", json={"title": "x"}).status_code
        == 404
    )
    assert client.patch(f"/api/pages/{page_id}", json={"title": "x"}).status_code == 404
    assert client.delete(f"/api/pages/{page_id}").status_code == 404
    assert (
        client.post(
            f"/api/pages/{page_id}/activities",
            json={"activity_type": "markdown"},
        ).status_code
        == 404
    )
    assert client.delete(f"/api/activities/{activity_id}").status_code == 404
    assert (
        client.post(
            f"/api/activities/{activity_id}/move",
            json={"direction": "up", "page_id": page_id},
        ).status_code
        == 404
    )


def test_owner_can_edit_own_activity(client: TestClient) -> None:
    _signup(client, "a@example.com")
    _course_id, _page_id, activity_id = _create_course_with_activity(client)

    edit = client.post(
        f"/api/activity/{activity_id}/edit/actions",
        json={"name": "config.save", "value": {"markdown_content": "hello"}},
    )
    assert edit.status_code == 200


def test_unauthenticated_cannot_list_courses(client: TestClient) -> None:
    response = client.get("/api/courses")
    assert response.status_code == 401
