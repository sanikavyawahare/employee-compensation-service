import os
import pyodbc


def get_connection() -> pyodbc.Connection:
    """Connection string comes from app settings (env), never from source."""
    conn_str = os.environ.get("SQL_CONNECTION_STRING")
    if not conn_str:
        raise RuntimeError("SQL_CONNECTION_STRING is not configured")
    return pyodbc.connect(conn_str, timeout=15)


def query(sql: str, params: tuple = ()) -> list[dict]:
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute(sql, params)
        if cur.description is None:
            return []
        cols = [c[0] for c in cur.description]
        return [dict(zip(cols, row)) for row in cur.fetchall()]


def execute(sql: str, params: tuple = ()) -> list[dict]:
    """Run a write; returns rows if the statement has an OUTPUT clause. Commits on success."""
    with get_connection() as conn:  
        cur = conn.cursor()
        cur.execute(sql, params)
        rows = []
        if cur.description is not None:
            cols = [c[0] for c in cur.description]
            rows = [dict(zip(cols, r)) for r in cur.fetchall()]
        rowcount = cur.rowcount
    return rows if rows else [{"_rowcount": rowcount}]
