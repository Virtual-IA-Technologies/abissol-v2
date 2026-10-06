"""Restaurar rutas implementadas sin cambiar etiquetas, padres ni posiciones."""
from alembic import op
import sqlalchemy as sa

revision = "0003_medical_routes"
down_revision = "0002_medical"
branch_labels = None
depends_on = None


def upgrade():
    menus = sa.table("menus", sa.column("slug", sa.String), sa.column("ruta", sa.String))
    for section in ("plans", "network", "emissions", "dispatches", "liquidations", "billing", "reports"):
        op.execute(menus.update().where(menus.c.slug == "medical-" + section).values(ruta="/plataforma/medical/" + section))


def downgrade():
    # La reparación no debe reintroducir enlaces rotos al revertir código.
    pass
