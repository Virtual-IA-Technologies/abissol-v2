from __future__ import annotations

import os
import platform
import json
import logging
import re
import signal
import secrets
import subprocess
import tempfile
import threading
import urllib.error
import urllib.request
import sys
from importlib import metadata as package_metadata
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Literal

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Response
from pydantic import BaseModel, Field
from sqlalchemy import case, func, or_, text
from sqlalchemy.orm import Session

from ..database import get_db
from ..models.devops import DevopsActionLog
from ..models.user import Usuario
from ..services.access_control import require_access
from ..utils.time import utc_iso


router = APIRouter(prefix="/devops")
logger = logging.getLogger(__name__)

REPO_PATH = Path(
    os.getenv("DEVOPS_REPO_PATH", str(Path(__file__).resolve().parents[3]))
).resolve()
BRANCH = os.getenv("DEVOPS_BRANCH", "main")
PUBLISH_BRANCH = os.getenv("DEVOPS_PUBLISH_BRANCH", "production")
REMOTE = os.getenv("DEVOPS_REMOTE", "origin")
AUDIT_URL = os.getenv("DEVOPS_AUDIT_URL", "").strip()
AUDIT_TOKEN = os.getenv("DEVOPS_AUDIT_TOKEN", "").strip()
AUDIT_RECEIVER = os.getenv("DEVOPS_AUDIT_RECEIVER", "false").lower() == "true"
WORKSTATION_NAME = os.getenv("DEVOPS_WORKSTATION_NAME", platform.node()).strip() or "equipo-local"
DEPLOY_TRIGGER_FILE = os.getenv("DEVOPS_DEPLOY_TRIGGER_FILE", "").strip()
PUBLISH_MODE = os.getenv("DEVOPS_PUBLISH_MODE", "branch").strip().lower()
GITHUB_REPOSITORY = os.getenv("DEVOPS_GITHUB_REPOSITORY", "virtualizate-pe/abissol-v2").strip()
GITHUB_TOKEN = os.getenv("DEVOPS_GITHUB_TOKEN", "").strip()
DEVELOPER_SLUG = os.getenv("DEVOPS_DEVELOPER_SLUG", "").strip().lower()
PERSONAL_BRANCH = f"feature/{DEVELOPER_SLUG}" if DEVELOPER_SLUG else None
require_devops_view = require_access("devops", "lector")
require_devops_edit = require_access("devops", "editor")
require_devops_manage = require_access("devops", "gestor")

PROGRESS_LOCK = threading.Lock()
PROGRESS: dict[int, dict] = {}
ACTIVE_PROCESSES: dict[int, subprocess.Popen] = {}
MAX_PROGRESS_LINES = 600
ACTIVE_INTEGRATION_STATES = {"queued", "in_progress", "waiting", "requested", "pending"}


class DevopsActionRequest(BaseModel):
    commit_message: str | None = Field(default=None, max_length=180)


class DevopsBranchRequest(BaseModel):
    branch: str = Field(min_length=1, max_length=120)
    create: bool = False


class DevopsPublishRequest(BaseModel):
    target: Literal["backend", "frontend", "both"] = "both"


class DevopsAuditEvent(BaseModel):
    user_id: int | None = None
    actor: str = Field(max_length=200)
    origin: str = Field(max_length=120)
    action: str = Field(max_length=30)
    status: str = Field(max_length=20)
    message: str = Field(max_length=500)
    commit_hash: str | None = Field(default=None, max_length=40)
    created_at: str


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


def reconcile_migration_heads(
    on_output: Callable[[str], None] | None = None,
    user_id: int | None = None,
) -> tuple[str, bool]:
    output = run_command(
        [sys.executable, "-B", "scripts/reconcile_migration_heads.py"],
        cwd=REPO_PATH / "BackEnd",
        timeout=60,
        on_output=on_output,
        user_id=user_id,
    )
    return output, "MIGRATION_MERGE_CREATED=" in output


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


def git_value_with_env(*args: str, extra_env: dict[str, str]) -> str:
    environment = os.environ.copy()
    environment["GIT_TERMINAL_PROMPT"] = "0"
    environment.update(extra_env)
    result = subprocess.run(
        ["git", *args],
        cwd=str(REPO_PATH),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=environment,
        timeout=60,
        check=False,
    )
    if result.returncode != 0:
        raise CommandFailure(result.stderr.strip() or "No se pudo preparar el compilado")
    return result.stdout.rstrip("\r\n")


def build_frontend(on_output: Callable[[str], None], user_id: int | None = None) -> str:
    frontend = REPO_PATH / "FrontEnd" / "frontend-app"
    npm = "npm.cmd" if platform.system().lower() == "windows" else "npm"
    api_url = os.getenv("DEVOPS_BUILD_API_URL", "http://localhost:8015")
    return run_command(
        [npm, "run", "build"],
        cwd=frontend,
        timeout=600,
        on_output=on_output,
        user_id=user_id,
        extra_env={
            "VITE_API_URL": api_url,
        },
    )


