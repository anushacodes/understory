from alembic import context
from app.config import settings
from app.models import Base
from sqlalchemy import create_engine

config = context.config

if context.is_offline_mode():
    context.configure(url=settings.database_url, target_metadata=Base.metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()
else:

    def migrate(connection):
        context.configure(
            connection=connection,
            target_metadata=Base.metadata,
            version_table_schema=config.attributes.get("version_table_schema"),
        )
        with context.begin_transaction():
            context.run_migrations()

    supplied = config.attributes.get("connection")
    if supplied is not None:
        migrate(supplied)
    else:
        with create_engine(settings.database_url).connect() as connection:
            migrate(connection)
