def first_smell(client, analysis_id, rule):
    return next(s for s in client.get(f"/analyses/{analysis_id}/smells?rule={rule}").json())


def file_content(client, project_id, path):
    from app.db import SessionLocal
    from app.models import SourceFile
    with SessionLocal() as db:
        return db.query(SourceFile).filter_by(project_id=project_id, path=path).one().content


def test_preview_does_not_change_file(client, analysed):
    smell = first_smell(client, analysed["id"], "unused_import")
    before = file_content(client, analysed["project_id"], smell["file_path"])
    r = client.post(f"/smells/{smell['id']}/fix?preview=true")
    assert r.status_code == 200
    assert r.json()["status"] == "preview"
    assert r.json()["diff"].startswith("--- a/")
    assert file_content(client, analysed["project_id"], smell["file_path"]) == before


def test_apply_and_rollback(client, analysed):
    smell = first_smell(client, analysed["id"], "unused_import")
    before = file_content(client, analysed["project_id"], smell["file_path"])
    fix = client.post(f"/smells/{smell['id']}/fix").json()
    assert fix["status"] == "applied"
    assert "-import os" in fix["diff"]
    assert "import os\n" not in file_content(client, analysed["project_id"], smell["file_path"])
    assert client.post(f"/smells/{smell['id']}/fix").status_code == 409
    back = client.post(f"/fixes/{fix['id']}/rollback")
    assert back.json()["status"] == "rolled_back"
    assert file_content(client, analysed["project_id"], smell["file_path"]) == before
    assert client.post(f"/fixes/{fix['id']}/rollback").status_code == 409


def test_partial_from_import_keeps_used_name(client, analysed):
    smells = client.get(f"/analyses/{analysed['id']}/smells?rule=unused_import").json()
    target = next(s for s in smells if "OrderedDict" in s["message"])
    fix = client.post(f"/smells/{target['id']}/fix").json()
    assert "+from collections import defaultdict" in fix["diff"]


def test_fix_not_supported_for_rule(client, analysed):
    smell = first_smell(client, analysed["id"], "deep_nesting")
    r = client.post(f"/smells/{smell['id']}/fix")
    assert r.status_code == 422
    assert "не поддерживается" in r.json()["detail"]


def test_fix_missing_smell(client):
    assert client.post("/smells/12345/fix").status_code == 404
    assert client.post("/fixes/12345/rollback").status_code == 404
