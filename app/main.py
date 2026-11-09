import ast
import re
import time
from collections import Counter
from contextlib import asynccontextmanager
from typing import Literal

from fastapi import Depends, FastAPI, HTTPException, Query, Request, Response, status
from fastapi.responses import HTMLResponse, PlainTextResponse
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app import analyzer, fixer, report
from app.db import Base, SessionLocal, engine, get_db
from app.metrics import ANALYSES, ANALYSIS_TIME, FIXES, HTTP_LATENCY, HTTP_REQUESTS, SMELLS
from app.models import Analysis, Fix, Project, Rule, Smell, SourceFile
from app.schemas import (AnalysisOut, FileIn, FileOut, FixOut, ProjectCreate, ProjectOut, ProjectUpdate,
                         RuleOut, RuleUpdate, SmellOut)


def seed_rules():
    with SessionLocal() as db:
        existing = set(db.scalars(select(Rule.code)))
        for rule in analyzer.DEFAULT_RULES:
            if rule["code"] not in existing:
                db.add(Rule(**rule))
        db.commit()


@asynccontextmanager
async def lifespan(app):
    Base.metadata.create_all(engine)
    seed_rules()
    yield


app = FastAPI(title="Платформа рефакторинга", version="1.0.0", lifespan=lifespan,
              description="Поиск запахов кода, автоисправления и отчёты (вариант №14)")


@app.middleware("http")
async def collect_metrics(request: Request, call_next):
    start = time.perf_counter()
    response = await call_next(request)
    route = request.scope.get("route")
    path = route.path if route else "unmatched"
    if path != "/metrics":
        HTTP_REQUESTS.labels(request.method, path, str(response.status_code)).inc()
        HTTP_LATENCY.labels(request.method, path).observe(time.perf_counter() - start)
    return response


def get_or_404(db, model, obj_id, what):
    obj = db.get(model, obj_id)
    if obj is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"{what} {obj_id} не найден")
    return obj


def smell_out(s):
    return SmellOut(id=s.id, rule_code=s.rule.code, file_path=s.file_path, line=s.line, end_line=s.end_line,
                    severity=s.severity, message=s.message, fixable=s.rule.autofix and s.fix is None)


def analysis_out(a):
    return AnalysisOut(id=a.id, project_id=a.project_id, status=a.status, started_at=a.started_at,
                       duration_ms=round(a.duration_ms, 2), files_count=a.files_count,
                       smells_count=len(a.smells), by_severity=dict(Counter(s.severity for s in a.smells)))


@app.get("/health", tags=["service"])
def health(db: Session = Depends(get_db)):
    db.execute(text("SELECT 1"))
    return {"status": "ok", "database": "ok"}


@app.get("/metrics", tags=["service"], include_in_schema=False)
def metrics():
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)


@app.post("/projects", response_model=ProjectOut, status_code=201, tags=["projects"])
def create_project(data: ProjectCreate, db: Session = Depends(get_db)):
    project = Project(**data.model_dump())
    db.add(project)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, f"проект {data.name} уже существует")
    return project


@app.get("/projects", response_model=list[ProjectOut], tags=["projects"])
def list_projects(skip: int = Query(0, ge=0), limit: int = Query(50, ge=1, le=100), db: Session = Depends(get_db)):
    return db.scalars(select(Project).order_by(Project.id).offset(skip).limit(limit)).all()


@app.get("/projects/{project_id}", response_model=ProjectOut, tags=["projects"])
def get_project(project_id: int, db: Session = Depends(get_db)):
    return get_or_404(db, Project, project_id, "проект")


@app.put("/projects/{project_id}", response_model=ProjectOut, tags=["projects"])
def update_project(project_id: int, data: ProjectUpdate, db: Session = Depends(get_db)):
    project = get_or_404(db, Project, project_id, "проект")
    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(project, key, value)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "проект с таким именем уже существует")
    return project


@app.delete("/projects/{project_id}", status_code=204, tags=["projects"])
def delete_project(project_id: int, db: Session = Depends(get_db)):
    db.delete(get_or_404(db, Project, project_id, "проект"))
    db.commit()


@app.post("/projects/{project_id}/files", response_model=FileOut, status_code=201, tags=["projects"])
def upload_file(project_id: int, data: FileIn, db: Session = Depends(get_db)):
    get_or_404(db, Project, project_id, "проект")
    try:
        ast.parse(data.content)
    except SyntaxError as e:
        raise HTTPException(422, f"синтаксическая ошибка в строке {e.lineno}: {e.msg}")
    file = db.scalar(select(SourceFile).where(SourceFile.project_id == project_id, SourceFile.path == data.path))
    if file:
        file.content = data.content
    else:
        file = SourceFile(project_id=project_id, path=data.path, content=data.content)
        db.add(file)
    db.commit()
    return FileOut(id=file.id, path=file.path, lines=len(file.content.splitlines()))


@app.get("/projects/{project_id}/files", response_model=list[FileOut], tags=["projects"])
def list_files(project_id: int, db: Session = Depends(get_db)):
    project = get_or_404(db, Project, project_id, "проект")
    return [FileOut(id=f.id, path=f.path, lines=len(f.content.splitlines())) for f in project.files]


