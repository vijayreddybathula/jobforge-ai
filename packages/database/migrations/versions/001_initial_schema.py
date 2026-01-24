"""Initial schema

Revision ID: 001_initial
Revises: 
Create Date: 2024-01-01 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from pgvector.sqlalchemy import Vector

# revision identifiers, used by Alembic.
revision = '001_initial'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Enable pgvector extension
    op.execute('CREATE EXTENSION IF NOT EXISTS vector')
    
    # Users table
    op.create_table(
        'users',
        sa.Column('user_id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('email', sa.String(255), nullable=False, unique=True),
        sa.Column('hashed_password', sa.String(255), nullable=False),
        sa.Column('full_name', sa.String(255)),
        sa.Column('is_active', sa.Boolean(), default=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
    )
    op.create_index('ix_users_email', 'users', ['email'])
    
    # Resumes table
    op.create_table(
        'resumes',
        sa.Column('resume_id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.user_id'), nullable=False),
        sa.Column('file_path', sa.String(500), nullable=False),
        sa.Column('file_name', sa.String(255), nullable=False),
        sa.Column('file_type', sa.String(50)),
        sa.Column('content_hash', sa.String(64), unique=True),
        sa.Column('parsed_data', postgresql.JSONB),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
    )
    op.create_index('ix_resumes_user_id', 'resumes', ['user_id'])
    op.create_index('ix_resumes_content_hash', 'resumes', ['content_hash'])
    
    # Role matches table
    op.create_table(
        'role_matches',
        sa.Column('role_match_id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('resume_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('resumes.resume_id'), nullable=False),
        sa.Column('role_title', sa.String(255), nullable=False),
        sa.Column('confidence_score', sa.Integer()),
        sa.Column('is_confirmed', sa.Boolean(), default=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
    )
    op.create_index('ix_role_matches_resume_id', 'role_matches', ['resume_id'])
    
    # User profiles table
    op.create_table(
        'user_profiles',
        sa.Column('profile_id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.user_id'), nullable=False, unique=True),
        sa.Column('core_roles', postgresql.JSONB),
        sa.Column('skills', postgresql.JSONB),
        sa.Column('approved_bullets', postgresql.JSONB),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
    )
    op.create_index('ix_user_profiles_user_id', 'user_profiles', ['user_id'])
    
    # User preferences table
    op.create_table(
        'user_preferences',
        sa.Column('preferences_id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.user_id'), nullable=False, unique=True),
        sa.Column('visa_status', sa.String(100)),
        sa.Column('location_preferences', postgresql.JSONB),
        sa.Column('disability_status', sa.String(100)),
        sa.Column('disability_accommodations', sa.Text()),
        sa.Column('salary_min_usd', sa.Integer()),
        sa.Column('salary_max_usd', sa.Integer()),
        sa.Column('company_size_preferences', postgresql.JSONB),
        sa.Column('industry_preferences', postgresql.JSONB),
        sa.Column('work_authorization', sa.String(100)),
        sa.Column('other_constraints', postgresql.JSONB),
        sa.Column('is_ready', sa.Boolean(), default=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
    )
    op.create_index('ix_user_preferences_user_id', 'user_preferences', ['user_id'])
    
    # Ingestion sources table
    op.create_table(
        'ingestion_sources',
        sa.Column('source_id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.user_id'), nullable=False),
        sa.Column('source_type', sa.String(50), nullable=False),
        sa.Column('source_url', sa.String(1000), nullable=False),
        sa.Column('is_active', sa.Boolean(), default=True),
        sa.Column('last_run_at', sa.DateTime(timezone=True)),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
    )
    op.create_index('ix_ingestion_sources_user_id', 'ingestion_sources', ['user_id'])
    op.create_index('idx_source_user_type', 'ingestion_sources', ['user_id', 'source_type'])
    
    # Scraping sessions table
    op.create_table(
        'scraping_sessions',
        sa.Column('session_id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('source_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('ingestion_sources.source_id'), nullable=False),
        sa.Column('jobs_found', sa.Integer(), default=0),
        sa.Column('jobs_ingested', sa.Integer(), default=0),
        sa.Column('jobs_duplicates', sa.Integer(), default=0),
        sa.Column('jobs_failed', sa.Integer(), default=0),
        sa.Column('status', sa.String(50), default='running'),
        sa.Column('error_message', sa.Text()),
        sa.Column('started_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
        sa.Column('completed_at', sa.DateTime(timezone=True)),
    )
    op.create_index('ix_scraping_sessions_source_id', 'scraping_sessions', ['source_id'])
    
    # Jobs raw table
    op.create_table(
        'jobs_raw',
        sa.Column('job_id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('source', sa.String(50), nullable=False),
        sa.Column('source_url', sa.String(1000), unique=True, nullable=False),
        sa.Column('company', sa.String(255)),
        sa.Column('title', sa.String(500)),
        sa.Column('location', sa.String(255)),
        sa.Column('posted_at', sa.DateTime(timezone=True)),
        sa.Column('html_snapshot_path', sa.String(500)),
        sa.Column('text_content', sa.Text()),
        sa.Column('content_hash', sa.String(64), unique=True),
        sa.Column('ingest_status', sa.String(50), default='INGESTED'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
    )
    op.create_index('ix_jobs_raw_source', 'jobs_raw', ['source'])
    op.create_index('ix_jobs_raw_source_url', 'jobs_raw', ['source_url'])
    op.create_index('ix_jobs_raw_company', 'jobs_raw', ['company'])
    op.create_index('ix_jobs_raw_title', 'jobs_raw', ['title'])
    op.create_index('ix_jobs_raw_content_hash', 'jobs_raw', ['content_hash'])
    op.create_index('ix_jobs_raw_ingest_status', 'jobs_raw', ['ingest_status'])
    
    # Jobs parsed table
    op.create_table(
        'jobs_parsed',
        sa.Column('parsed_id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('job_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('jobs_raw.job_id'), nullable=False, unique=True),
        sa.Column('parsed_json', postgresql.JSONB, nullable=False),
        sa.Column('parser_version', sa.String(50)),
        sa.Column('parse_status', sa.String(50), default='PARSED'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
    )
    op.create_index('ix_jobs_parsed_job_id', 'jobs_parsed', ['job_id'])
    op.create_index('ix_jobs_parsed_parse_status', 'jobs_parsed', ['parse_status'])
    
    # Job scores table
    op.create_table(
        'job_scores',
        sa.Column('score_id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('job_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('jobs_raw.job_id'), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.user_id'), nullable=False),
        sa.Column('total_score', sa.Integer(), nullable=False),
        sa.Column('breakdown', postgresql.JSONB),
        sa.Column('verdict', sa.String(50), nullable=False),
        sa.Column('rationale', sa.Text()),
        sa.Column('scoring_version', sa.String(50)),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
    )
    op.create_index('ix_job_scores_job_id', 'job_scores', ['job_id'])
    op.create_index('ix_job_scores_user_id', 'job_scores', ['user_id'])
    op.create_index('ix_job_scores_total_score', 'job_scores', ['total_score'])
    op.create_index('ix_job_scores_verdict', 'job_scores', ['verdict'])
    op.create_index('idx_job_user_score', 'job_scores', ['job_id', 'user_id', 'total_score'])
    
    # Artifacts table
    op.create_table(
        'artifacts',
        sa.Column('artifact_id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('job_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('jobs_raw.job_id'), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.user_id'), nullable=False),
        sa.Column('artifact_type', sa.String(50), nullable=False),
        sa.Column('path', sa.String(500), nullable=False),
        sa.Column('metadata', postgresql.JSONB),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
    )
    op.create_index('ix_artifacts_job_id', 'artifacts', ['job_id'])
    op.create_index('ix_artifacts_user_id', 'artifacts', ['user_id'])
    op.create_index('ix_artifacts_artifact_type', 'artifacts', ['artifact_type'])
    op.create_index('idx_artifact_job_type', 'artifacts', ['job_id', 'artifact_type'])
    
    # Applications table
    op.create_table(
        'applications',
        sa.Column('application_id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('job_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('jobs_raw.job_id'), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.user_id'), nullable=False),
        sa.Column('apply_mode', sa.String(50), nullable=False),
        sa.Column('status', sa.String(50), default='started'),
        sa.Column('submitted_at', sa.DateTime(timezone=True)),
        sa.Column('notes', sa.Text()),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
    )
    op.create_index('ix_applications_job_id', 'applications', ['job_id'])
    op.create_index('ix_applications_user_id', 'applications', ['user_id'])
    op.create_index('ix_applications_status', 'applications', ['status'])
    
    # Outcomes table
    op.create_table(
        'outcomes',
        sa.Column('outcome_id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('application_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('applications.application_id'), nullable=False),
        sa.Column('stage', sa.String(50), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
        sa.Column('source', sa.String(50)),
        sa.Column('details', postgresql.JSONB),
    )
    op.create_index('ix_outcomes_application_id', 'outcomes', ['application_id'])
    op.create_index('ix_outcomes_stage', 'outcomes', ['stage'])


def downgrade() -> None:
    op.drop_table('outcomes')
    op.drop_table('applications')
    op.drop_table('artifacts')
    op.drop_table('job_scores')
    op.drop_table('jobs_parsed')
    op.drop_table('jobs_raw')
    op.drop_table('scraping_sessions')
    op.drop_table('ingestion_sources')
    op.drop_table('user_preferences')
    op.drop_table('user_profiles')
    op.drop_table('role_matches')
    op.drop_table('resumes')
    op.drop_table('users')
    op.execute('DROP EXTENSION IF EXISTS vector')
