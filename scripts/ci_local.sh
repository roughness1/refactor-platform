#!/usr/bin/env bash
# те же этапы, что в .github/workflows/ci.yml, но локально (сценарий В)
set -e
echo "== lint =="
flake8 app tests scripts && echo "flake8: замечаний нет"
echo "== test =="
pytest --cov=app --cov-report=term --cov-fail-under=80
echo "== build =="
if command -v docker >/dev/null && docker info >/dev/null 2>&1; then
  docker build -t refactor-platform:local .
else
  echo "docker недоступен — этап build пропущен"
fi
