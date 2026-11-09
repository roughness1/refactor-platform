import os
import tempfile

import pytest

os.environ["DATABASE_URL"] = "sqlite:///" + os.path.join(tempfile.mkdtemp(), "test.db")

from fastapi.testclient import TestClient  # noqa: E402

from app.db import Base, engine  # noqa: E402
from app.main import app, seed_rules  # noqa: E402

SMELLY = '''import os
import sys
import json as js
from collections import OrderedDict, defaultdict


def calc(a, b, c, d, e, f, g):
    total = a + b + c
    total += d + e + f + g
    return total


def process(items):
    result = defaultdict(int)
    for item in items:
        if item:
            for part in item:
                if part:
                    while part > 0:
                        if part % 2:
                            result[part] += 1
                        part -= 1
    return result
'''

DUPLICATE_BLOCK = '''
def report_a(rows):
    header = "id;name;value"
    lines = [header]
    for row in rows:
        lines.append(f"{row[0]};{row[1]};{row[2]}")
    text = "\\n".join(lines)
    return text.strip()
'''


@pytest.fixture()
def client():
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    seed_rules()
    with TestClient(app) as c:
        yield c


@pytest.fixture()
def project(client):
    return client.post("/projects", json={"name": "demo"}).json()


@pytest.fixture()
def analysed(client, project):
    pid = project["id"]
    client.post(f"/projects/{pid}/files", json={"path": "src/smelly.py", "content": SMELLY})
    client.post(f"/projects/{pid}/files", json={"path": "src/a.py", "content": DUPLICATE_BLOCK})
    client.post(f"/projects/{pid}/files",
                json={"path": "src/b.py", "content": DUPLICATE_BLOCK.replace("report_a", "report_b")})
    return client.post(f"/projects/{pid}/analyses").json()
