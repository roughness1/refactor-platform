"""нагрузка для smoke-проверки: python scripts/smoke_load.py http://localhost:8000 120"""
import json
import random
import sys
import time
import urllib.error
import urllib.request

BASE = sys.argv[1].rstrip("/")
DURATION = float(sys.argv[2]) if len(sys.argv) > 2 else 60

LEGACY = '''import os
import sys
import json
from collections import OrderedDict, defaultdict


def create_order(customer, items, address, phone, email, discount, promo_code):
    total = 0
    for item in items:
        if item["qty"] > 0:
            if item["price"] > 0:
                if discount:
                    if promo_code:
                        total += item["price"] * item["qty"] * 0.9
    return {"customer": customer, "total": total, "groups": defaultdict(list)}
'''


def call(method, path, body=None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(BASE + path, data=data, method=method, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            text = r.read().decode()
            return r.status, json.loads(text) if text.startswith(("{", "[")) else text
    except urllib.error.HTTPError as e:
        return e.code, None


status, project = call("POST", "/projects", {"name": "legacy-shop"})
pid = project["id"]
call("POST", f"/projects/{pid}/files", {"path": "shop/orders.py", "content": LEGACY})
end = time.time() + DURATION
runs = 0
while time.time() < end:
    runs += 1
    _, analysis = call("POST", f"/projects/{pid}/analyses")
    _, smells = call("GET", f"/analyses/{analysis['id']}/smells")
    call("GET", f"/analyses/{analysis['id']}/report?format={random.choice(['json', 'md', 'html'])}")
    fixable = [s for s in smells if s["fixable"]]
    if fixable:
        s = random.choice(fixable)
        call("POST", f"/smells/{s['id']}/fix?preview=true")
        code, fix = call("POST", f"/smells/{s['id']}/fix")
        if code == 200:
            call("POST", f"/fixes/{fix['id']}/rollback")
    call("GET", random.choice(["/projects", "/rules", "/health"]))
    if random.random() < 0.2:
        call("GET", "/projects/999")
    time.sleep(random.uniform(0.2, 0.6))
print(f"циклов нагрузки: {runs}")
