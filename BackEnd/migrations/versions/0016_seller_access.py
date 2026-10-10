"""Commercial accounts can settle and view only scoped business documents."""
from alembic import op
import sqlalchemy as sa
revision = '0016_seller_access'
down_revision = '0015_medical_test_batch'
branch_labels = None
depends_on = None

def upgrade():
    connection = op.get_bind()
    for slug, level in [('medical-liquidations', 'editor'), ('medical-billing', 'lector'), ('documentos', 'editor')]:
        connection.execute(sa.text("""INSERT INTO access_grants (role_id, menu_id, access_level, is_active, created_at, updated_at)
            SELECT r.id, m.id, :level, 1, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
            FROM roles r JOIN menus m ON m.slug=:slug
            WHERE r.nombre IN (:responsible, :emitter, :coordinator)
            AND NOT EXISTS (SELECT 1 FROM access_grants a WHERE a.role_id=r.id AND a.menu_id=m.id)"""),
            dict(slug=slug, level=level, responsible='Comercial · Vendedor responsable', emitter='Comercial · Emisor dependiente', coordinator='Comercial · Coordinador de origen'))

def downgrade():
    # Preserve explicit account permissions; permission rollback is an audited administrative action.
    pass