def release_commit(
    base_commit: str,
    target: Literal["backend", "frontend", "both"],
    on_output: Callable[[str], None],
    user_id: int | None = None,
) -> str:
    dist = REPO_PATH / "FrontEnd" / "frontend-app" / "dist"
    if target in {"frontend", "both"} and not (dist / "index.html").is_file():
        raise CommandFailure("La compilación no generó FrontEnd/frontend-app/dist/index.html")
    with tempfile.TemporaryDirectory(prefix="abissol-v2-devops-") as temporary:
        index_env = {"GIT_INDEX_FILE": str(Path(temporary) / "index")}
        run_command(
            ["git", "read-tree", base_commit],
            on_output=on_output,
            extra_env=index_env,
            user_id=user_id,
        )
        marker = Path(temporary) / "deploy-target"
        marker.write_text(f"{target}\n", encoding="utf-8")
        marker_blob = git_value_with_env("hash-object", "-w", str(marker), extra_env=index_env)
        run_command(
            ["git", "update-index", "--add", "--cacheinfo", "100644", marker_blob, ".deploy-target"],
            on_output=on_output,
            extra_env=index_env,
            user_id=user_id,
        )
        if target in {"frontend", "both"}:
            run_command(
                ["git", "add", "-f", "--", "FrontEnd/frontend-app/dist"],
                on_output=on_output,
                extra_env=index_env,
                user_id=user_id,
            )
        tree = git_value_with_env("write-tree", extra_env=index_env)
    commit = git_value(
        "commit-tree", tree, "-p", base_commit, "-m",
        f"release: {target} for {base_commit[:8]}",
    )
    on_output(f"Release {target} preparada para GitHub: {commit[:8]}")
    return commit


def can_auto_sync_integrated_branch(
    *,
    refresh_remote: bool,
    verified: bool,
    is_personal_branch: bool,
    changes: list[str],
    main_contains_head: bool,
    base_ahead: int,
    base_behind: int,
) -> bool:
    return bool(
        refresh_remote
        and verified
        and is_personal_branch
        and not changes
        and main_contains_head
        and base_ahead == 0
        and base_behind > 0
    )


def personal_upload_ahead(
    *,
    branch_ahead: int,
    base_ahead: int,
    main_contains_head: bool,
) -> int:
    """Cuenta solo commits locales que no estén ya en main ni en la rama remota."""
    if main_contains_head:
        return 0
    return min(max(branch_ahead, 0), max(base_ahead, 0))


