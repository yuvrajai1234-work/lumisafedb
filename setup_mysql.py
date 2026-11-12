#!/usr/bin/env python3
"""
LumiSafe MySQL Setup & Verification Utility
Connects to MySQL Server and initializes LumiSafeDB with full schema, triggers, and seed data.
"""

import sys
import argparse
from pathlib import Path
import pymysql

BASE_DIR = Path(__file__).resolve().parent

def main():
    parser = argparse.ArgumentParser(description="Initialize LumiSafeDB on MySQL Server.")
    parser.add_argument("--host", default="127.0.0.1", help="MySQL Server host (default: 127.0.0.1)")
    parser.add_argument("--port", type=int, default=3306, help="MySQL Server port (default: 3306)")
    parser.add_argument("--user", default="root", help="MySQL User (default: root)")
    parser.add_argument("--password", default="", help="MySQL root password")
    parser.add_argument("--db", default="LumiSafeDB", help="Database name (default: LumiSafeDB)")
    parser.add_argument("--schema", default=str(BASE_DIR / "lumisafe_schema.sql"), help="Path to schema SQL file")

    args = parser.parse_args()

    # If password is not provided via argument, prompt for it if standard terminal
    pwd = args.password
    if not pwd and sys.stdin.isatty():
        import getpass
        pwd = getpass.getpass(f"Enter MySQL password for {args.user}@{args.host} (press Enter if none): ")

    print(f"\n=======================================================")
    print(f"  LumiSafe: Connecting to MySQL at {args.host}:{args.port}")
    print(f"  User: {args.user} | Target DB: {args.db}")
    print(f"=======================================================\n")

    try:
        conn = pymysql.connect(
            host=args.host,
            port=args.port,
            user=args.user,
            password=pwd,
            charset="utf8mb4",
            autocommit=True
        )
        print("✓ Connected to MySQL Server successfully.")
    except Exception as e:
        print(f"✗ Failed to connect to MySQL: {e}")
        print("\nPlease check that MySQL Server is running and your credentials are correct.")
        sys.exit(1)

    schema_file = Path(args.schema)
    if not schema_file.exists():
        print(f"✗ Schema file not found: {schema_file}")
        sys.exit(1)

    print(f"-> Reading schema file: {schema_file.name}...")
    with open(schema_file, "r", encoding="utf-8") as f:
        content = f.read()

    with conn.cursor() as cur:
        print(f"-> Creating database `{args.db}`...")
        cur.execute(f"CREATE DATABASE IF NOT EXISTS `{args.db}` CHARACTER SET utf8mb4;")
        cur.execute(f"USE `{args.db}`;")

        # Parsing statements respecting DELIMITER $$
        statements = []
        current_delimiter = ';'
        current_stmt = []

        for line in content.splitlines():
            stripped = line.strip()
            if stripped.upper().startswith('DELIMITER'):
                parts = stripped.split()
                if len(parts) >= 2:
                    current_delimiter = parts[1]
                continue

            if not stripped or stripped.startswith('--') or stripped.startswith('#'):
                continue

            current_stmt.append(line)

            if current_delimiter == ';' and stripped.endswith(';'):
                stmt = '\n'.join(current_stmt).strip()
                if stmt:
                    statements.append(stmt)
                current_stmt = []
            elif current_delimiter != ';' and stripped.endswith(current_delimiter):
                stmt = '\n'.join(current_stmt).rstrip(current_delimiter).strip()
                if stmt:
                    statements.append(stmt)
                current_stmt = []

        print(f"-> Executing {len(statements)} SQL commands (tables, triggers, procedures, data)...")
        executed = 0
        for stmt in statements:
            stmt_clean = stmt.strip()
            if stmt_clean and not stmt_clean.upper().startswith("USE "):
                try:
                    cur.execute(stmt_clean)
                    executed += 1
                except Exception as err:
                    print(f"   [Warning] {err} in: {stmt_clean[:50]}...")

        print(f"✓ Executed {executed} SQL statements.")

        # Verification
        print("\n--- Verifying Created Tables in LumiSafeDB ---")
        cur.execute("SHOW TABLES;")
        tables = [row[0] for row in cur.fetchall()]
        for t in tables:
            cur.execute(f"SELECT COUNT(*) FROM `{t}`;")
            count = cur.fetchone()[0]
            print(f"   • {t:<22} ({count} rows)")

        print("\n--- Verifying Triggers ---")
        cur.execute("SHOW TRIGGERS;")
        triggers = [row[0] for row in cur.fetchall()]
        for tr in triggers:
            print(f"   • Trigger: {tr}")

    conn.close()
    print("\n=======================================================")
    print("  Setup Completed Successfully!")
    print(f"  Now open MySQL Workbench, connect to {args.host}:{args.port}")
    print(f"  and expand `{args.db}` in SCHEMAS to see all your tables.")
    print("=======================================================\n")

if __name__ == "__main__":
    main()

