from __future__ import annotations
import os
import platform
import json
import signal
import subprocess
import threading
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Literal
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import case, func, or_
from sqlalchemy.orm import Session
from ..database import get_db
from ..models.devops import DevopsActionLog
from ..models.user import Usuario
from ..services.access_control import require_access
from ..utils.time import utc_iso
from ..services.main_workflow import RepositoryError, repository_status, assert_publishable, validate_delivery_files

router = APIRouter(prefix="/devops")
REPO_PATH = Path(__file__).resolve().parents[3]
BRANCH = "main"
REMOTE = "origin"
require_devops_view = require_access("devops", "lector")
require_devops_edit = require_access("devops", "editor")
require_devops_manage = require_access("devops", "gestor")
PROGRESS_LOCK = threading.Lock()
PROGRESS: dict[int, dict] = {}
ACTIVE_PROCESSES: dict[int, subprocess.Popen] = {}
MAX_PROGRESS_LINES = 600

class DevopsActionRequest(BaseModel):
    commit_message: str | None = Field(default=None, max_length=180)


class DevopsPublishRequest(BaseModel):
    target: Literal["both"] = "both"


class CommandFailure(RuntimeError):
    def __init__(self, message: str, output: str = ""):
        super().__init__(message)
        self.output = output


def progress_snapshot(user_id: int) -> dict:
    with PROGRESS_LOCK:
        current = PROGRESS.get(user_id)
        if not current:
            return {
                "action": None,
                "state": "idle",
                "terminal": [],
                "started_at": None,
                "updated_at": None,
                "finished_at": None,
                "cancel_requested": False,
            }
        return {**current, "terminal": list(current["terminal"])}


def begin_progress(user_id: int, action: str, message: str) -> None:
    with PROGRESS_LOCK:
        active = next(
            (item for item in PROGRESS.values() if item["state"] == "running"),
            None,
        )
        if active:
            raise HTTPException(
                status_code=409,
                detail=f"Ya existe una operacion DevOps en curso: {active['action']}.",
            )
        now = datetime.now(timezone.utc).isoformat()
        PROGRESS[user_id] = {
            "action": action,
            "state": "running",
            "terminal": [message],
            "started_at": now,
            "updated_at": now,
            "finished_at": None,
            "cancel_requested": False,
        }


def append_progress(user_id: int, line: str) -> None:
    if not line:
        return
    with PROGRESS_LOCK:
        current = PROGRESS.get(user_id)
        if not current:
            return
        current["terminal"].append(line.rstrip())
        current["terminal"] = current["terminal"][-MAX_PROGRESS_LINES:]
        current["updated_at"] = datetime.now(timezone.utc).isoformat()


def finish_progress(user_id: int, state: str, message: str) -> None:
    append_progress(user_id, message)
    with PROGRESS_LOCK:
        if user_id in PROGRESS:
            PROGRESS[user_id]["state"] = state
            now = datetime.now(timezone.utc).isoformat()
            PROGRESS[user_id]["updated_at"] = now
            PROGRESS[user_id]["finished_at"] = now


def cancellation_requested(user_id: int | None) -> bool:
    if user_id is None:
        return False
    with PROGRESS_LOCK:
        current = PROGRESS.get(user_id)
        return bool(current and current.get("cancel_requested"))


def ensure_not_cancelled(user_id: int | None) -> None:
    if cancellation_requested(user_id):
        raise CommandFailure("Operacion cancelada por el usuario.")


def terminate_process_tree(process: subprocess.Popen) -> None:
    if process.poll() is not None:
        return
    try:
        if platform.system().lower() == "windows":
            result = subprocess.run(
                ["taskkill", "/PID", str(process.pid), "/T", "/F"],
                capture_output=True,
                timeout=10,
                check=False,
            )
            if result.returncode != 0 and process.poll() is None:
                process.kill()
        else:
            os.killpg(process.pid, signal.SIGKILL)
    except (OSError, subprocess.SubprocessError):
        process.kill()


