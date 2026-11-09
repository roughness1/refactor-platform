import ast
import difflib


class FixError(Exception):
    pass


def _render(node, names):
    parts = []
    for alias in names:
        parts.append(f"{alias.name} as {alias.asname}" if alias.asname else alias.name)
    if isinstance(node, ast.Import):
        return "import " + ", ".join(parts)
    module = "." * node.level + (node.module or "")
    return f"from {module} import " + ", ".join(parts)


def remove_unused_import(content, line, name):
    tree = ast.parse(content)
    target = None
    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)) and node.lineno == line:
            target = node
            break
    if target is None:
        raise FixError("импорт на этой строке не найден — файл изменился после анализа")

    def bound(alias):
        if isinstance(target, ast.Import):
            return alias.asname or alias.name.split(".")[0]
        return alias.asname or alias.name

    rest = [a for a in target.names if bound(a) != name]
    if len(rest) == len(target.names):
        raise FixError(f"имя {name} в импорте не найдено")

    lines = content.splitlines(keepends=True)
    start, end = target.lineno - 1, target.end_lineno
    indent = lines[start][:len(lines[start]) - len(lines[start].lstrip())]
    replacement = [indent + _render(target, rest) + "\n"] if rest else []
    return "".join(lines[:start] + replacement + lines[end:])


def make_diff(path, old, new):
    return "".join(difflib.unified_diff(old.splitlines(keepends=True), new.splitlines(keepends=True),
                                        fromfile=f"a/{path}", tofile=f"b/{path}"))
