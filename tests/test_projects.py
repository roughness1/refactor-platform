import pytest


def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok", "database": "ok"}


def test_create_and_get_project(client):
    r = client.post("/projects", json={"name": "legacy-shop", "repo_url": "https://git.example/shop.git"})
    assert r.status_code == 201
    pid = r.json()["id"]
    got = client.get(f"/projects/{pid}").json()
    assert got["name"] == "legacy-shop"
    assert got["language"] == "python"


@pytest.mark.parametrize("name, code", [("", 422), ("x" * 100, 201), ("x" * 101, 422)],
                         ids=["empty", "len100", "len101"])
def test_project_name_boundaries(client, name, code):
    assert client.post("/projects", json={"name": name}).status_code == code


def test_duplicate_project_name(client, project):
    r = client.post("/projects", json={"name": "demo"})
    assert r.status_code == 409


def test_missing_project_404(client):
    r = client.get("/projects/999")
    assert r.status_code == 404
    assert "не найден" in r.json()["detail"]


def test_update_and_delete_project(client, project):
    pid = project["id"]
    r = client.put(f"/projects/{pid}", json={"name": "renamed"})
    assert r.json()["name"] == "renamed"
    assert client.delete(f"/projects/{pid}").status_code == 204
    assert client.get(f"/projects/{pid}").status_code == 404


def test_list_projects_pagination(client):
    for i in range(3):
        client.post("/projects", json={"name": f"p{i}"})
    assert len(client.get("/projects?limit=2").json()) == 2
    assert client.get("/projects?limit=0").status_code == 422


def test_upload_rejects_syntax_error(client, project):
    r = client.post(f"/projects/{project['id']}/files", json={"path": "bad.py", "content": "def f(:\n"})
    assert r.status_code == 422
    assert "синтаксическая ошибка" in r.json()["detail"]


def test_upload_rejects_non_python_path(client, project):
    r = client.post(f"/projects/{project['id']}/files", json={"path": "readme.md", "content": "x"})
    assert r.status_code == 422
