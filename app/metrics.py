from prometheus_client import Counter, Histogram

HTTP_REQUESTS = Counter("http_requests_total", "Количество HTTP-запросов", ["method", "path", "status"])
HTTP_LATENCY = Histogram("http_request_duration_seconds", "Время обработки запроса", ["method", "path"],
                         buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5))
ANALYSES = Counter("refactor_analyses_total", "Выполненные анализы", ["status"])
ANALYSIS_TIME = Histogram("refactor_analysis_duration_seconds", "Длительность анализа проекта",
                          buckets=(0.01, 0.05, 0.1, 0.25, 0.5, 1, 2, 5, 10))
SMELLS = Counter("refactor_smells_detected_total", "Найденные запахи кода", ["rule"])
FIXES = Counter("refactor_fixes_total", "Операции с исправлениями", ["action"])
