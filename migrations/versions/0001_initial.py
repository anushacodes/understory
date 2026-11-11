"""Initial repository, source, job and answer schema; frozen DDL.

Revision ID: 0001
"""

from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None

DDL = [
    "CREATE TABLE repositories (\n\tid VARCHAR(32) NOT NULL, \n\towner_scope VARCHAR NOT NULL, \n\tname VARCHAR(201) NOT NULL, \n\tprovider_id VARCHAR, \n\tdefault_ref VARCHAR NOT NULL, \n\tactive_snapshot_id VARCHAR(32), \n\tgeneration INTEGER NOT NULL, \n\tcreated_at TIMESTAMP WITH TIME ZONE NOT NULL, \n\tPRIMARY KEY (id), \n\tUNIQUE (owner_scope, name)\n)",
    "CREATE TABLE embedding_cache (\n\tkey VARCHAR(64) NOT NULL, \n\tconfig JSON NOT NULL, \n\tdimensions INTEGER NOT NULL, \n\tvector VECTOR NOT NULL, \n\tPRIMARY KEY (key)\n)",
    "CREATE TABLE snapshots (\n\tid VARCHAR(32) NOT NULL, \n\trepository_id VARCHAR(32) NOT NULL, \n\tcommit_sha VARCHAR(40) NOT NULL, \n\tconfig_hash VARCHAR(64) NOT NULL, \n\tconfig JSON NOT NULL, \n\tstate VARCHAR NOT NULL, \n\tcoverage JSON NOT NULL, \n\tcreated_at TIMESTAMP WITH TIME ZONE NOT NULL, \n\tready_at TIMESTAMP WITH TIME ZONE, \n\tPRIMARY KEY (id), \n\tUNIQUE (repository_id, commit_sha, config_hash), \n\tCHECK (state IN ('staging','ready','failed')), \n\tFOREIGN KEY(repository_id) REFERENCES repositories (id) ON DELETE CASCADE\n)",
    "CREATE INDEX ix_snapshots_repository_id ON snapshots (repository_id)",
    "CREATE TABLE source_versions (\n\tid VARCHAR(32) NOT NULL, \n\trepository_id VARCHAR(32) NOT NULL, \n\tpath TEXT NOT NULL, \n\tcontent_hash VARCHAR(64) NOT NULL, \n\tcontent TEXT NOT NULL, \n\tkind VARCHAR NOT NULL, \n\tline_count INTEGER NOT NULL, \n\tbyte_count INTEGER NOT NULL, \n\tPRIMARY KEY (id), \n\tUNIQUE (repository_id, path, content_hash), \n\tFOREIGN KEY(repository_id) REFERENCES repositories (id) ON DELETE CASCADE\n)",
    "CREATE INDEX ix_source_versions_repository_id ON source_versions (repository_id)",
    "CREATE TABLE snapshot_files (\n\tid BIGSERIAL NOT NULL, \n\tsnapshot_id VARCHAR(32) NOT NULL, \n\tpath TEXT NOT NULL, \n\tsource_version_id VARCHAR(32), \n\tbyte_count INTEGER NOT NULL, \n\tstate VARCHAR NOT NULL, \n\treason VARCHAR, \n\tPRIMARY KEY (id), \n\tUNIQUE (snapshot_id, path), \n\tFOREIGN KEY(snapshot_id) REFERENCES snapshots (id) ON DELETE CASCADE, \n\tFOREIGN KEY(source_version_id) REFERENCES source_versions (id) ON DELETE CASCADE\n)",
    "CREATE INDEX ix_snapshot_files_snapshot_id ON snapshot_files (snapshot_id)",
    "CREATE TABLE symbols (\n\tid VARCHAR(32) NOT NULL, \n\tsource_version_id VARCHAR(32) NOT NULL, \n\tparser VARCHAR NOT NULL, \n\tname VARCHAR NOT NULL, \n\tqualified_name VARCHAR NOT NULL, \n\tkind VARCHAR NOT NULL, \n\tparent VARCHAR, \n\tstart_line INTEGER NOT NULL, \n\tend_line INTEGER NOT NULL, \n\tPRIMARY KEY (id), \n\tUNIQUE (source_version_id, parser, qualified_name, start_line), \n\tFOREIGN KEY(source_version_id) REFERENCES source_versions (id) ON DELETE CASCADE\n)",
    "CREATE INDEX ix_symbols_qualified_name ON symbols (qualified_name)",
    "CREATE INDEX ix_symbols_name ON symbols (name)",
    "CREATE INDEX ix_symbols_source_version_id ON symbols (source_version_id)",
    "CREATE TABLE passages (\n\tid VARCHAR(32) NOT NULL, \n\tsource_version_id VARCHAR(32) NOT NULL, \n\tconfig_hash VARCHAR NOT NULL, \n\tlabel VARCHAR NOT NULL, \n\tstart_line INTEGER NOT NULL, \n\tend_line INTEGER NOT NULL, \n\texcerpt TEXT NOT NULL, \n\tsearch_text TEXT NOT NULL, \n\tembedding_key VARCHAR(64), \n\tPRIMARY KEY (id), \n\tUNIQUE (source_version_id, config_hash, start_line, end_line, label), \n\tFOREIGN KEY(source_version_id) REFERENCES source_versions (id) ON DELETE CASCADE, \n\tFOREIGN KEY(embedding_key) REFERENCES embedding_cache (key)\n)",
    "CREATE INDEX ix_passages_source_version_id ON passages (source_version_id)",
    "CREATE TABLE jobs (\n\tid VARCHAR(32) NOT NULL, \n\trepository_id VARCHAR(32) NOT NULL, \n\towner_scope VARCHAR NOT NULL, \n\tkind VARCHAR NOT NULL, \n\trequest JSON NOT NULL, \n\trequest_hash VARCHAR NOT NULL, \n\tidempotency_key VARCHAR NOT NULL, \n\tstatus VARCHAR NOT NULL, \n\tstage VARCHAR NOT NULL, \n\tgeneration INTEGER, \n\tresolved_sha VARCHAR, \n\tsnapshot_id VARCHAR(32), \n\tattempt INTEGER NOT NULL, \n\tlease_token INTEGER NOT NULL, \n\tlease_until TIMESTAMP WITH TIME ZONE, \n\theartbeat_at TIMESTAMP WITH TIME ZONE, \n\tretry_at TIMESTAMP WITH TIME ZONE, \n\tcancel_requested BOOLEAN NOT NULL, \n\tcheckpoint JSON NOT NULL, \n\tresult JSON, \n\terror JSON, \n\tevent_sequence INTEGER NOT NULL, \n\tcreated_at TIMESTAMP WITH TIME ZONE NOT NULL, \n\tfinished_at TIMESTAMP WITH TIME ZONE, \n\tPRIMARY KEY (id), \n\tUNIQUE (owner_scope, repository_id, kind, idempotency_key), \n\tCHECK (status IN ('queued','running','retry_wait','succeeded','failed','cancelled')), \n\tFOREIGN KEY(repository_id) REFERENCES repositories (id) ON DELETE CASCADE, \n\tFOREIGN KEY(snapshot_id) REFERENCES snapshots (id)\n)",
    "CREATE INDEX ix_jobs_repository_id ON jobs (repository_id)",
    "CREATE INDEX ix_jobs_status ON jobs (status)",
    "CREATE INDEX ix_jobs_eligibility ON jobs (status, retry_at, lease_until)",
    "CREATE TABLE job_events (\n\tid BIGSERIAL NOT NULL, \n\tjob_id VARCHAR(32) NOT NULL, \n\tsequence INTEGER NOT NULL, \n\tevent VARCHAR NOT NULL, \n\tpayload JSON NOT NULL, \n\tcreated_at TIMESTAMP WITH TIME ZONE NOT NULL, \n\tPRIMARY KEY (id), \n\tUNIQUE (job_id, sequence), \n\tFOREIGN KEY(job_id) REFERENCES jobs (id) ON DELETE CASCADE\n)",
    "CREATE INDEX ix_job_events_job_id ON job_events (job_id)",
    "CREATE TABLE answer_runs (\n\tid VARCHAR(32) NOT NULL, \n\trepository_id VARCHAR(32) NOT NULL, \n\tsnapshot_id VARCHAR(32) NOT NULL, \n\tjob_id VARCHAR(32) NOT NULL, \n\tkind VARCHAR NOT NULL, \n\tquestion TEXT NOT NULL, \n\tconfig JSON NOT NULL, \n\tevidence JSON NOT NULL, \n\toutput JSON, \n\tcreated_at TIMESTAMP WITH TIME ZONE NOT NULL, \n\tPRIMARY KEY (id), \n\tFOREIGN KEY(repository_id) REFERENCES repositories (id) ON DELETE CASCADE, \n\tFOREIGN KEY(snapshot_id) REFERENCES snapshots (id), \n\tUNIQUE (job_id), \n\tFOREIGN KEY(job_id) REFERENCES jobs (id) ON DELETE CASCADE\n)",
    "CREATE INDEX ix_answer_runs_repository_id ON answer_runs (repository_id)",
    "CREATE TABLE usage_events (\n\tid VARCHAR(32) NOT NULL, \n\tjob_id VARCHAR(32) NOT NULL, \n\tprovider VARCHAR NOT NULL, \n\tmodel VARCHAR NOT NULL, \n\treserved_tokens INTEGER NOT NULL, \n\tactual_tokens INTEGER, \n\toutcome VARCHAR NOT NULL, \n\tcreated_at TIMESTAMP WITH TIME ZONE NOT NULL, \n\tPRIMARY KEY (id), \n\tFOREIGN KEY(job_id) REFERENCES jobs (id) ON DELETE CASCADE\n)",
    "CREATE INDEX ix_usage_events_job_id ON usage_events (job_id)",
    "ALTER TABLE repositories ADD CONSTRAINT fk_active_snapshot FOREIGN KEY(active_snapshot_id) REFERENCES snapshots (id)",
]


def upgrade():
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    for statement in DDL:
        op.execute(statement)
    op.execute("CREATE INDEX ix_passages_lexical ON passages USING gin (to_tsvector('simple', search_text))")


def downgrade():
    op.execute("ALTER TABLE repositories DROP CONSTRAINT fk_active_snapshot")
    op.execute("DROP TABLE usage_events CASCADE")
    op.execute("DROP TABLE job_events CASCADE")
    op.execute("DROP TABLE answer_runs CASCADE")
    op.execute("DROP TABLE symbols CASCADE")
    op.execute("DROP TABLE snapshot_files CASCADE")
    op.execute("DROP TABLE passages CASCADE")
    op.execute("DROP TABLE jobs CASCADE")
    op.execute("DROP TABLE source_versions CASCADE")
    op.execute("DROP TABLE snapshots CASCADE")
    op.execute("DROP TABLE repositories CASCADE")
    op.execute("DROP TABLE embedding_cache CASCADE")
