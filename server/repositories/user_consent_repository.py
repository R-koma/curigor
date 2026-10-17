from core.database import DBConnection


async def has_consented(conn: DBConnection, user_id: str, terms_version: int) -> bool:
    query = """--sql
    SELECT EXISTS (SELECT 1 FROM user_consents WHERE user_id = $1 AND terms_version = $2)
    """
    consented: bool = await conn.fetchval(query, user_id, terms_version)
    return consented


async def record(conn: DBConnection, user_id: str, terms_version: int) -> None:
    query = """--sql
    INSERT INTO user_consents (user_id, terms_version)
    VALUES ($1, $2)
    ON CONFLICT (user_id, terms_version) DO NOTHING
    """
    await conn.execute(query, user_id, terms_version)
