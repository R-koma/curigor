from core.database import DBConnection


async def find_hint_ids_by_user(conn: DBConnection, user_id: str) -> list[str]:
    query = """--sql
    SELECT hint_id FROM user_hint_dismissals WHERE user_id = $1 ORDER BY hint_id
    """
    rows = await conn.fetch(query, user_id)
    return [row["hint_id"] for row in rows]


async def dismiss(conn: DBConnection, user_id: str, hint_id: str) -> None:
    query = """--sql
    INSERT INTO user_hint_dismissals (user_id, hint_id)
    VALUES ($1, $2)
    ON CONFLICT (user_id, hint_id) DO NOTHING
    """
    await conn.execute(query, user_id, hint_id)


async def delete_all_by_user(conn: DBConnection, user_id: str) -> None:
    query = """--sql
    DELETE FROM user_hint_dismissals WHERE user_id = $1
    """
    await conn.execute(query, user_id)
