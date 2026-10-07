"""Install the bundled public geographic catalog without replacing existing rows."""
import csv
from pathlib import Path
import sqlalchemy as sa
from alembic import op

revision='0011_ubigeo_catalog'
down_revision='0010_invoice_choice'
branch_labels=None
depends_on=None


def upgrade():
    connection=op.get_bind()
    existing=set(connection.execute(sa.text('SELECT code FROM ubigeos')).scalars())
    table=sa.table('ubigeos',sa.column('code',sa.String),sa.column('department_code',sa.String),
        sa.column('department',sa.String),sa.column('province_code',sa.String),
        sa.column('province',sa.String),sa.column('district',sa.String),sa.column('is_active',sa.Boolean))
    path=Path(__file__).resolve().parents[2]/'app/data/ubigeos_peru.csv'
    with path.open(encoding='utf-8-sig',newline='') as handle:
        rows=[{'code':row['ubigeo'],'department_code':row['department_code'],'department':row['department'],
               'province_code':row['province_code'],'province':row['province'],'district':row['district'],'is_active':True}
              for row in csv.DictReader(handle) if row['ubigeo'] not in existing]
    for offset in range(0,len(rows),200):op.bulk_insert(table,rows[offset:offset+200])


def downgrade():
    # Shared public data may already be referenced by business records; retain it.
    pass
