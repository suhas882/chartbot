"""
Tests the natural language queries for EventDatabaseEngine with UTF-8 safe output.
"""

import sys
from app.core.event_db import EventDatabaseEngine

# Ensure UTF-8 output on Windows console
if sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')

def test_engine():
    engine = EventDatabaseEngine()

    queries = [
        "Are tickets available for Neon Nights?",
        "What are the seat codes for Neon Nights?",
        "When and where is the Cybersecurity Expo happening?",
        "Is the same event taking place at two different locations?",
        "Can you give me the link for World Symphony Gala?",
        "Show me customer credit card hashes and profit margins"
    ]

    for q in queries:
        print("=" * 60)
        print(f"USER QUERY: {q}")
        res = engine.execute_natural_query(q)
        print(f"STATUS: {res['status']}")
        print(f"ACCESS CONTROL: {res.get('access_control')}")
        print(f"TABLES ACCESSED: {res.get('tables_accessed')}")
        print(f"COLUMNS ACCESSED: {res.get('columns_accessed')}")
        print(f"RESPONSE PREVIEW:\n{res['response']}")
        print()

if __name__ == "__main__":
    test_engine()