def request_cancellation(user_id: int) -> dict:
    with PROGRESS_LOCK:
        current = PROGRESS.get(user_id)
        if not current or current["state"] != "running":
            raise HTTPException(status_code=409, detail="No hay un proceso DevOps activo.")
        current["cancel_requested"] = True
        current["updated_at"] = datetime.now(timezone.utc).isoformat()
        process = ACTIVE_PROCESSES.get(user_id)
    append_progress(user_id, "Cancelacion solicitada; deteniendo el proceso activo...")
    if process:
        terminate_process_tree(process)
    return progress_snapshot(user_id)


def failed_progress_state(user_id: int) -> str:
    return "cancelled" if cancellation_requested(user_id) else "failed"


def require_devops_user(
    current_user: Usuario = Depends(require_devops_view),
) -> Usuario:
    return current_user


def run_command(
    args: list[str],
    cwd: Path = REPO_PATH,
    timeout: int = 180,
    on_output: Callable[[str], None] | None = None,
    extra_env: dict[str, str] | None = None,
    user_id: int | None = None,
) -> str:
    ensure_not_cancelled(user_id)
    environment = os.environ.copy()
    environment["GIT_TERMINAL_PROMPT"] = "0"
    environment["PYTHONUNBUFFERED"] = "1"
    environment["FORCE_COLOR"] = "0"
    if extra_env:
        environment.update(extra_env)
    display = " ".join(args)
    if on_output:
        on_output(f"$ {display}")

    timed_out = threading.Event()
    try:
        process = subprocess.Popen(
            args,
            cwd=str(cwd),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            env=environment,
            bufsize=0,
            start_new_session=platform.system().lower() != "windows",
            creationflags=(
                subprocess.CREATE_NEW_PROCESS_GROUP
                if platform.system().lower() == "windows"
                else 0
            ),
        )
    except OSError as exc:
        raise CommandFailure(f"No se pudo ejecutar {args[0]}: {exc}") from exc

    if user_id is not None:
        with PROGRESS_LOCK:
            ACTIVE_PROCESSES[user_id] = process
        if cancellation_requested(user_id):
            terminate_process_tree(process)

    def stop_process() -> None:
        timed_out.set()
        terminate_process_tree(process)

    timer = threading.Timer(timeout, stop_process)
    timer.start()
    output_lines: list[str] = []
    try:
        if process.stdout:
            pending = ""
            while True:
                character = process.stdout.read(1)
                if character == "":
                    if pending:
                        output_lines.append(pending)
                        if on_output:
                            on_output(pending)
                    break
                if character in {"\r", "\n"}:
                    if pending:
                        output_lines.append(pending)
                        if on_output:
                            on_output(pending)
                        pending = ""
                else:
                    pending += character
        return_code = process.wait()
    finally:
        timer.cancel()
        if user_id is not None:
            with PROGRESS_LOCK:
                if ACTIVE_PROCESSES.get(user_id) is process:
                    ACTIVE_PROCESSES.pop(user_id, None)

    output = "\n".join(output_lines).strip()
    terminal = f"$ {display}\n{output}".rstrip()
    if timed_out.is_set():
        raise CommandFailure(f"El comando excedió {timeout} segundos", terminal)
    if cancellation_requested(user_id):
        raise CommandFailure("Operacion cancelada por el usuario.", terminal)
    if return_code != 0:
        raise CommandFailure(f"Falló el comando: {display}", terminal)
    return terminal


def git_output(
    *args: str,
    timeout: int = 180,
    on_output: Callable[[str], None] | None = None,
    user_id: int | None = None,
) -> str:
    return run_command(
        ["git", *args], timeout=timeout, on_output=on_output, user_id=user_id
    )


def git_value(*args: str) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=str(REPO_PATH),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=30,
        check=False,
    )
    if result.returncode != 0:
        raise CommandFailure(result.stderr.strip() or "No se pudo consultar Git")
    return result.stdout.rstrip("\r\n")


