# Платформа рефакторинга (вариант №14)

REST API для поиска запахов кода в Python-проектах, автоисправлений с предпросмотром и откатом и отчётов.
Учебный проект по дисциплине «Технологии разработки программных средств».

## Запуск локально

```bash
python -m venv .venv
.venv\Scripts\activate          # Windows; в Linux/macOS: source .venv/bin/activate
pip install -r requirements-dev.txt
uvicorn app.main:app --reload
```

Swagger UI: http://localhost:8000/docs, метрики: http://localhost:8000/metrics

## Тесты и линтер

```bash
flake8 app tests
pytest --cov=app --cov-report=term
```

## Docker

```bash
docker compose up --build -d      # app + PostgreSQL + Prometheus + Grafana
docker compose ps
```

- API — http://localhost:8000/docs
- Prometheus — http://localhost:9090
- Grafana — http://localhost:3000 (admin / admin), дашборд «Платформа рефакторинга»

## Основные маршруты

| Метод | Путь | Назначение |
|---|---|---|
| POST | /projects | создать проект |
| POST | /projects/{id}/files | загрузить файл .py |
| POST | /projects/{id}/analyses | запустить анализ |
| GET | /analyses/{id}/smells | найденные запахи |
| GET | /analyses/{id}/report?format=json\|md\|html | отчёт |
| POST | /smells/{id}/fix?preview=true | diff без применения |
| POST | /smells/{id}/fix | применить исправление |
| POST | /fixes/{id}/rollback | откатить исправление |