def repository_status(
    refresh_remote: bool = True,
    on_output: Callable[[str], None] | None = None,
    user_id: int | None = None,
) -> tuple[dict, list[str]]:
    ensure_not_cancelled(user_id)
    terminal: list[str] = []
    if not (REPO_PATH / ".git").exists():
        raise CommandFailure(f"No existe un repositorio Git en {REPO_PATH}")

    main_guard_path = REPO_PATH / ".githooks" / "pre-push"
    policy_entries = [
        ("pull.ff", "only"),
        ("fetch.prune", "true"),
        ("push.default", "current"),
        ("rebase.autoStash", "false"),
        ("merge.autoStash", "false"),
    ]
    if main_guard_path.is_file():
        policy_entries.append(("core.hooksPath", ".githooks"))
    for key, value in policy_entries:
        try:
            current_value = git_value("config", "--local", "--get", key)
        except CommandFailure:
            current_value = None
        if not current_value or current_value.lower() != value.lower():
            git_value("config", "--local", key, value)
    try:
        configured_hooks_path = git_value("config", "--local", "--get", "core.hooksPath")
    except CommandFailure:
        configured_hooks_path = None
    local_main_guard = main_guard_path.is_file() and configured_hooks_path == ".githooks"

    branch = git_value("branch", "--show-current")
    if not branch:
        raise CommandFailure("El repositorio esta en detached HEAD. Cambia a una rama antes de usar DevOps.")

    fetch_error = None
    if refresh_remote:
        try:
            terminal.append(
                git_output(
                    "fetch", REMOTE, "--prune", timeout=180,
                    on_output=on_output, user_id=user_id,
                )
            )
        except CommandFailure as exc:
            fetch_error = str(exc)
            terminal.append(exc.output or fetch_error)

    ensure_not_cancelled(user_id)

    if on_output:
        on_output("Revisando cambios y comparando commits...")
    changes_raw = git_value("status", "--porcelain")
    changes = [line for line in changes_raw.splitlines() if line.strip()]
    local_commit = git_value("rev-parse", "HEAD")

    upstream = None
    try:
        upstream = git_value(
            "rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{upstream}"
        )
    except CommandFailure:
        pass

    branch_remote_ref = f"{REMOTE}/{branch}"
    try:
        remote_commit = git_value("rev-parse", branch_remote_ref)
        counts = git_value(
            "rev-list", "--left-right", "--count", f"HEAD...{branch_remote_ref}"
        ).split()
        ahead, behind = int(counts[0]), int(counts[1])
    except (CommandFailure, ValueError, IndexError):
        remote_commit = None
        behind = 0
        try:
            ahead = int(git_value("rev-list", "--count", f"{REMOTE}/{BRANCH}..HEAD"))
        except (CommandFailure, ValueError):
            ahead = 0

    try:
        base_remote_commit = git_value("rev-parse", f"{REMOTE}/{BRANCH}")
        base_counts = git_value(
            "rev-list", "--left-right", "--count", f"HEAD...{REMOTE}/{BRANCH}"
        ).split()
        base_ahead, base_behind = int(base_counts[0]), int(base_counts[1])
    except (CommandFailure, ValueError, IndexError):
        base_remote_commit = None
        base_ahead, base_behind = 0, 0

    main_contains_head = False
    if base_remote_commit is not None:
        result = subprocess.run(
            ["git", "merge-base", "--is-ancestor", "HEAD", f"{REMOTE}/{BRANCH}"],
            cwd=str(REPO_PATH),
            capture_output=True,
            timeout=30,
            check=False,
        )
        main_contains_head = result.returncode == 0

    remote_changes = []
    if remote_commit and behind:
        parts = git_value("diff", "--name-status", "--no-renames", "-z", f"HEAD...{branch_remote_ref}").split("\0")
        remote_changes = [f"{parts[i]}  {parts[i + 1]}" for i in range(0, len(parts) - 1, 2)]
    ahead_changes = []
    ahead_commits = []
    if remote_commit and ahead:
        parts = git_value(
            "diff", "--name-status", "--no-renames", "-z",
            f"{branch_remote_ref}..HEAD"
        ).split("\0")
        ahead_changes = [
            f"{parts[i]}  {parts[i + 1]}" for i in range(0, len(parts) - 1, 2)
        ]
        ahead_commits = [
            line for line in git_value(
                "log", "--format=%h  %an  %s",
                f"{branch_remote_ref}..HEAD"
            ).splitlines() if line.strip()
        ]
    blocked = bool(git_value("diff", "--name-only", "--diff-filter=U")) or any(
        (REPO_PATH / ".git" / name).exists() for name in ("MERGE_HEAD", "rebase-merge", "rebase-apply")
    )
    integration_activity = github_integration_activity() if refresh_remote else {
        "busy": False, "branch": None, "run_number": None, "url": None,
        "status": None, "error": None,
    }
    remote_integration_busy = bool(integration_activity["busy"])
    is_protected_branch = branch == BRANCH
    is_personal_branch = PERSONAL_BRANCH is not None and branch == PERSONAL_BRANCH
    developer_configured = bool(
        DEVELOPER_SLUG and re.fullmatch(r"[a-z0-9][a-z0-9._-]*", DEVELOPER_SLUG)
    )
    upload_ahead = ahead
    upload_changes = ahead_changes
    if is_personal_branch:
        upload_ahead = personal_upload_ahead(
            branch_ahead=ahead,
            base_ahead=base_ahead,
            main_contains_head=main_contains_head,
        )
        upload_changes = []
        if upload_ahead and base_remote_commit:
            parts = git_value(
                "diff", "--name-status", "--no-renames", "-z",
                f"{REMOTE}/{BRANCH}..HEAD",
            ).split("\0")
            upload_changes = [
                f"{parts[i]}  {parts[i + 1]}"
                for i in range(0, len(parts) - 1, 2)
            ]
    verified = (
        not fetch_error and base_remote_commit is not None and not blocked
        and local_main_guard and developer_configured
    )
    auto_sync_ready = can_auto_sync_integrated_branch(
        refresh_remote=refresh_remote,
        verified=verified,
        is_personal_branch=is_personal_branch,
        changes=changes,
        main_contains_head=main_contains_head,
        base_ahead=base_ahead,
        base_behind=base_behind,
    )
    if auto_sync_ready:
        if on_output:
            on_output(
                "GitHub termino la integracion; sincronizando automaticamente la rama local..."
            )
        terminal.append(
            git_output(
                "merge",
                "--ff-only",
                f"{REMOTE}/{BRANCH}",
                timeout=300,
                on_output=on_output,
                user_id=user_id,
            )
        )
        synchronized, synchronized_terminal = repository_status(
            refresh_remote=False,
            user_id=user_id,
        )
        terminal.extend(synchronized_terminal)
        synchronized["auto_synced_after_integration"] = True
        return synchronized, terminal

    matches_integrated_main = bool(
        not changes
        and base_ahead == 0
        and base_behind == 0
        and local_commit == base_remote_commit
    )
    if blocked:
        state = "diverged"
        message = "Resuelve los conflictos o la integracion pendiente antes de continuar."
    elif fetch_error:
        state = "offline"
        message = "No se pudo consultar GitHub. Subir y publicar están bloqueados."
    elif not local_main_guard:
        state = "diverged"
        message = "Falta la proteccion local de main. Reinstala o actualiza DevOps antes de continuar."
    elif not developer_configured:
        state = "diverged"
        message = "Falta configurar DEVOPS_DEVELOPER_SLUG para asignar la rama personal de este equipo."
    elif not is_protected_branch and not is_personal_branch:
        state = "diverged"
        message = f"Cambia a la rama personal asignada {PERSONAL_BRANCH} antes de continuar."
    elif remote_integration_busy:
        state = "dirty" if changes else "behind"
        occupied_branch = integration_activity["branch"] or "otra rama"
        message = (
            f"GitHub está integrando {occupied_branch}. Subir se habilitará "
            "automáticamente cuando termine el turno."
        )
    elif remote_commit and ahead and behind:
        state = "diverged"
        message = f"La rama {branch} y GitHub tienen cambios distintos; requiere integración manual."
    elif behind and changes:
        state = "diverged"
        message = (
            f"GitHub tiene {behind} actualizaciÃ³n(es) en {branch} y hay {len(changes)} archivo(s) "
            "local(es). La descarga estÃ¡ bloqueada para no mezclar trabajos; guarda "
            "los cambios en una rama y usa un Pull Request."
        )
    elif behind:
        state = "behind"
        message = f"GitHub tiene {behind} actualización(es) pendiente(s) para {branch}."
    elif changes:
        state = "dirty"
        if is_protected_branch:
            message = (
                f"Hay {len(changes)} archivo(s) local(es) en {BRANCH}. "
                "Crea una rama de trabajo antes de subirlos."
            )
        else:
            message = f"Hay {len(changes)} archivo(s) local(es) pendiente(s) en {branch}."
    elif matches_integrated_main:
        state = "synced"
        message = f"La rama {branch} coincide con {REMOTE}/{BRANCH} integrado."
    elif ahead:
        state = "ahead"
        message = f"Hay {ahead} commit(s) de {branch} pendiente(s) de subir."
    elif not remote_commit and not is_protected_branch:
        state = "ahead"
        message = f"La rama {branch} todavia no existe en GitHub. Puedes subirla para respaldarla."
    else:
        state = "synced"
        message = f"La rama {branch} esta sincronizada con GitHub."

    remote_url = git_value("remote", "get-url", REMOTE)
    web_url = remote_url[:-4] if remote_url.endswith(".git") else remote_url
    if web_url.startswith("git@github.com:"):
        web_url = "https://github.com/" + web_url.removeprefix("git@github.com:")
    pull_request_url = None
    if not is_protected_branch and web_url.startswith("https://github.com/"):
        pull_request_url = f"{web_url}/compare/{BRANCH}...{branch}?expand=1"

    local_branches = sorted(
        item for item in git_value(
            "for-each-ref", "--format=%(refname:short)", "refs/heads"
        ).splitlines() if item.strip()
    )
    remote_branches = sorted(
        item.removeprefix(f"{REMOTE}/")
        for item in git_value(
            "for-each-ref", "--format=%(refname:short)", f"refs/remotes/{REMOTE}"
        ).splitlines()
        if item.strip() and item not in {REMOTE, f"{REMOTE}/HEAD"}
    )

    return {
        "repository": str(REPO_PATH),
        "remote": REMOTE,
        "remote_url": remote_url,
        "branch": branch,
        "protected_branch": BRANCH,
        "is_protected_branch": is_protected_branch,
        "developer_slug": DEVELOPER_SLUG or None,
        "developer_configured": developer_configured,
        "personal_branch": PERSONAL_BRANCH,
        "is_personal_branch": is_personal_branch,
        "upstream": upstream,
        "branch_remote_ref": branch_remote_ref,
        "remote_branch_exists": remote_commit is not None,
        "publish_branch": PUBLISH_BRANCH,
        "local_commit": local_commit,
        "remote_commit": remote_commit,
        "base_remote_commit": base_remote_commit,
        "ahead": ahead,
        "behind": behind,
        "upload_ahead": upload_ahead,
        "base_ahead": base_ahead,
        "base_behind": base_behind,
        "main_contains_head": main_contains_head,
        "changes": changes,
        "remote_changes": remote_changes,
        "ahead_changes": ahead_changes,
        "upload_changes": upload_changes,
        "ahead_commits": ahead_commits,
        "integration_pending": blocked,
        "integration_busy": remote_integration_busy,
        "integration_busy_branch": integration_activity["branch"],
        "integration_run_number": integration_activity["run_number"],
        "integration_run_url": integration_activity["url"],
        "integration_lock_error": integration_activity["error"],
        "state": state,
        "message": message,
        "fetch_error": fetch_error,
        "pull_request_url": pull_request_url,
        "local_main_guard": local_main_guard,
        "local_branches": local_branches,
        "remote_branches": remote_branches,
        "can_switch_branch": verified and not changes,
        "can_create_branch": verified,
        "can_pull": (
            verified and is_personal_branch and not remote_integration_busy and not changes
            and (base_behind > 0 or (remote_commit is not None and behind > 0))
        ),
        "can_push": (
            verified and is_personal_branch and not remote_integration_busy
            and not matches_integrated_main
            and (bool(changes) or ahead > 0 or remote_commit is None)
        ),
        "can_publish": (
            verified and not remote_integration_busy
            and (is_protected_branch or is_personal_branch)
            and matches_integrated_main
        ),
    }, terminal


