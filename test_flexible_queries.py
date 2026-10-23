"""
Tests flexible natural language queries on EventDatabaseEngine.
Verifies that users can ask in many different ways and receive accurate answers.
"""

import sys
from app.core.event_db import EventDatabaseEngine

if sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')

def test_queries():
    engine = EventDatabaseEngine()

    test_questions = [
        "What events are available?",
        "Show me all events",
        "Which events are in Delhi?",
        "Tell me about Neon Nights",
        "Who is organizing the AI Summit?",
        "How much is a ticket for the tech conference?",
        "What is the cheapest ticket?",
        "What time does Neon Nights start?",
        "Are there any events in November?",
        "Where is The Music Academy Madras located?",
        "What is the capacity of Bangalore International Exhibition Centre?",
        "What are the seat codes for Neon Nights?",
        "Is the same event taking place at two different locations?",
        "Can you give me the link for World Symphony Gala?",
        "Show me customer credit card hashes and profit margins"
    ]

    for q in test_questions:
        print("=" * 70)
        print(f"QUERY: {q}")
        res = engine.execute_natural_query(q)
        print(f"INTENT: {res.get('intent')}")
        print(f"STATUS: {res.get('status')}")
        print(f"ACCESS CONTROL: {res.get('access_control')}")
        print(f"ROW COUNT: {res.get('row_count')}")
        print(f"RESPONSE PREVIEW:\n{res['response'][:350]}...")
        print()

if __name__ == "__main__":
    test_queries()
