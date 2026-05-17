"""
db_analyzer.py
Kết nối SQL Server (Windows Auth), lấy stored procedures / views / functions,
parse dependency và trả về graph_data cùng format với sql_visualizer.
"""

from collections import defaultdict
from sql_visualizer import parse_sql_text

try:
    import pyodbc
except ImportError:
    pyodbc = None

# Thứ tự thử driver — dùng driver đầu tiên tìm thấy
_DRIVERS = [
    "ODBC Driver 18 for SQL Server",
    "ODBC Driver 17 for SQL Server",
    "ODBC Driver 13 for SQL Server",
    "SQL Server Native Client 11.0",
    "SQL Server",
]


def _get_driver() -> str | None:
    if pyodbc is None:
        return None
    available = {d for d in pyodbc.drivers()}
    for d in _DRIVERS:
        if d in available:
            return d
    return None


def _connect(server: str, database: str = "master"):
    if pyodbc is None:
        raise RuntimeError("Thiếu thư viện pyodbc. Chạy: pip install pyodbc")
    driver = _get_driver()
    if driver is None:
        raise RuntimeError(
            "Không tìm thấy ODBC Driver cho SQL Server.\n"
            "Tải tại: https://learn.microsoft.com/sql/connect/odbc/download-odbc-driver-for-sql-server"
        )
    conn_str = (
        f"DRIVER={{{driver}}};"
        f"SERVER={server};"
        f"DATABASE={database};"
        "Trusted_Connection=yes;"
        "TrustServerCertificate=yes;"
        "Connection Timeout=10;"
    )
    return pyodbc.connect(conn_str)


# ── Public API ────────────────────────────────────────────────────────────────

def list_databases(server: str) -> list[str]:
    """Trả về danh sách database user (bỏ system DB) trên server."""
    conn = _connect(server)
    cur = conn.cursor()
    cur.execute("""
        SELECT name FROM sys.databases
        WHERE database_id > 4
          AND state_desc = 'ONLINE'
          AND name NOT IN ('ReportServer','ReportServerTempDB')
        ORDER BY name
    """)
    dbs = [row[0] for row in cur.fetchall()]
    conn.close()
    return dbs


def analyze_database(server: str, database: str) -> dict:
    """
    Kết nối DB, lấy tất cả SP / View / Function / Table,
    parse dependency và trả về graph_data.

    graph_data = {
        "files":  { object_name: {"creates": set, "uses": set, "node_type": str} },
        "tables": { table_name:  {"created_by": [...], "used_by": [...], "node_type": "table"} },
    }
    """
    conn = _connect(server, database)
    cur  = conn.cursor()

    # ── Lấy định nghĩa SP / View / Function ──────────────────────────────────
    cur.execute("""
        SELECT
            o.name          AS obj_name,
            o.type          AS obj_type,   -- P, V, FN, TF, IF
            m.definition    AS body
        FROM sys.sql_modules  m
        JOIN sys.objects      o ON m.object_id = o.object_id
        WHERE o.type IN ('P','V','FN','TF','IF')
          AND o.is_ms_shipped = 0
        ORDER BY o.name
    """)
    objects = cur.fetchall()

    # ── Lấy danh sách bảng thật trong DB ─────────────────────────────────────
    cur.execute("""
        SELECT TABLE_NAME FROM INFORMATION_SCHEMA.TABLES
        WHERE TABLE_TYPE = 'BASE TABLE'
    """)
    real_tables = {row[0].upper() for row in cur.fetchall()}
    conn.close()

    _TYPE_MAP = {
        "P":  "procedure",
        "V":  "view",
        "FN": "function",
        "TF": "function",
        "IF": "function",
    }

    file_data: dict  = {}
    all_tables: dict = defaultdict(lambda: {"created_by": [], "used_by": [], "node_type": "table"})

    obj_names_upper = {row[0].upper() for row in objects}  # để detect EXEC gọi SP khác

    for obj_name, obj_type, body in objects:
        ntype  = _TYPE_MAP.get(obj_type.strip(), "procedure")
        parsed = parse_sql_text(obj_name, body or "")

        # Lọc: chỉ giữ references đến bảng thật HOẶC SP/View khác trong cùng DB
        filtered_uses = {
            t for t in parsed["uses"]
            if t.upper() in real_tables or t.upper() in obj_names_upper
        }
        filtered_creates = {
            t for t in parsed["creates"]
            if t.upper() in real_tables
        }

        file_data[obj_name] = {
            "creates":   filtered_creates,
            "uses":      filtered_uses,
            "node_type": ntype,
        }

        for tbl in filtered_creates:
            all_tables[tbl]["created_by"].append(obj_name)
        for tbl in filtered_uses:
            # Nếu tbl là SP/View khác thì node_type = object type của nó
            ttype = "table" if tbl.upper() in real_tables else "procedure"
            all_tables[tbl]["node_type"] = ttype
            all_tables[tbl]["used_by"].append(obj_name)

    return {"files": file_data, "tables": dict(all_tables)}
