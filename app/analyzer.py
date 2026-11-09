import ast
import hashlib
from dataclasses import dataclass

DEFAULT_RULES = [
    {"code": "long_method", "name": "Длинный метод", "category": "bloaters", "threshold": 30},
    {"code": "long_parameter_list", "name": "Длинный список параметров", "category": "bloaters", "threshold": 5},
    {"code": "large_class", "name": "Большой класс", "category": "bloaters", "threshold": 15},
    {"code": "deep_nesting", "name": "Глубокая вложенность", "category": "complexity", "threshold": 4},
    {"code": "duplicate_code", "name": "Дублирование кода", "category": "dispensables", "threshold": 6},
    {"code": "unused_import", "name": "Неиспользуемый импорт", "category": "dispensables", "threshold": 1,
     "autofix": True},
]

NESTING_NODES = (ast.If, ast.For, ast.AsyncFor, ast.While, ast.With, ast.AsyncWith, ast.Try, ast.Match)


@dataclass
class Finding:
    rule: str
    path: str
    line: int
    end_line: int
    severity: str
    message: str


def plural(n, forms):
    if n % 10 == 1 and n % 100 != 11:
        return f"{n} {forms[0]}"
    if 2 <= n % 10 <= 4 and not 12 <= n % 100 <= 14:
        return f"{n} {forms[1]}"
    return f"{n} {forms[2]}"


LINES = ("строку", "строки", "строк")
PARAMS = ("параметр", "параметра", "параметров")
LEVELS = ("уровня", "уровней", "уровней")
METHODS = ("метод", "метода", "методов")
BLOCK = ("строки", "строк", "строк")


def severity(value, threshold):
    return "high" if value >= 2 * threshold else "medium"


def _functions(tree):
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            yield node


def _depth(node, level=0):
    best = level
    for child in ast.iter_child_nodes(node):
        if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            continue
        nxt = level + 1 if isinstance(child, NESTING_NODES) else level
        best = max(best, _depth(child, nxt))
    return best


def check_functions(tree, path, rules):
    found = []
    for fn in _functions(tree):
        if "long_method" in rules:
            limit = rules["long_method"]
            size = fn.end_lineno - fn.lineno + 1
            if size > limit:
                found.append(Finding("long_method", path, fn.lineno, fn.end_lineno, severity(size, limit),
                                     f"метод {fn.name} занимает {plural(size, LINES)} (порог {limit})"))
        if "long_parameter_list" in rules:
            limit = rules["long_parameter_list"]
            a = fn.args
            params = [x.arg for x in a.posonlyargs + a.args + a.kwonlyargs if x.arg not in ("self", "cls")]
            if len(params) > limit:
                found.append(Finding("long_parameter_list", path, fn.lineno, fn.lineno, severity(len(params), limit),
                                     f"у метода {fn.name} {plural(len(params), PARAMS)} (порог {limit})"))
        if "deep_nesting" in rules:
            limit = rules["deep_nesting"]
            depth = _depth(fn)
            if depth > limit:
                found.append(Finding("deep_nesting", path, fn.lineno, fn.end_lineno, severity(depth, limit),
                                     f"вложенность в {fn.name} достигает {plural(depth, LEVELS)} (порог {limit})"))
    return found


def check_classes(tree, path, rules):
    if "large_class" not in rules:
        return []
    limit = rules["large_class"]
    found = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            methods = [n for n in node.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]
            if len(methods) > limit:
                found.append(Finding("large_class", path, node.lineno, node.end_lineno,
                                     severity(len(methods), limit),
                                     f"класс {node.name} содержит {plural(len(methods), METHODS)} (порог {limit})"))
    return found


def unused_imports(tree):
    imported = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imported.append((alias.asname or alias.name.split(".")[0], node))
        elif isinstance(node, ast.ImportFrom) and node.module != "__future__":
            for alias in node.names:
                if alias.name != "*":
                    imported.append((alias.asname or alias.name, node))
    used = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Name):
            used.add(node.id)
        elif isinstance(node, ast.Constant) and isinstance(node.value, str):
            used.add(node.value)
    return [(name, node) for name, node in imported if name not in used]


def check_imports(tree, path, rules):
    if "unused_import" not in rules or path.endswith("__init__.py"):
        return []
    return [Finding("unused_import", path, node.lineno, node.end_lineno, "low", f"импорт {name} не используется")
            for name, node in unused_imports(tree)]


def _normalized(content):
    rows = []
    for number, raw in enumerate(content.splitlines(), start=1):
        text = raw.strip()
        if text and not text.startswith("#"):
            rows.append((number, text))
    return rows


def check_duplicates(files, rules):
    if "duplicate_code" not in rules:
        return []
    size = rules["duplicate_code"]
    seen = {}
    found = []
    for path, content in files.items():
        rows = _normalized(content)
        i = 0
        while i + size <= len(rows):
            block = "\n".join(t for _, t in rows[i:i + size])
            key = hashlib.sha1(block.encode()).hexdigest()
            first = seen.get(key)
            if first and not (first[0] == path and i < first[1] + size):
                other_path, j, other_rows = first
                length = size
                while (i + length < len(rows) and j + length < len(other_rows)
                       and rows[i + length][1] == other_rows[j + length][1]):
                    length += 1
                found.append(Finding("duplicate_code", path, rows[i][0], rows[i + length - 1][0],
                                     severity(length, size),
                                     f"блок из {plural(length, BLOCK)} повторяет {other_path}:{other_rows[j][0]}"))
                i += length
                continue
            seen.setdefault(key, (path, i, rows))
            i += 1
    return found


def analyze(files, rules):
    # rules: {код правила: порог}, только включённые
    findings = []
    for path, content in files.items():
        tree = ast.parse(content)
        findings += check_functions(tree, path, rules)
        findings += check_classes(tree, path, rules)
        findings += check_imports(tree, path, rules)
    findings += check_duplicates(files, rules)
    return sorted(findings, key=lambda f: (f.path, f.line, f.rule))
