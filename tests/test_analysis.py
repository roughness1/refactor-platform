import pytest


def smells_by_rule(client, analysis_id):
    result = {}
    for s in client.get(f"/analyses/{analysis_id}/smells").json():
        result.setdefault(s["rule_code"], []).append(s)
    return result


def test_analysis_finds_expected_smells(client, analysed):
    assert analysed["status"] == "completed"
    assert analysed["files_count"] == 3
    found = smells_by_rule(client, analysed["id"])
    assert len(found["unused_import"]) == 4
    assert len(found["long_parameter_list"]) == 1
    assert len(found["deep_nesting"]) == 1
    assert len(found["duplicate_code"]) == 1
    assert "long_method" not in found


def test_analysis_without_files_conflict(client, project):
    r = client.post(f"/projects/{project['id']}/analyses")
    assert r.status_code == 409


@pytest.mark.parametrize("threshold, expected", [(7, 0), (6, 1)])
def test_parameter_threshold_boundary(client, project, threshold, expected):
    rule = next(r for r in client.get("/rules").json() if r["code"] == "long_parameter_list")
    client.patch(f"/rules/{rule['id']}", json={"threshold": threshold})
    pid = project["id"]
    client.post(f"/projects/{pid}/files", json={"path": "m.py", "content": "def f(a, b, c, d, e, f, g):\n    pass\n"})
    analysis = client.post(f"/projects/{pid}/analyses").json()
    assert len(smells_by_rule(client, analysis["id"]).get("long_parameter_list", [])) == expected


def test_disabled_rule_is_skipped(client, project):
    rule = next(r for r in client.get("/rules").json() if r["code"] == "unused_import")
    client.patch(f"/rules/{rule['id']}", json={"enabled": False})
    pid = project["id"]
    client.post(f"/projects/{pid}/files", json={"path": "m.py", "content": "import os\n"})
    analysis = client.post(f"/projects/{pid}/analyses").json()
    assert analysis["smells_count"] == 0


def test_rule_threshold_validation(client):
    assert client.patch("/rules/1", json={"threshold": 0}).status_code == 422
    assert client.patch("/rules/999", json={"threshold": 5}).status_code == 404


def test_filter_smells_by_severity(client, analysed):
    low = client.get(f"/analyses/{analysed['id']}/smells?severity=low").json()
    assert low and all(s["severity"] == "low" for s in low)
    assert client.get(f"/analyses/{analysed['id']}/smells?severity=critical").status_code == 422


@pytest.mark.parametrize("fmt, marker", [("json", None), ("md", "| Критичность |"), ("html", "<table")],
                         ids=["json", "md", "html"])
def test_report_formats(client, analysed, fmt, marker):
    r = client.get(f"/analyses/{analysed['id']}/report?format={fmt}")
    assert r.status_code == 200
    if fmt == "json":
        assert r.json()["total"] == analysed["smells_count"]
    else:
        assert marker in r.text


def test_report_unknown_format(client, analysed):
    assert client.get(f"/analyses/{analysed['id']}/report?format=pdf").status_code == 422


def test_metrics_exposed(client, analysed):
    body = client.get("/metrics").text
    assert "http_requests_total" in body
    assert "refactor_smells_detected_total" in body


@pytest.mark.parametrize("body_lines, expected", [(29, 0), (30, 1)])
def test_long_method_boundary(client, project, body_lines, expected):
    code = "def big():\n" + "    x = 1\n" * body_lines
    pid = project["id"]
    client.post(f"/projects/{pid}/files", json={"path": "big.py", "content": code})
    analysis = client.post(f"/projects/{pid}/analyses").json()
    assert len(smells_by_rule(client, analysis["id"]).get("long_method", [])) == expected


def test_large_class_detected_with_lower_threshold(client, project):
    rule = next(r for r in client.get("/rules").json() if r["code"] == "large_class")
    client.patch(f"/rules/{rule['id']}", json={"threshold": 2})
    code = "class God:\n" + "".join(f"    def m{i}(self):\n        return {i}\n" for i in range(5))
    pid = project["id"]
    client.post(f"/projects/{pid}/files", json={"path": "god.py", "content": code})
    analysis = client.post(f"/projects/{pid}/analyses").json()
    smell = smells_by_rule(client, analysis["id"])["large_class"][0]
    assert smell["severity"] == "high"