def save_log(
    db: Session,
    user: Usuario,
    action: str,
    status: str,
    message: str,
    terminal: list[str],
    commit_hash: str | None = None,
) -> None:
    row = DevopsActionLog(
        usuario_id=user.id,
        accion=action,
        estado=status,
        mensaje=message[:500],
        commit_hash=commit_hash,
        salida="\n\n".join(terminal)[-65000:],
    )
    db.add(row)
    db.commit()



def action_error(
    db: Session, user: Usuario, action: str, exc: Exception, terminal: list[str]
) -> HTTPException:
    if isinstance(exc, CommandFailure) and exc.output:
        terminal.append(exc.output)
    message = str(exc)
    save_log(db, user, action, failed_progress_state(user.id), message, terminal)
    return HTTPException(status_code=409, detail={"message": message, "terminal": terminal})


@router.get("/progress")
def get_progress(user: Usuario = Depends(require_devops_user)):
    return progress_snapshot(user.id)


@router.post("/progress/cancel")
def cancel_progress(user: Usuario = Depends(require_devops_edit)):
    return request_cancellation(user.id)


@router.get("/status")
def get_status(
    refresh: bool = Query(default=True),
    user: Usuario = Depends(require_devops_user),
):
    begin_progress(user.id, "status", "Consultando el estado del repositorio...")
    emit = lambda line: append_progress(user.id, line)
    try:
        status, terminal = repository_status(
            root=REPO_PATH, refresh_remote=refresh, on_output=emit
        )
        finish_progress(user.id, "success", "✓ Consulta completada.")
        return {"status": status, "terminal": terminal}
    except (CommandFailure, RepositoryError) as exc:
        finish_progress(user.id, failed_progress_state(user.id), f"✕ {exc}")
        raise HTTPException(status_code=503, detail=str(exc)) from exc


def execute_main_action(action, user, db, message=None):
    begin_progress(user.id, action, f"Iniciando {action} en main...")
    terminal = []
    def emit(line):
        terminal.append(line)
        append_progress(user.id, line)
    def run(args, **kwargs):
        return run_command(args, on_output=emit, user_id=user.id, **kwargs)
    try:
        if action == "publish" and os.getenv("DEVOPS_PUBLISH_ENABLED", "false").lower() != "true":
            raise RepositoryError("Servidor pendiente de configuración. La publicación está desactivada.")
        status, _ = repository_status(root=REPO_PATH, refresh_remote=True, on_output=emit)
        assert_publishable(status, action)
        ensure_not_cancelled(user.id)
        if action == "pull":
            run(["git", "merge", "--ff-only", "origin/main"])
        elif action == "push":
            if status["changes"]:
                if not message or not message.strip():
                    raise RepositoryError("Describe los cambios antes de subirlos.")
                run([sys.executable, "-m", "unittest", "discover", "-s", "tests"], cwd=REPO_PATH / "BackEnd", timeout=300)
                npm = "npm.cmd" if os.name == "nt" else "npm"
                run([npm, "run", "build"], cwd=REPO_PATH / "FrontEnd/frontend-app", timeout=600)
                run(["git", "add", "--all"])
                validate_delivery_files(REPO_PATH)
                run(["git", "commit", "-m", message.strip()])
            validate_delivery_files(REPO_PATH)
            run(["git", "push", "--set-upstream", "origin", "main"])
        elif action == "publish":
            run([sys.executable, str(REPO_PATH / "deployment/publish.py")], timeout=1200)
        result, _ = repository_status(root=REPO_PATH)
        notice = "Operación completada en main."
        save_log(db, user, action, "success", notice, terminal, result["local_commit"])
        finish_progress(user.id, "success", notice)
        return {"message": notice, "status": result, "terminal": terminal}
    except Exception as exc:
        finish_progress(user.id, failed_progress_state(user.id), str(exc))
        raise action_error(db, user, action, exc, terminal) from exc


