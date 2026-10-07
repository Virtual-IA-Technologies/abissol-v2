"""Managed document folders with stable business bindings."""
from alembic import op
import sqlalchemy as sa

revision='0012_document_archive'
down_revision='0011_ubigeo_catalog'
branch_labels=None
depends_on=None

def upgrade():
    op.add_column('document_folders',sa.Column('system_key',sa.String(180),nullable=True))
    op.create_unique_constraint('uq_document_folder_system_key','document_folders',['system_key'])
    op.add_column('documents',sa.Column('is_system',sa.Boolean(),nullable=False,server_default='0'))
    op.create_index('ix_documents_is_system','documents',['is_system'])
    op.create_table('document_bindings',sa.Column('id',sa.Integer(),primary_key=True),
        sa.Column('document_id',sa.Integer(),sa.ForeignKey('documents.id'),nullable=False,unique=True),
        sa.Column('source_type',sa.String(40),nullable=False),sa.Column('source_id',sa.Integer(),nullable=False),
        sa.Column('artifact_key',sa.String(80),nullable=False),
        sa.UniqueConstraint('source_type','source_id','artifact_key',name='uq_document_source_artifact'))

def downgrade():
    op.drop_table('document_bindings')
    op.drop_index('ix_documents_is_system','documents')
    op.drop_column('documents','is_system')
    op.drop_constraint('uq_document_folder_system_key','document_folders',type_='unique')
    op.drop_column('document_folders','system_key')
