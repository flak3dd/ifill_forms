"""Add Profile Management tables

Revision ID: 001
Revises: 
Create Date: 2026-04-21 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '001'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Profile fields table
    op.create_table(
        'profile_fields',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('label', sa.String(), nullable=True),
        sa.Column('field_type', sa.String(), nullable=False, server_default='text'),
        sa.Column('semantic_tag', sa.String(), nullable=False, server_default='custom'),
        sa.Column('required', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('locator_type', sa.String(), nullable=False, server_default='css'),
        sa.Column('locator_value', sa.String(), nullable=False),
        sa.Column('locator_fallback', postgresql.JSON(), nullable=True),
        sa.Column('validation_regex', sa.String(), nullable=True),
        sa.Column('min_length', sa.Integer(), nullable=True),
        sa.Column('max_length', sa.Integer(), nullable=True),
        sa.Column('options', postgresql.JSON(), nullable=True),
        sa.Column('is_visible', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('is_in_iframe', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('iframe_selector', sa.String(), nullable=True),
        sa.Column('order_index', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('detection_confidence', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('ai_reasoning', sa.String(), nullable=True),
        sa.Column('profile_id', sa.String(), nullable=False),
        sa.Column('workflow_step_id', sa.String(), nullable=True),
        sa.ForeignKeyConstraint(['profile_id'], ['profile.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['workflow_step_id'], ['workflow_step.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_profile_fields_profile_id', 'profile_fields', ['profile_id'])
    op.create_index('ix_profile_fields_semantic_tag', 'profile_fields', ['semantic_tag'])
    
    # Workflow steps table
    op.create_table(
        'workflow_step',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('step_type', sa.String(), nullable=False),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('description', sa.String(), nullable=True),
        sa.Column('order_index', sa.Integer(), nullable=False),
        sa.Column('config', postgresql.JSON(), nullable=False, server_default='{}'),
        sa.Column('condition', sa.String(), nullable=True),
        sa.Column('retry_count', sa.Integer(), nullable=False, server_default='3'),
        sa.Column('retry_delay_ms', sa.Integer(), nullable=False, server_default='1000'),
        sa.Column('on_error', sa.String(), nullable=False, server_default='fail'),
        sa.Column('profile_id', sa.String(), nullable=False),
        sa.Column('parent_step_id', sa.String(), nullable=True),
        sa.ForeignKeyConstraint(['profile_id'], ['profile.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['parent_step_id'], ['workflow_step.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_workflow_step_profile_id', 'workflow_step', ['profile_id'])
    
    # Profile versions table
    op.create_table(
        'profile_versions',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('version_number', sa.Integer(), nullable=False),
        sa.Column('snapshot', postgresql.JSON(), nullable=False),
        sa.Column('change_summary', sa.String(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('created_by', sa.String(), nullable=True),
        sa.Column('profile_id', sa.String(), nullable=False),
        sa.ForeignKeyConstraint(['profile_id'], ['profile.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['created_by'], ['user.id']),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_profile_versions_profile_id', 'profile_versions', ['profile_id'])
    op.create_index('ix_profile_versions_version_number', 'profile_versions', ['version_number'])
    
    # Mapping sessions table
    op.create_table(
        'mapping_session',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('csv_headers', postgresql.ARRAY(sa.String()), nullable=False),
        sa.Column('csv_sample_rows', postgresql.JSON(), nullable=False),
        sa.Column('is_complete', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('profile_id', sa.String(), nullable=False),
        sa.ForeignKeyConstraint(['profile_id'], ['profile.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Column mappings table
    op.create_table(
        'column_mappings',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('csv_column_name', sa.String(), nullable=False),
        sa.Column('csv_sample_values', postgresql.ARRAY(sa.String()), nullable=True),
        sa.Column('field_id', sa.String(), nullable=True),
        sa.Column('semantic_tag', sa.String(), nullable=True),
        sa.Column('transform_template', sa.String(), nullable=True),
        sa.Column('transform_function', sa.String(), nullable=True),
        sa.Column('confidence', sa.String(), nullable=False, server_default='manual'),
        sa.Column('ai_reasoning', sa.String(), nullable=True),
        sa.Column('is_user_override', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.Column('profile_id', sa.String(), nullable=False),
        sa.Column('mapping_session_id', sa.String(), nullable=True),
        sa.ForeignKeyConstraint(['profile_id'], ['profile.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['field_id'], ['profile_fields.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['mapping_session_id'], ['mapping_session.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_column_mappings_profile_id', 'column_mappings', ['profile_id'])
    op.create_index('ix_column_mappings_session_id', 'column_mappings', ['mapping_session_id'])


def downgrade() -> None:
    op.drop_index('ix_column_mappings_session_id', table_name='column_mappings')
    op.drop_index('ix_column_mappings_profile_id', table_name='column_mappings')
    op.drop_table('column_mappings')
    op.drop_table('mapping_session')
    op.drop_index('ix_profile_versions_version_number', table_name='profile_versions')
    op.drop_index('ix_profile_versions_profile_id', table_name='profile_versions')
    op.drop_table('profile_versions')
    op.drop_index('ix_workflow_step_profile_id', table_name='workflow_step')
    op.drop_table('workflow_step')
    op.drop_index('ix_profile_fields_semantic_tag', table_name='profile_fields')
    op.drop_index('ix_profile_fields_profile_id', table_name='profile_fields')
    op.drop_table('profile_fields')
