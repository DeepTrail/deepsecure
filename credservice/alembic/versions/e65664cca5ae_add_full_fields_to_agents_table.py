"""add_full_fields_to_agents_table"""

# revision identifiers, used by Alembic.
revision = 'e65664cca5ae'
down_revision = 'fad6afa30f7f'
branch_labels = None
depends_on = None

from alembic import op
import sqlalchemy as sa
# from sqlalchemy.dialects import postgresql # Uncomment if specific PG types are needed


def upgrade() -> None:
    op.add_column('agents', sa.Column('name', sa.String(length=255), nullable=True))
    op.create_index(op.f('ix_agents_name'), 'agents', ['name'], unique=False)

    op.add_column('agents', sa.Column('description', sa.Text(), nullable=True))

    op.add_column('agents', sa.Column('status', sa.String(length=50), nullable=False, server_default='active'))
    op.create_index(op.f('ix_agents_status'), 'agents', ['status'], unique=False)

    op.add_column('agents', sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False))
    # Note: for onupdate, DDL usually just sets server_default. Application logic or DB triggers handle actual updates.
    
    op.add_column('agents', sa.Column('last_seen_at', sa.DateTime(timezone=True), nullable=True))

    # Add unique constraint for current_public_key as per model unique=True
    # Assuming it doesn't exist yet. If it might, add checks or try-except.
    op.create_unique_constraint(op.f('uq_agents_current_public_key'), 'agents', ['current_public_key'])

    # Ensure created_at is not nullable as per model
    op.alter_column('agents', 'created_at', 
                    existing_type=sa.DateTime(timezone=True),
                    nullable=False,
                    existing_server_default=sa.text('now()'))


def downgrade() -> None:
    op.alter_column('agents', 'created_at',
                    existing_type=sa.DateTime(timezone=True),
                    nullable=True,
                    existing_server_default=sa.text('now()')) # Revert to original nullability if needed

    op.drop_constraint(op.f('uq_agents_current_public_key'), 'agents', type_='unique')
    
    op.drop_column('agents', 'last_seen_at')
    op.drop_column('agents', 'updated_at')
    
    op.drop_index(op.f('ix_agents_status'), table_name='agents')
    op.drop_column('agents', 'status')
    
    op.drop_column('agents', 'description')
    
    op.drop_index(op.f('ix_agents_name'), table_name='agents')
    op.drop_column('agents', 'name')