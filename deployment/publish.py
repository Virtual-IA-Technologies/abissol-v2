"""Publica el commit de main sincronizado con GitHub. Configuración en deployment/.env."""
from __future__ import annotations
import os
import shutil
import subprocess
import tarfile
import tempfile
from pathlib import Path
import sys
import hashlib
import json

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "BackEnd"))
from dotenv import dotenv_values
from app.services.main_workflow import repository_status, validate_delivery_files

def run(args, **kwargs):
    subprocess.run([str(arg) for arg in args], check=True, **kwargs)

def dist_digest(directory):
    digest = hashlib.sha256()
    for file in sorted(directory.rglob("*")):
        if file.is_file():
            digest.update(file.relative_to(directory).as_posix().encode())
            digest.update(file.read_bytes())
    return digest.hexdigest()

def main():
    config = dotenv_values(ROOT / "deployment/.env")
    if config.get("SSH_HOST") != "161.132.50.114" or config.get("DOMAIN") != "v2.abissol.org":
        raise RuntimeError("Configura deployment/.env para el piloto autorizado.")
    status, _ = repository_status(root=ROOT, refresh_remote=True)
    if status["branch"] != "main" or status["changes"] or status["ahead"] or status["behind"] or status["fetch_error"]:
        raise RuntimeError("Primero sincroniza main limpio con origin/main.")
    validate_delivery_files(ROOT)
    commit = status["local_commit"]
    frontend = ROOT / "FrontEnd/frontend-app"
    # Reutilizar solamente un build del mismo árbol, origen y contenido verificado.
    tree = subprocess.check_output(["git", "rev-parse", "HEAD:FrontEnd/frontend-app"], cwd=ROOT, text=True).strip()
    stamp = ROOT / ".local/frontend-build.json"
    cached = json.loads(stamp.read_text()) if stamp.exists() else {}
    build_key = tree + ":https://v2.abissol.org"
    npm = "npm.cmd" if os.name == "nt" else "npm"
    if cached.get("key") != build_key or not (frontend / "dist/index.html").exists() or cached.get("digest") != dist_digest(frontend / "dist"):
        run([npm, "run", "build"], cwd=frontend, env={**os.environ, "VITE_API_URL": "https://v2.abissol.org"})
        stamp.parent.mkdir(exist_ok=True)
        stamp.write_text(json.dumps({"key": build_key, "digest": dist_digest(frontend / "dist")}))
    else:
        print("Build de producción verificado; reutilizando los mismos archivos.", flush=True)
    with tempfile.TemporaryDirectory(prefix="abissol-publish-") as directory:
        tmp = Path(directory)
        key = tmp / "identity"
        shutil.copyfile(config["SSH_KEY"], key)
        try:
            if os.name == "nt":
                run(["icacls", key, "/inheritance:r", "/grant:r", os.environ["USERNAME"] + ":(F)"], stdout=subprocess.DEVNULL)
            else: key.chmod(0o600)
            options = ["-i", key, "-o", "StrictHostKeyChecking=yes", "-o", "IdentitiesOnly=yes",
                       "-o", "UserKnownHostsFile=" + config["SSH_KNOWN_HOSTS"], "-o", "ConnectTimeout=15"]
            archive = tmp / "release.tar"
            run(["git", "archive", "--format=tar", "--output", archive, commit], cwd=ROOT)
            with tarfile.open(archive, "a") as bundle:
                bundle.add(frontend / "dist", arcname="FrontEnd/frontend-app/dist")
            import gzip
            compressed = tmp / "release.tar.gz"
            with archive.open("rb") as source, gzip.open(compressed, "wb", compresslevel=3) as output:
                shutil.copyfileobj(source, output)
            target = "root@" + config["SSH_HOST"]
            remote = "/home/abissol/apps/abissol-v2/incoming-" + commit + ".tar.gz"
            run(["scp", *options, compressed, target + ":" + remote])
            script = (ROOT / "deployment/server.sh").read_text(encoding="utf-8").replace("\r", "")
            run(["ssh", *options, target, "bash -s -- " + commit], input=script.encode("utf-8"))
            print("Piloto publicado: https://v2.abissol.org/ — commit " + commit)
        finally:
            key.unlink(missing_ok=True)

if __name__ == "__main__": main()
