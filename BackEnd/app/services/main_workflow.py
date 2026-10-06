"""Flujo exclusivo main -> origin/main; sin merges automáticos ni force push."""
from __future__ import annotations
import os
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
EXPECTED_REMOTE = "https://github.com/Virtual-IA-Technologies/abissol-v2.git"

class RepositoryError(RuntimeError):
    pass

def git(root: Path, *args: str) -> str:
    environment = {**os.environ, "GIT_TERMINAL_PROMPT": "0", "GCM_INTERACTIVE": "never"}
    result = subprocess.run(["git", *args], cwd=root, env=environment, capture_output=True,
                            text=True, encoding="utf-8", errors="replace", timeout=90)
    if result.returncode:
        raise RepositoryError(f"Git no pudo completar {args[0]}; revisa conexión, permisos y estado local.")
    return result.stdout.strip()

def _optional(root, *args):
    try: return git(root, *args)
    except RepositoryError: return None

def _remote_valid(url):
    return url.rstrip('/') in {EXPECTED_REMOTE, EXPECTED_REMOTE[:-4],
        "git@github.com:Virtual-IA-Technologies/abissol-v2.git"}

def repository_status(*, root=ROOT, refresh_remote=False, on_output=None):
    root = Path(root)
    branch = git(root, "branch", "--show-current")
    remote_url = _optional(root, "remote", "get-url", "origin") or ""
    remote_valid = _remote_valid(remote_url)
    fetch_error = None
    if refresh_remote:
        if not remote_valid:
            fetch_error = "origin no corresponde al repositorio ABISSOL V2 configurado."
        else:
            try:
                if on_output: on_output("Consultando origin/main...")
                git(root, "fetch", "--prune", "origin")
            except RepositoryError as exc: fetch_error = str(exc)
    changes = git(root, "status", "--porcelain").splitlines()
    local = git(root, "rev-parse", "HEAD")
    remote = _optional(root, "rev-parse", "--verify", "refs/remotes/origin/main")
    ahead, behind = (int(git(root,"rev-list","--count","HEAD")), 0) if not remote else map(int,git(root,"rev-list","--left-right","--count","HEAD...origin/main").split())
    conflict = bool(git(root,"diff","--name-only","--diff-filter=U"))
    git_dir = Path(git(root,"rev-parse","--absolute-git-dir"))
    conflict |= any((git_dir/name).exists() for name in ('MERGE_HEAD','rebase-merge','rebase-apply','CHERRY_PICK_HEAD'))
    local_mode = os.getenv("APP_ENV", "development") != "production"
    allowed = branch == "main" and remote_valid and not fetch_error and not conflict and local_mode
    deploy_configured = os.getenv("DEVOPS_PUBLISH_ENABLED", "false").lower() == "true" and (root/'deployment/publish.py').is_file()
    if not remote_valid: message = "Configura origin con el repositorio ABISSOL V2."
    elif branch != "main": message = "Este proyecto trabaja exclusivamente en main."
    elif fetch_error: message = fetch_error
    elif conflict or ahead and behind: message = "Hay cambios divergentes; resolverlos antes de continuar."
    elif behind: message = "Hay cambios en GitHub. Bajar requiere el árbol local limpio."
    elif changes: message = "Hay archivos locales pendientes de subir a main."
    elif ahead: message = "Hay commits locales pendientes de subir a main."
    else: message = "main coincide con origin/main."
    state = 'offline' if fetch_error or not remote_valid else 'diverged' if conflict or ahead and behind else 'behind' if behind else 'dirty' if changes else 'ahead' if ahead else 'synced'
    return {
        'repository': str(root), 'remote_url': remote_url if remote_valid else '', 'branch': branch,
        'local_commit': local, 'remote_commit': remote, 'ahead': ahead, 'behind': behind,
        'changes': changes, 'state': state, 'message': message, 'fetch_error': fetch_error,
        'read_only': not local_mode, 'deployment_configured': deploy_configured,
        'can_pull': allowed and not changes and not ahead and bool(behind),
        'can_push': allowed and not behind and bool(changes or ahead or not remote),
        'can_publish': allowed and not changes and not ahead and not behind and remote == local and deploy_configured,
    }, []

def assert_publishable(status, action):
    if not status.get('can_'+action):
        raise RepositoryError(status.get('message') or 'Operación no disponible')

def validate_delivery_files(root=ROOT):
    """No permite versionar secretos o artefactos; no imprime su contenido."""
    names=git(root,'ls-files','-z').split('\0')
    banned=re.compile(r'(^|/)(\.env($|\.(?!example$))|\.venv/|node_modules/|storage/|\.local/|dist/)|\.(pem|key|sql)$')
    signatures=[re.compile(rb'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----'),
                re.compile(rb'gh[pousr]_[A-Za-z0-9]{30,}'), re.compile(rb'sk-proj-[A-Za-z0-9_-]{30,}')]
    for name in filter(None,names):
        p=Path(root)/name
        if banned.search(name) or (p.is_file() and p.stat().st_size<2_000_000 and any(pattern.search(p.read_bytes()) for pattern in signatures)):
            raise RepositoryError('Archivo no permitido en Git: '+name)