def validate_branch_name(branch: str, *, allow_protected: bool = False) -> str:
    normalized = branch.strip()
    if normalized == PUBLISH_BRANCH or (normalized == BRANCH and not allow_protected):
        raise CommandFailure(
            f"{normalized} es una rama reservada. Usa feature/<tema>, fix/<tema> o chore/<tema>."
        )
    try:
        git_value("check-ref-format", "--branch", normalized)
    except CommandFailure as exc:
        raise CommandFailure(
            "Nombre de rama invalido. Usa por ejemplo feature/mi-cambio, sin espacios."
        ) from exc
    return normalized


def require_personal_branch(branch: str) -> None:
    if not PERSONAL_BRANCH:
        raise CommandFailure(
            "Configura DEVOPS_DEVELOPER_SLUG en BackEnd/.env antes de usar DevOps."
        )
    if branch != PERSONAL_BRANCH:
        raise CommandFailure(
            f"Este equipo solo puede trabajar desde su rama personal {PERSONAL_BRANCH}."
        )


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
    send_central_log(user, action, status, message, commit_hash)


def user_display_name(user: Usuario) -> str:
    name = " ".join(
        str(value).strip()
        for value in (getattr(user, "nombre", ""), getattr(user, "apellido", ""))
        if value
    )
    return name or str(getattr(user, "email", "")) or f"Usuario {user.id}"


