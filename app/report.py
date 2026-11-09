import html
from collections import Counter

SEVERITY_ORDER = {"high": 0, "medium": 1, "low": 2}


def build(analysis, smells):
    rows = sorted(smells, key=lambda s: (SEVERITY_ORDER[s.severity], s.file_path, s.line))
    return {
        "analysis_id": analysis.id,
        "project": analysis.project.name,
        "started_at": analysis.started_at.isoformat(),
        "duration_ms": round(analysis.duration_ms, 2),
        "files": analysis.files_count,
        "total": len(rows),
        "by_severity": dict(Counter(s.severity for s in rows)),
        "by_rule": dict(Counter(s.rule.code for s in rows)),
        "smells": [
            {"id": s.id, "rule": s.rule.code, "severity": s.severity, "file": s.file_path,
             "line": s.line, "message": s.message, "fixable": s.rule.autofix and s.fix is None}
            for s in rows
        ],
    }


def to_markdown(data):
    out = [f"# Отчёт по анализу №{data['analysis_id']} — {data['project']}", "",
           f"Файлов: {data['files']}, запахов: {data['total']}, время: {data['duration_ms']} мс", "",
           "| Критичность | Правило | Файл:строка | Описание |", "|---|---|---|---|"]
    for s in data["smells"]:
        out.append(f"| {s['severity']} | {s['rule']} | {s['file']}:{s['line']} | {s['message']} |")
    return "\n".join(out) + "\n"


def to_html(data):
    rows = "".join(
        f"<tr><td>{s['severity']}</td><td>{s['rule']}</td><td>{html.escape(s['file'])}:{s['line']}</td>"
        f"<td>{html.escape(s['message'])}</td></tr>" for s in data["smells"])
    return (f"<!DOCTYPE html><html lang='ru'><head><meta charset='utf-8'>"
            f"<title>Отчёт №{data['analysis_id']}</title></head><body>"
            f"<h1>Отчёт по анализу №{data['analysis_id']} — {html.escape(data['project'])}</h1>"
            f"<p>Файлов: {data['files']}, запахов: {data['total']}, время: {data['duration_ms']} мс</p>"
            f"<table border='1'><tr><th>Критичность</th><th>Правило</th><th>Файл:строка</th>"
            f"<th>Описание</th></tr>{rows}</table></body></html>")
