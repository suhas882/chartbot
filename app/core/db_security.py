"""
Database Security & Access Control Engine.
Enforces strict table and column-level whitelisting at the backend layer.
Guarantees the AI chatbot cannot access restricted tables, sensitive columns,
or execute mutating/destructive SQL commands.
"""

import re
import sqlite3
from typing import Dict, Any, List, Set, Tuple, Optional
from pathlib import Path

class SecurityAccessDeniedError(Exception):
    """Raised when a query attempts to access restricted tables, columns, or commands."""
    def __init__(self, reason: str, violations: Optional[List[str]] = None):
        super().__init__(reason)
        self.reason = reason
        self.violations = violations or []

class DatabaseSecurityEngine:
    """
    Backend access control governor.
    Enforces least-privilege query execution on the relational database.
    """

    # Whitelist of tables the chatbot is permitted to query
    ALLOWED_TABLES: Dict[str, Set[str]] = {
        "events": {
            "event_id", "name", "category", "description", "organizer"
        },
        "event_locations": {
            "location_id", "venue_name", "address", "city", "state", "country", "postal_code", "capacity"
        },
        "event_schedules": {
            "schedule_id", "event_id", "location_id", "event_date", "start_time", "end_time", "doors_open", "status"
        },
        "tickets": {
            "ticket_id", "schedule_id", "tier_name", "price", "currency", "perks"
        },
        "seats": {
            "seat_id", "location_id", "schedule_id", "seat_code", "section", "row_num", "seat_number", "tier_name", "is_accessible"
        },
        "availability": {
            "availability_id", "schedule_id", "ticket_id", "total_allocated", "tickets_sold", "tickets_available", "status", "last_updated"
        },
        "event_urls": {
            "url_id", "event_id", "schedule_id", "url_type", "url", "label"
        }
    }

    # Explicit restricted tables (Chatbot has zero access)
    FORBIDDEN_TABLES: Set[str] = {
        "customer_bookings",
        "financial_transactions",
        "admin_credentials",
        "internal_audit_records",
        "payment_logs",
        "user_passwords",
        "sqlite_master",
        "sqlite_sequence",
        "sqlite_stat1"
    }

    # Explicit restricted columns (Chatbot has zero access even if querying whitelisted tables)
    FORBIDDEN_COLUMNS: Set[str] = {
        # Financial & pricing internals
        "internal_production_cost",
        "profit_margin_target",
        "organizer_bank_account",
        "internal_markup_rate",
        "merchant_fee_cut",
        "revenue",
        "net_profit",
        "bank_wire_routing",
        # Security & physical venue secrets
        "venue_security_alarm_code",
        "manager_private_phone",
        "vip_security_notes",
        "escort_officer_id",
        "reserve_override_pin",
        "broker_allocation_ratio",
        # PII & Credentials
        "customer_name",
        "customer_email",
        "credit_card_hash",
        "card_number",
        "cvv",
        "password_hash",
        "api_secret_key",
        "server_secret_key"
    }

    # Prohibited SQL keywords / mutating statements
    PROHIBITED_COMMANDS: Set[str] = {
        "INSERT", "UPDATE", "DELETE", "DROP", "ALTER", "CREATE",
        "TRUNCATE", "REPLACE", "ATTACH", "DETACH", "PRAGMA",
        "REINDEX", "VACUUM", "GRANT", "REVOKE", "EXEC", "EXECUTE"
    }

    @classmethod
    def inspect_and_validate_sql(cls, sql_query: str) -> Dict[str, Any]:
        """
        Validates SQL against access control rules:
        1. Must be a single SELECT statement.
        2. Prohibits mutating keywords, multiple semicolon queries, and comment tricks.
        3. Checks all referenced tables against ALLOWED_TABLES whitelist.
        4. Checks that no FORBIDDEN_TABLES or FORBIDDEN_COLUMNS are accessed.
        5. Returns parsed metadata about allowed tables and columns.
        """
        clean_sql = sql_query.strip()
        violations: List[str] = []

        # 1. Reject multiple statements (SQL injection chain)
        # Strip trailing semicolon if present
        if clean_sql.endswith(";"):
            clean_sql = clean_sql[:-1].strip()
        if ";" in clean_sql:
            violations.append("Multiple statements separated by ';' are strictly prohibited.")

        # 2. Reject comment-based SQL injections (-- or /* */)
        if "--" in clean_sql or "/*" in clean_sql:
            violations.append("SQL comments ('--' or '/*') are prohibited for security audit reasons.")

        # 3. Must begin with SELECT
        tokens = clean_sql.split()
        if not tokens or tokens[0].upper() not in ["SELECT", "WITH"]:
            violations.append(f"Only read-only SELECT queries are permitted. Detected: '{tokens[0] if tokens else 'EMPTY'}'")

        # 4. Check for prohibited commands anywhere in query
        upper_query = clean_sql.upper()
        for cmd in cls.PROHIBITED_COMMANDS:
            # Match whole-word keyword
            if re.search(r'\b' + cmd + r'\b', upper_query):
                violations.append(f"Prohibited command '{cmd}' detected in query.")

        # 5. Check for forbidden tables
        tables_found: Set[str] = set()
        for forbidden_table in cls.FORBIDDEN_TABLES:
            if re.search(r'\b' + re.escape(forbidden_table) + r'\b', clean_sql, re.IGNORECASE):
                violations.append(f"Access Denied: Table '{forbidden_table}' is restricted by backend access control.")

        # 6. Check for forbidden columns
        for forbidden_col in cls.FORBIDDEN_COLUMNS:
            if re.search(r'\b' + re.escape(forbidden_col) + r'\b', clean_sql, re.IGNORECASE):
                violations.append(f"Access Denied: Column '{forbidden_col}' is restricted by backend data privacy policy.")

        # 7. Identify referenced allowed tables
        for allowed_table in cls.ALLOWED_TABLES:
            if re.search(r'\b' + re.escape(allowed_table) + r'\b', clean_sql, re.IGNORECASE):
                tables_found.add(allowed_table)

        # 8. Check if any unknown tables are referenced in FROM / JOIN
        # Regex to find words following FROM or JOIN
        from_join_matches = re.findall(r'(?:FROM|JOIN)\s+([a-zA-Z0-9_]+)', clean_sql, re.IGNORECASE)
        for tbl in from_join_matches:
            tbl_clean = tbl.lower()
            if tbl_clean not in cls.ALLOWED_TABLES:
                violations.append(f"Access Denied: Table '{tbl}' is not in the authorized query whitelist.")

        if violations:
            raise SecurityAccessDeniedError(
                reason="Backend Database Security Policy Violation",
                violations=violations
            )

        # 9. Ensure safe LIMIT is appended if not present
        if not re.search(r'\bLIMIT\b', upper_query):
            clean_sql += " LIMIT 25"

        return {
            "status": "APPROVED",
            "sanitized_sql": clean_sql,
            "tables_accessed": list(tables_found),
            "columns_permitted": [col for tbl in tables_found for col in cls.ALLOWED_TABLES.get(tbl, set())]
        }

    @classmethod
    def execute_safe_query(cls, db_path: Path, sql_query: str) -> Dict[str, Any]:
        """
        Executes a validated query in read-only mode and returns structured results.
        Enforces backend permissions before query touches the database.
        """
        if not db_path.exists():
            raise FileNotFoundError(f"Database file not found at {db_path}")

        # Step 1: Backend Inspection & Policy Validation
        inspection = cls.inspect_and_validate_sql(sql_query)
        sanitized_sql = inspection["sanitized_sql"]

        # Step 2: Open SQLite connection in Read-Only URI mode
        uri = f"file:{db_path.resolve().as_posix()}?mode=ro"
        conn = sqlite3.connect(uri, uri=True, timeout=5.0)
        conn.row_factory = sqlite3.Row

        denied_reads: List[str] = []

        def authorize(action: int, arg1: Optional[str], arg2: Optional[str], _database: Optional[str], _source: Optional[str]) -> int:
            if action == sqlite3.SQLITE_SELECT or action == getattr(sqlite3, "SQLITE_RECURSIVE", -1):
                return sqlite3.SQLITE_OK
            if action == sqlite3.SQLITE_READ:
                table = (arg1 or "").lower()
                column = (arg2 or "").lower()
                allowed_columns = cls.ALLOWED_TABLES.get(table)
                if allowed_columns is None:
                    denied_reads.append(f"Table '{table}' is not in the authorized query whitelist.")
                    return sqlite3.SQLITE_DENY
                if column and column not in allowed_columns:
                    denied_reads.append(f"Column '{table}.{column}' is not in the authorized query whitelist.")
                    return sqlite3.SQLITE_DENY
                return sqlite3.SQLITE_OK
            if action == sqlite3.SQLITE_FUNCTION:
                function_name = (arg2 or arg1 or "").lower()
                safe_functions = {
                    "count", "min", "max", "sum", "avg", "lower", "upper", "coalesce",
                    "ifnull", "nullif", "length", "date", "time", "datetime", "strftime",
                    "substr", "trim", "ltrim", "rtrim", "replace", "abs", "round", "like",
                }
                if function_name in safe_functions:
                    return sqlite3.SQLITE_OK
                denied_reads.append(f"Function '{function_name}' is not permitted.")
                return sqlite3.SQLITE_DENY
            return sqlite3.SQLITE_DENY

        try:
            cursor = conn.cursor()
            conn.set_authorizer(authorize)
            cursor.execute(sanitized_sql)
            rows = cursor.fetchall()
            
            # Convert rows to dicts
            results = []
            columns_retrieved = []
            if rows:
                columns_retrieved = list(rows[0].keys())
                for r in rows:
                    results.append(dict(r))

            return {
                "status": "SUCCESS",
                "sql_executed": sanitized_sql,
                "tables_accessed": inspection["tables_accessed"],
                "columns_retrieved": columns_retrieved,
                "row_count": len(results),
                "data": results,
                "policy_enforcement": "PASSED (Backend Whitelist Enforced)"
            }
        except sqlite3.DatabaseError as exc:
            if denied_reads:
                raise SecurityAccessDeniedError(
                    reason="Backend Database Security Policy Violation",
                    violations=denied_reads,
                ) from exc
            raise
        finally:
            conn.close()
