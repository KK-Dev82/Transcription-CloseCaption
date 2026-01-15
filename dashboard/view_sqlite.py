#!/usr/bin/env python3
"""
Simple SQLite Viewer Script
สำหรับดูข้อมูลใน SQLite database โดยไม่ต้องติดตั้ง GUI
"""
import sqlite3
import sys
from pathlib import Path

try:
    from tabulate import tabulate
    HAS_TABULATE = True
except ImportError:
    HAS_TABULATE = False

def view_tables(db_path):
    """แสดงรายการ tables ทั้งหมด"""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = cursor.fetchall()
    
    print("\n📊 Tables in database:")
    print("=" * 50)
    for table in tables:
        print(f"  - {table[0]}")
    print()
    
    conn.close()

def view_table_data(db_path, table_name, limit=10):
    """แสดงข้อมูลใน table"""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    try:
        cursor.execute(f"SELECT * FROM {table_name} LIMIT {limit}")
        rows = cursor.fetchall()
        
        if not rows:
            print(f"❌ Table '{table_name}' is empty")
            return
        
        # Get column names
        columns = [description[0] for description in cursor.description]
        
        # Convert rows to list of lists
        data = []
        for row in rows:
            data.append([str(row[col])[:50] for col in columns])  # Truncate long values
        
        print(f"\n📋 Data from table '{table_name}' (showing {len(rows)} rows):")
        print("=" * 100)
        if HAS_TABULATE:
            print(tabulate(data, headers=columns, tablefmt="grid"))
        else:
            # Simple table format without tabulate
            col_widths = []
            for i, col in enumerate(columns):
                max_col_len = len(str(col))
                if data:
                    max_val_len = max(len(str(row[i])) for row in data)
                    max_col_len = max(max_col_len, max_val_len)
                col_widths.append(max_col_len)
            # Print header
            header = " | ".join(str(col).ljust(col_widths[i]) for i, col in enumerate(columns))
            print(header)
            print("-" * len(header))
            # Print rows
            for row in data:
                print(" | ".join(str(val).ljust(col_widths[i]) for i, val in enumerate(row)))
        print()
        
        # Show total count
        cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
        total = cursor.fetchone()[0]
        print(f"Total rows: {total}")
        print()
        
    except sqlite3.Error as e:
        print(f"❌ Error: {e}")
    finally:
        conn.close()

def view_table_schema(db_path, table_name):
    """แสดง schema ของ table"""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        cursor.execute(f"PRAGMA table_info({table_name})")
        columns = cursor.fetchall()
        
        print(f"\n📐 Schema of table '{table_name}':")
        print("=" * 80)
        if HAS_TABULATE:
            print(tabulate(columns, headers=["cid", "name", "type", "notnull", "dflt_value", "pk"], tablefmt="grid"))
        else:
            # Simple format
            print("cid | name | type | notnull | dflt_value | pk")
            print("-" * 80)
            for col in columns:
                print(" | ".join(str(c) for c in col))
        print()
        
    except sqlite3.Error as e:
        print(f"❌ Error: {e}")
    finally:
        conn.close()

def main():
    # Default database path
    db_path = Path(__file__).parent.parent / "storage" / "database.db"
    
    if len(sys.argv) > 1:
        db_path = Path(sys.argv[1])
    
    if not db_path.exists():
        print(f"❌ Database file not found: {db_path}")
        sys.exit(1)
    
    print(f"📂 Database: {db_path}")
    print(f"📏 Size: {db_path.stat().st_size / 1024 / 1024:.2f} MB")
    
    # Show tables
    view_tables(db_path)
    
    # Interactive mode
    if len(sys.argv) == 1:
        print("💡 Usage:")
        print("  python view_sqlite.py                    # Show all tables")
        print("  python view_sqlite.py <table_name>       # Show data from table")
        print("  python view_sqlite.py <table_name> schema # Show table schema")
        print()
        
        # Show first few tables
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [t[0] for t in cursor.fetchall()]
        conn.close()
        
        if tables:
            print("📋 Quick preview of first table:")
            view_table_data(db_path, tables[0], limit=5)
    else:
        table_name = sys.argv[1]
        
        if len(sys.argv) > 2 and sys.argv[2] == "schema":
            view_table_schema(db_path, table_name)
        else:
            limit = int(sys.argv[2]) if len(sys.argv) > 2 else 10
            view_table_data(db_path, table_name, limit=limit)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n👋 Goodbye!")
        sys.exit(0)
