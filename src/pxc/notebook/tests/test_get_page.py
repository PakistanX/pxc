from collections.abc import Generator
from unittest.mock import patch

from fastapi import HTTPException
from fastapi.testclient import TestClient
import pytest
from sqlmodel import Session

from pxc.notebook.app import app
from pxc.notebook.auth import hash_password
from pxc.notebook.db import get_session
from pxc.notebook.models import Course, Page, PageActivity, User


@pytest.fixture(name="user")
def user_fixture(session: Session) -> User:
    password_hash, password_salt = hash_password("password123")
    user = User(
        email="test@example.com",
        password_hash=password_hash,
        password_salt=password_salt,
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


@pytest.fixture(name="client")
def client_fixture(session: Session, user: User) -> Generator[TestClient, None, None]:
    def override_get_session() -> Generator[Session, None, None]:
        yield session

    app.dependency_overrides[get_session] = override_get_session
    client = TestClient(app)
    login = client.post(
        "/api/auth/login",
        json={"email": user.email, "password": "password123"},
    )
    assert login.status_code == 200
    yield client
    app.dependency_overrides.clear()


def test_get_page_degrades_when_activity_files_missing(
    client: TestClient, session: Session, user: User
) -> None:
    course = Course(title="Test Course", owner_id=user.id)
    session.add(course)
    session.commit()
    page = Page(title="Test Page", course_id=course.id)
    session.add(page)
    session.commit()
    good = PageActivity(page_id=page.id, activity_type="markdown", position=0)
    broken = PageActivity(
        page_id=page.id, activity_type="@nobody/missing-activity", position=1
    )
    session.add(good)
    session.add(broken)
    session.commit()
    session.refresh(good)
    session.refresh(broken)

    real_find = __import__(
        "pxc.notebook.views.activities", fromlist=["find_activity_dir"]
    ).find_activity_dir

    def fake_find(activity_type: str):  # type: ignore[no-untyped-def]
        if activity_type == broken.activity_type:
            raise HTTPException(
                status_code=404, detail=f"Activity '{activity_type}' not found"
            )
        return real_find(activity_type)

    with patch(
        "pxc.notebook.views.activities.find_activity_dir", side_effect=fake_find
    ):
        response = client.get(f"/api/pages/{page.id}")

    assert response.status_code == 200
    body = response.json()
    activities = {a["id"]: a for a in body["activities"]}
    assert len(activities) == 2
    assert "error" not in activities[good.id]
    assert activities[broken.id]["error"] == "Activity files not found"
    assert activities[broken.id]["activity_type"] == broken.activity_type


def test_delete_activity_with_missing_files(
    client: TestClient, session: Session, user: User
) -> None:
    course = Course(title="Test Course", owner_id=user.id)
    session.add(course)
    session.commit()
    page = Page(title="Test Page", course_id=course.id)
    session.add(page)
    session.commit()
    broken = PageActivity(
        page_id=page.id, activity_type="@nobody/missing-activity", position=0
    )
    session.add(broken)
    session.commit()
    session.refresh(broken)

    def fake_find(activity_type: str):  # type: ignore[no-untyped-def]
        raise HTTPException(
            status_code=404, detail=f"Activity '{activity_type}' not found"
        )

    with patch(
        "pxc.notebook.views.activities.find_activity_dir", side_effect=fake_find
    ):
        response = client.delete(f"/api/activities/{broken.id}")

    assert response.status_code == 204
    assert session.get(PageActivity, broken.id) is None