def send_central_log(
    user: Usuario,
    action: str,
    status: str,
    message: str,
    commit_hash: str | None,
) -> None:
    if not AUDIT_URL or not AUDIT_TOKEN or AUDIT_RECEIVER:
        return
    payload = json.dumps(
        {
            "user_id": user.id,
            "actor": user_display_name(user),
            "origin": WORKSTATION_NAME,
            "action": action,
            "status": status,
            "message": message[:500],
            "commit_hash": commit_hash,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
    ).encode("utf-8")
    request = urllib.request.Request(
        AUDIT_URL,
        data=payload,
        method="POST",
        headers={
            "Content-Type": "application/json",
            "X-DevOps-Audit-Key": AUDIT_TOKEN,
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=8):
            pass
    except (OSError, urllib.error.URLError) as exc:
        logger.warning("No se pudo enviar el historial DevOps central: %s", exc)


def github_tokens() -> list[str]:
    tokens = [GITHUB_TOKEN] if GITHUB_TOKEN else []
    if os.getenv("APP_ENV", "development").strip().lower() != "production":
        try:
            credential_command = (
                ["git", "credential-manager", "get"]
                if os.name == "nt"
                else ["git", "credential", "fill"]
            )
            credential = subprocess.run(
                credential_command,
                cwd=str(REPO_PATH),
                input="protocol=https\nhost=github.com\n\n",
                text=True,
                capture_output=True,
                timeout=30,
                check=False,
            )
            if credential.returncode == 0:
                values = dict(
                    line.split("=", 1)
                    for line in credential.stdout.splitlines()
                    if "=" in line
                )
                fallback = values.get("password", "").strip()
                if fallback and fallback not in tokens:
                    tokens.append(fallback)
        except (OSError, subprocess.SubprocessError):
            pass
    return tokens


def github_integration_activity() -> dict:
    """Consulta el turno remoto sin exponer ni persistir credenciales."""
    tokens = github_tokens()
    if not tokens:
        return {"busy": False, "branch": None, "run_number": None, "url": None,
                "status": None, "error": "GitHub no tiene una credencial disponible."}
    url = (
        f"https://api.github.com/repos/{GITHUB_REPOSITORY}/actions/workflows/"
        "integrate-personal.yml/runs?per_page=20"
    )
    last_error: str | None = None
    for token in tokens:
        request = urllib.request.Request(
            url,
            headers={
                "Accept": "application/vnd.github+json",
                "Authorization": f"Bearer {token}",
                "X-GitHub-Api-Version": "2022-11-28",
                "User-Agent": "ABISSOL-V4-DevOps",
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=12) as response:
                payload = json.load(response)
            active = next(
                (run for run in payload.get("workflow_runs", [])
                 if run.get("status") in ACTIVE_INTEGRATION_STATES),
                None,
            )
            if not active:
                return {"busy": False, "branch": None, "run_number": None,
                        "url": None, "status": None, "error": None}
            return {
                "busy": True,
                "branch": active.get("head_branch"),
                "run_number": active.get("run_number"),
                "url": active.get("html_url"),
                "status": active.get("status"),
                "error": None,
            }
        except urllib.error.HTTPError as exc:
            last_error = f"GitHub respondió {exc.code} al consultar el turno."
            if exc.code not in {401, 403, 404}:
                break
        except (urllib.error.URLError, TimeoutError, ValueError) as exc:
            last_error = f"No se pudo consultar el turno de GitHub: {exc}"
            break
    return {"busy": False, "branch": None, "run_number": None, "url": None,
            "status": None, "error": last_error}


def dispatch_release_workflow(target: str) -> str:
    tokens = github_tokens()
    if not tokens:
        raise CommandFailure(
            "Falta una credencial GitHub autorizada para solicitar el workflow protegido."
        )
    url = f"https://api.github.com/repos/{GITHUB_REPOSITORY}/actions/workflows/release.yml/dispatches"
    body = json.dumps({
        "ref": BRANCH,
        "inputs": {"target": target},
    }).encode("utf-8")
    last_http_error: urllib.error.HTTPError | None = None
    for token in tokens:
        request = urllib.request.Request(
            url,
            data=body,
            method="POST",
            headers={
                "Accept": "application/vnd.github+json",
                "Authorization": f"Bearer {token}",
                "X-GitHub-Api-Version": "2022-11-28",
                "User-Agent": "ABISSOL-V4-DevOps",
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=20) as response:
                if response.status != 204:
                    raise CommandFailure(f"GitHub respondió con estado {response.status}")
            return f"Workflow release.yml solicitado para producción; objetivo: {target}."
        except urllib.error.HTTPError as exc:
            last_http_error = exc
            if exc.code not in {401, 403, 404}:
                break
        except urllib.error.URLError as exc:
            raise CommandFailure("No se pudo conectar con GitHub Actions.") from exc
    code = last_http_error.code if last_http_error else "desconocido"
    raise CommandFailure(f"GitHub rechazó la solicitud del workflow ({code}).") from last_http_error


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


@router.get("/maintenance")
def get_maintenance_status(
    _: Usuario = Depends(require_devops_user),
    db: Session = Depends(get_db),
):
    packages = {}
    for distribution in ("fastapi", "uvicorn", "SQLAlchemy", "PyMySQL", "alembic", "pydantic"):
        try:
            packages[distribution] = package_metadata.version(distribution)
        except package_metadata.PackageNotFoundError:
            packages[distribution] = None
    try:
        migration = db.execute(text("SELECT version_num FROM alembic_version LIMIT 1")).scalar()
    except Exception:
        migration = None
    return {
        "runtime": {"python": platform.python_version(), "executable": sys.executable},
        "packages": packages,
        "database_migration": migration,
        "schema_managed": migration is not None,
        "update_source": "Dependabot y GitHub Actions",
        "direct_install_allowed": False,
        "publish_mode": PUBLISH_MODE,
        "workflow_configured": PUBLISH_MODE == "workflow" and bool(GITHUB_TOKEN),
    }


@router.get("/status")
def get_status(
    refresh: bool = Query(default=True),
    user: Usuario = Depends(require_devops_user),
):
    begin_progress(user.id, "status", "Consultando el estado del repositorio...")
    emit = lambda line: append_progress(user.id, line)
    try:
        status, terminal = repository_status(
            refresh_remote=refresh, on_output=emit, user_id=user.id
        )
        finish_progress(user.id, "success", "✓ Consulta completada.")
        return {"status": status, "terminal": terminal}
    except CommandFailure as exc:
        finish_progress(user.id, failed_progress_state(user.id), f"✕ {exc}")
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.get("/integration-activity")
def get_integration_activity(_: Usuario = Depends(require_devops_user)):
    """Sondeo liviano del turno remoto, sin ejecutar fetch ni inspeccionar el árbol."""
    return github_integration_activity()


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
    publish_condition = func.lower(DevopsActionLog.accion).like("%public%")
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


@router.post("/audit", status_code=204, include_in_schema=False)
def receive_audit_event(
    payload: DevopsAuditEvent,
    response: Response,
    x_devops_audit_key: str | None = Header(default=None),
    db: Session = Depends(get_db),
):
    if not AUDIT_RECEIVER or not AUDIT_TOKEN:
        raise HTTPException(status_code=404, detail="Not found")
    if not x_devops_audit_key or not secrets.compare_digest(
        x_devops_audit_key, AUDIT_TOKEN
    ):
        raise HTTPException(status_code=403, detail="Invalid audit key")

    linked_user_id = None
    if payload.user_id is not None:
        linked_user = db.query(Usuario.id).filter(Usuario.id == payload.user_id).first()
        linked_user_id = payload.user_id if linked_user else None

    db.add(
        DevopsActionLog(
            usuario_id=linked_user_id,
            accion=payload.action,
            estado=payload.status,
            mensaje=payload.message,
            commit_hash=payload.commit_hash,
            salida=json.dumps(
                {
                    "central_audit": True,
                    "origin": payload.origin,
                    "actor": payload.actor,
                    "created_at": payload.created_at,
                },
                ensure_ascii=False,
            ),
        )
    )
    db.commit()
    if (
        payload.action == "publish"
        and payload.status == "success"
        and DEPLOY_TRIGGER_FILE
    ):
        try:
            Path(DEPLOY_TRIGGER_FILE).touch()
        except OSError as exc:
            logger.error("No se pudo activar el despliegue inmediato: %s", exc)
    response.status_code = 204


@router.post("/branch")
def change_branch(
    payload: DevopsBranchRequest,
    user: Usuario = Depends(require_devops_edit),
    db: Session = Depends(get_db),
):
    terminal: list[str] = []
    action_label = "crear rama" if payload.create else "cambiar rama"
    begin_progress(user.id, "branch", f"Preparando {action_label}...")
    emit = lambda line: append_progress(user.id, line)
    live_git = lambda *args, timeout=180: git_output(
        *args, timeout=timeout, on_output=emit, user_id=user.id
    )
    try:
        status, status_terminal = repository_status(
            refresh_remote=True, on_output=emit, user_id=user.id
        )
        terminal.extend(status_terminal)
        if status["fetch_error"] or status["integration_pending"]:
            raise CommandFailure("No se puede cambiar de rama sin verificar GitHub o con una integracion pendiente.")

        branch = validate_branch_name(payload.branch, allow_protected=not payload.create)
        if branch != BRANCH:
            require_personal_branch(branch)
        local_branches = set(status["local_branches"])
        remote_branches = set(status["remote_branches"])
        if payload.create:
            if branch in local_branches or branch in remote_branches:
                raise CommandFailure(
                    f"La rama {branch} ya existe. Seleccionala en Cambiar a una rama existente."
                )
            terminal.append(live_git("switch", "-c", branch))
            message = f"Rama local {branch} creada. Sus cambios permanecen intactos y ya puede subirla."
        else:
            if status["changes"]:
                raise CommandFailure(
                    "Cambio de rama bloqueado: primero confirma y sube los archivos de la rama activa."
                )
            if branch == status["branch"]:
                raise CommandFailure(f"La rama {branch} ya esta activa.")
            if branch in local_branches:
                terminal.append(live_git("switch", branch))
            elif branch in remote_branches:
                terminal.append(
                    live_git("switch", "--track", "-c", branch, f"{REMOTE}/{branch}")
                )
            else:
                raise CommandFailure(f"La rama {branch} no existe localmente ni en GitHub.")
            message = f"Rama activa cambiada a {branch}."

        updated, _ = repository_status(refresh_remote=False, user_id=user.id)
        ensure_not_cancelled(user.id)
        save_log(db, user, "branch", "success", message, terminal, updated["local_commit"])
        finish_progress(user.id, "success", f"✓ {message}")
        return {"message": message, "status": updated, "terminal": terminal}
    except Exception as exc:
        finish_progress(user.id, failed_progress_state(user.id), f"✕ {exc}")
        raise action_error(db, user, "branch", exc, terminal) from exc


@router.post("/pull")
def pull_updates(
    user: Usuario = Depends(require_devops_edit),
    db: Session = Depends(get_db),
):
    terminal: list[str] = []
    begin_progress(user.id, "pull", "Preparando la descarga desde GitHub...")
    emit = lambda line: append_progress(user.id, line)
    live_git = lambda *args, timeout=180: git_output(
        *args, timeout=timeout, on_output=emit, user_id=user.id
    )
    try:
        status, status_terminal = repository_status(
            refresh_remote=True, on_output=emit, user_id=user.id
        )
        terminal.extend(status_terminal)
        if status["fetch_error"] or status["integration_pending"]:
            raise CommandFailure("Verifica GitHub y resuelve cualquier integracion pendiente antes de bajar.")
        require_personal_branch(status["branch"])
        if status["changes"]:
            raise CommandFailure(
                "Descarga bloqueada: primero usa Subir para guardar los cambios en un commit local. "
                "DevOps no usa stash ni sobrescribe archivos."
            )
        merged_sources: list[str] = []
        if status["remote_branch_exists"] and status["behind"]:
            terminal.append(live_git("merge", "--no-edit", status["branch_remote_ref"], timeout=300))
            merged_sources.append(status["branch_remote_ref"])
        current_status, _ = repository_status(refresh_remote=False, user_id=user.id)
        if current_status["base_behind"]:
            terminal.append(live_git("merge", "--no-edit", f"{REMOTE}/{BRANCH}", timeout=300))
            merged_sources.append(f"{REMOTE}/{BRANCH}")
        if merged_sources:
            message = (
                "Rama personal sincronizada con " + " y ".join(merged_sources)
                + ". Revisa y prueba antes de subir."
            )
        else:
            message = "La rama personal ya contenia toda la informacion compartida."
            terminal.append("Sin cambios remotos pendientes.")
        updated, _ = repository_status(refresh_remote=False, user_id=user.id)
        ensure_not_cancelled(user.id)
        save_log(db, user, "pull", "success", message, terminal, updated["local_commit"])
        finish_progress(user.id, "success", f"✓ {message}")
        return {"message": message, "status": updated, "terminal": terminal}
    except Exception as exc:
        finish_progress(user.id, failed_progress_state(user.id), f"✕ {exc}")
        raise action_error(db, user, "pull", exc, terminal) from exc


@router.post("/push")
def push_changes(
    payload: DevopsActionRequest,
    user: Usuario = Depends(require_devops_edit),
    db: Session = Depends(get_db),
):
    terminal: list[str] = []
    begin_progress(user.id, "push", "Preparando los cambios para GitHub...")
    emit = lambda line: append_progress(user.id, line)
    live_git = lambda *args, timeout=180: git_output(
        *args, timeout=timeout, on_output=emit, user_id=user.id
    )
    try:
        status, status_terminal = repository_status(
            refresh_remote=True, on_output=emit, user_id=user.id
        )
        terminal.extend(status_terminal)
        if status["is_protected_branch"]:
            raise CommandFailure(
                f"La rama {status['protected_branch']} esta protegida. "
                "Crea una rama feature/* o fix/* y usa un Pull Request."
            )
        require_personal_branch(status["branch"])
        if status.get("integration_busy"):
            occupied_branch = status.get("integration_busy_branch") or "otra rama"
            raise CommandFailure(
                f"GitHub está integrando {occupied_branch}. Espera a que termine el turno; "
                "no necesitas bajar sus cambios antes de subir."
            )
        if status["integration_pending"] or status["fetch_error"]:
            raise CommandFailure("No se puede subir: resuelve la integracion pendiente o la conexion con GitHub.")
        if not status["can_push"] and not status["behind"]:
            raise CommandFailure("No se puede subir: verifica GitHub, los cambios locales y cualquier integracion pendiente.")
        if status["changes"]:
            message = (payload.commit_message or "chore: update ABISSOL platform").strip()
            terminal.append(live_git("add", "-A"))
            terminal.append(live_git("commit", "-m", message, timeout=180))
            status, _ = repository_status(refresh_remote=False, user_id=user.id)

        synchronized_sources: list[str] = []
        if status["remote_branch_exists"] and status["behind"]:
            terminal.append(
                live_git("merge", "--no-edit", status["branch_remote_ref"], timeout=300)
            )
            synchronized_sources.append(status["branch_remote_ref"])
            status, _ = repository_status(refresh_remote=False, user_id=user.id)
        if synchronized_sources:
            terminal.append(
                "Sincronizacion automatica completada con "
                + " y ".join(synchronized_sources)
                + "."
            )

        migration_output, migration_merge_created = reconcile_migration_heads(
            emit, user.id
        )
        terminal.append(migration_output)
        if migration_merge_created:
            terminal.append(
                live_git("add", "--", "BackEnd/migrations/versions")
            )
            terminal.append(
                live_git(
                    "commit",
                    "-m",
                    "chore: reconcile concurrent Alembic migrations",
                    timeout=180,
                )
            )
            status, _ = repository_status(refresh_remote=False, user_id=user.id)
            terminal.append(
                "Cabezas Alembic concurrentes unidas sin modificar las migraciones originales."
            )
        if not status["ahead"] and status["remote_branch_exists"]:
            raise CommandFailure("No hay cambios locales nuevos para subir.")

        push_ref = f"HEAD:refs/heads/{status['branch']}"
        if status["upstream"] == status["branch_remote_ref"]:
            terminal.append(live_git("push", REMOTE, push_ref, timeout=300))
        else:
            terminal.append(live_git("push", "--set-upstream", REMOTE, push_ref, timeout=300))
        updated, _ = repository_status(
            refresh_remote=True, on_output=emit, user_id=user.id
        )
        message = (
            f"Rama {status['branch']} entregada a GitHub. El turno remoto incorporará el "
            f"{BRANCH} más reciente sin mezclarlo en esta carpeta; después de las pruebas, "
            "DevOps sincronizará esta copia y habilitará Publicar."
        )
        ensure_not_cancelled(user.id)
        save_log(db, user, "push", "success", message, terminal, updated["local_commit"])
        finish_progress(user.id, "success", f"✓ {message}")
        return {"message": message, "status": updated, "terminal": terminal}
    except Exception as exc:
        finish_progress(user.id, failed_progress_state(user.id), f"✕ {exc}")
        raise action_error(db, user, "push", exc, terminal) from exc


@router.post("/publish")
def publish_project(
    payload: DevopsPublishRequest,
    user: Usuario = Depends(require_devops_manage),
    db: Session = Depends(get_db),
):
    if os.getenv("DEVOPS_PUBLISH_ENABLED", "false").lower() != "true":
        raise HTTPException(409, "El despliegue de ABISSOL V2 todavía no está configurado")
    terminal: list[str] = []
    begin_progress(user.id, "publish", "Verificando el proyecto antes de publicar...")
    emit = lambda line: append_progress(user.id, line)
    try:
        status, status_terminal = repository_status(
            refresh_remote=True, on_output=emit, user_id=user.id
        )
        terminal.extend(status_terminal)
        if not status["can_publish"]:
            raise CommandFailure(
                "Publicacion bloqueada: la rama local debe estar limpia y ser exactamente igual "
                "al main integrado de GitHub. Consulta GitHub y usa Bajar primero."
            )

        if PUBLISH_MODE == "workflow":
            terminal.append(dispatch_release_workflow(payload.target))
            ensure_not_cancelled(user.id)
            message = (
                "Publicación solicitada en producción mediante GitHub Actions. "
                "El workflow validará migraciones, pruebas y compilación antes de continuar."
            )
            save_log(db, user, "publish", "success", message, terminal, status["local_commit"])
            finish_progress(user.id, "success", f"✓ {message}")
            return {"message": message, "status": status, "terminal": terminal}

        if payload.target in {"frontend", "both"}:
            terminal.append(build_frontend(emit, user.id))
        else:
            emit("Se omite la compilación del frontend.")

        publish_commit = release_commit(
            status["local_commit"], payload.target, emit, user.id
        )
        terminal.append(git_output(
            "push", "--force-with-lease", REMOTE, f"{publish_commit}:{PUBLISH_BRANCH}",
            timeout=300, on_output=emit, user_id=user.id,
        ))
        target_label = {
            "backend": "solo backend",
            "frontend": "solo frontend",
            "both": "backend y frontend",
        }[payload.target]
        message = (
            f"Publicación de {target_label} enviada a la secuencia única {PUBLISH_BRANCH}. "
            "El despliegue inmediato de app fue solicitado; el servidor lo aplicará en segundos."
        )
        ensure_not_cancelled(user.id)
        save_log(db, user, "publish", "success", message, terminal, status["local_commit"])
        finish_progress(user.id, "success", f"✓ {message}")
        return {"message": message, "status": status, "terminal": terminal}
    except Exception as exc:
        finish_progress(user.id, failed_progress_state(user.id), f"✕ {exc}")
        raise action_error(db, user, "publish", exc, terminal) from exc