@app.get("/rules", response_model=list[RuleOut], tags=["rules"])
def list_rules(db: Session = Depends(get_db)):
    return db.scalars(select(Rule).order_by(Rule.id)).all()


@app.patch("/rules/{rule_id}", response_model=RuleOut, tags=["rules"])
def update_rule(rule_id: int, data: RuleUpdate, db: Session = Depends(get_db)):
    rule = get_or_404(db, Rule, rule_id, "правило")
    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(rule, key, value)
    db.commit()
    return rule


@app.post("/projects/{project_id}/analyses", response_model=AnalysisOut, status_code=201, tags=["analysis"])
def run_analysis(project_id: int, db: Session = Depends(get_db)):
    project = get_or_404(db, Project, project_id, "проект")
    if not project.files:
        raise HTTPException(status.HTTP_409_CONFLICT, "в проекте нет файлов для анализа")
    rules = {r.code: r for r in db.scalars(select(Rule).where(Rule.enabled))}
    analysis = Analysis(project=project, files_count=len(project.files))
    db.add(analysis)
    start = time.perf_counter()
    findings = analyzer.analyze({f.path: f.content for f in project.files},
                                {code: r.threshold for code, r in rules.items()})
    for f in findings:
        analysis.smells.append(Smell(rule_id=rules[f.rule].id, file_path=f.path, line=f.line,
                                     end_line=f.end_line, severity=f.severity, message=f.message))
        SMELLS.labels(f.rule).inc()
    elapsed = time.perf_counter() - start
    analysis.duration_ms = elapsed * 1000
    analysis.status = "completed"
    db.commit()
    ANALYSES.labels("completed").inc()
    ANALYSIS_TIME.observe(elapsed)
    return analysis_out(analysis)


@app.get("/analyses/{analysis_id}", response_model=AnalysisOut, tags=["analysis"])
def get_analysis(analysis_id: int, db: Session = Depends(get_db)):
    return analysis_out(get_or_404(db, Analysis, analysis_id, "анализ"))


@app.get("/analyses/{analysis_id}/smells", response_model=list[SmellOut], tags=["analysis"])
def list_smells(analysis_id: int, severity: Literal["low", "medium", "high"] | None = None,
                rule: str | None = None, db: Session = Depends(get_db)):
    analysis = get_or_404(db, Analysis, analysis_id, "анализ")
    smells = [s for s in analysis.smells
              if (severity is None or s.severity == severity) and (rule is None or s.rule.code == rule)]
    return [smell_out(s) for s in smells]


@app.get("/analyses/{analysis_id}/report", tags=["reports"])
def get_report(analysis_id: int, format: Literal["json", "md", "html"] = "json", db: Session = Depends(get_db)):
    analysis = get_or_404(db, Analysis, analysis_id, "анализ")
    data = report.build(analysis, analysis.smells)
    if format == "md":
        return PlainTextResponse(report.to_markdown(data), media_type="text/markdown; charset=utf-8")
    if format == "html":
        return HTMLResponse(report.to_html(data))
    return data


@app.post("/smells/{smell_id}/fix", response_model=FixOut, tags=["fixes"])
def fix_smell(smell_id: int, preview: bool = False, db: Session = Depends(get_db)):
    smell = get_or_404(db, Smell, smell_id, "запах")
    if not smell.rule.autofix:
        raise HTTPException(422,
                            f"для правила {smell.rule.code} автоисправление не поддерживается")
    if smell.fix is not None and smell.fix.status == "applied":
        raise HTTPException(status.HTTP_409_CONFLICT, "исправление уже применено")
    file = db.scalar(select(SourceFile).where(SourceFile.project_id == smell.analysis.project_id,
                                              SourceFile.path == smell.file_path))
    if file is None:
        raise HTTPException(status.HTTP_409_CONFLICT, "файл удалён после анализа")
    name = re.search(r"импорт (\S+) не используется", smell.message).group(1)
    try:
        new_content = fixer.remove_unused_import(file.content, smell.line, name)
    except fixer.FixError as e:
        raise HTTPException(status.HTTP_409_CONFLICT, str(e))
    diff = fixer.make_diff(file.path, file.content, new_content)
    if preview:
        FIXES.labels("preview").inc()
        return FixOut(id=None, smell_id=smell.id, status="preview", diff=diff)
    if smell.fix is not None:
        db.delete(smell.fix)
        db.flush()
    fix = Fix(smell_id=smell.id, file_id=file.id, diff=diff, old_content=file.content)
    file.content = new_content
    db.add(fix)
    db.commit()
    FIXES.labels("applied").inc()
    return FixOut(id=fix.id, smell_id=smell.id, status=fix.status, diff=diff)


@app.post("/fixes/{fix_id}/rollback", response_model=FixOut, tags=["fixes"])
def rollback_fix(fix_id: int, db: Session = Depends(get_db)):
    fix = get_or_404(db, Fix, fix_id, "исправление")
    if fix.status != "applied":
        raise HTTPException(status.HTTP_409_CONFLICT, "исправление уже откатено")
    file = get_or_404(db, SourceFile, fix.file_id, "файл")
    file.content = fix.old_content
    fix.status = "rolled_back"
    db.commit()
    FIXES.labels("rolled_back").inc()
    return FixOut(id=fix.id, smell_id=fix.smell_id, status=fix.status, diff=fix.diff)
