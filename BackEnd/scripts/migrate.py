"""Aplica exclusivamente las migraciones de ABISSOL V2."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from alembic import command
from alembic.config import Config

if __name__ == "__main__":
    command.upgrade(Config(str(Path(__file__).resolve().parents[1] / "alembic.ini")), "head")
