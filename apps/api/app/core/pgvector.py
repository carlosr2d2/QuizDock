from pgvector.sqlalchemy import Vector as PgVector


class Vector(PgVector):
    """Force `$1::vector` binds so asyncpg does not treat embeddings as floats."""

    cache_ok = True
    render_bind_cast = True