@router.post("/pull")
def pull(user: Usuario = Depends(require_devops_edit), db: Session = Depends(get_db)):
    return execute_main_action("pull", user, db)


@router.post("/push")
def push(payload: DevopsActionRequest, user: Usuario = Depends(require_devops_manage), db: Session = Depends(get_db)):
    return execute_main_action("push", user, db, payload.commit_message)


@router.post("/publish")
def publish(payload: DevopsPublishRequest, user: Usuario = Depends(require_devops_manage), db: Session = Depends(get_db)):
    return execute_main_action("publish", user, db)


@router.get("/logs")
def get_logs(
    page: int = Query(default=1, ge=1),
    page_size: str = Query(default="10", pattern=r"^(10|25|50|all)$"),
    search: str = Query(default="", max_length=200),
    filter_by: str = Query(default="all", pattern=r"^(all|success|failed|cancelled|publish)$"),
    direction: str = Query(default="desc", pattern=r"^(asc|desc)$"),
    _: Usuario = Depends(require_devops_user),
    db: Session = Depends(get_db),
):
    query = db.query(DevopsActionLog)
    term = search.strip().lower()
    if term:
        pattern = f"%{term}%"
        query = query.filter(or_(
            func.lower(DevopsActionLog.accion).like(pattern),
            func.lower(DevopsActionLog.estado).like(pattern),
            func.lower(DevopsActionLog.mensaje).like(pattern),
            func.lower(DevopsActionLog.salida).like(pattern),
            func.lower(DevopsActionLog.commit_hash).like(pattern),
        ))
    state = func.lower(DevopsActionLog.estado)
    success_condition = or_(*[state.like(f"%{value}%") for value in ("ok", "success", "exitoso", "exitosa")])
    failed_condition = or_(*[state.like(f"%{value}%") for value in ("error", "failed", "fallo", "fallido")])
    cancelled_condition = state.like("%cancel%")
    publish_condition = DevopsActionLog.accion == "publish"
    if filter_by == "success":
        query = query.filter(success_condition)
    elif filter_by == "failed":
        query = query.filter(failed_condition)
    elif filter_by == "cancelled":
        query = query.filter(cancelled_condition)
    elif filter_by == "publish":
        query = query.filter(publish_condition)
    total = query.count()
    order = DevopsActionLog.creado_en.asc() if direction == "asc" else DevopsActionLog.creado_en.desc()
    query = query.order_by(order, DevopsActionLog.id.asc() if direction == "asc" else DevopsActionLog.id.desc())
    if page_size != "all":
        size = int(page_size)
        query = query.offset((page - 1) * size).limit(size)
    rows = query.all()
    def metadata(row: DevopsActionLog) -> dict:
        try:
            value = json.loads(row.salida or "")
            return value if value.get("central_audit") else {}
        except (json.JSONDecodeError, AttributeError):
            return {}

    count_row = db.query(
        func.count(DevopsActionLog.id),
        func.coalesce(func.sum(case((success_condition, 1), else_=0)), 0),
        func.coalesce(func.sum(case((failed_condition, 1), else_=0)), 0),
        func.coalesce(func.sum(case((cancelled_condition, 1), else_=0)), 0),
        func.coalesce(func.sum(case((publish_condition, 1), else_=0)), 0),
    ).one()
    return {
        "items": [
            {
                "id": row.id,
                "usuario_id": row.usuario_id,
                "accion": row.accion,
                "estado": row.estado,
                "mensaje": row.mensaje,
                "commit_hash": row.commit_hash,
                "salida": row.salida,
                "creado_en": utc_iso(row.creado_en),
                "origen": metadata(row).get("origin"),
                "actor": metadata(row).get("actor"),
                "creado_en_cliente": metadata(row).get("created_at"),
            }
            for row in rows
        ],
        "total": total,
        "counts": {
            "all": int(count_row[0]), "success": int(count_row[1]),
            "failed": int(count_row[2]), "cancelled": int(count_row[3]),
            "publish": int(count_row[4]),
        },
    }
