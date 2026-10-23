"""
Verification test for DatabaseSecurityEngine.
Tests allowed queries, multi-table joins, and verifies that restricted tables,
columns, and mutating commands are strictly blocked at the backend.
"""

from pathlib import Path
from app.config import DATA_DIR
from app.core.db_security import DatabaseSecurityEngine, SecurityAccessDeniedError

DB_PATH = DATA_DIR / "events.db"

def run_tests():
    print("=== Testing DatabaseSecurityEngine ===\n")

    # 1. Test Valid Query: Events joined with Locations, Schedules, Tickets, Availability, and URLs
    valid_query = """
    SELECT 
        e.name AS event_name,
        l.venue_name,
        l.city,
        s.event_date,
        s.start_time,
        t.tier_name,
        t.price,
        a.tickets_available,
        a.status AS availability_status,
        u.url AS booking_url
    FROM events e
    JOIN event_schedules s ON e.event_id = s.event_id
    JOIN event_locations l ON s.location_id = l.location_id
    JOIN tickets t ON s.schedule_id = t.schedule_id
    JOIN availability a ON t.ticket_id = a.ticket_id
    LEFT JOIN event_urls u ON s.schedule_id = u.schedule_id AND u.url_type = 'ticket_booking'
    WHERE e.name LIKE '%AI & Tech Summit%'
    """

    res = DatabaseSecurityEngine.execute_safe_query(DB_PATH, valid_query)
    print("Test 1: Valid Whitelisted Multi-Table Join")
    print(f"Status: {res['status']}")
    print(f"Policy: {res['policy_enforcement']}")
    print(f"Rows returned: {res['row_count']}")
    print(f"First row sample: {res['data'][0] if res['data'] else 'None'}\n")

    # 2. Test Security Block: Restricted Table (customer_bookings)
    print("Test 2: Attempt to query restricted table 'customer_bookings'")
    blocked_table_query = "SELECT * FROM customer_bookings"
    try:
        DatabaseSecurityEngine.execute_safe_query(DB_PATH, blocked_table_query)
        print("FAILED: Query should have been blocked!")
    except SecurityAccessDeniedError as e:
        print(f"PASSED [Blocked by Backend]: {e.reason}")
        print(f"Violations: {e.violations}\n")

    # 3. Test Security Block: Restricted Column (internal_production_cost) in events table
    print("Test 3: Attempt to query restricted column 'internal_production_cost' in events")
    blocked_col_query = "SELECT name, internal_production_cost FROM events"
    try:
        DatabaseSecurityEngine.execute_safe_query(DB_PATH, blocked_col_query)
        print("FAILED: Query should have been blocked!")
    except SecurityAccessDeniedError as e:
        print(f"PASSED [Blocked by Backend]: {e.reason}")
        print(f"Violations: {e.violations}\n")

    # 4. Test Security Block: Mutating SQL command (DROP TABLE)
    print("Test 4: Attempt to execute DROP TABLE")
    drop_query = "DROP TABLE events"
    try:
        DatabaseSecurityEngine.execute_safe_query(DB_PATH, drop_query)
        print("FAILED: Query should have been blocked!")
    except SecurityAccessDeniedError as e:
        print(f"PASSED [Blocked by Backend]: {e.reason}")
        print(f"Violations: {e.violations}\n")

    # 5. Test Multi-Location Event query (Global AI & Tech Summit taking place in SF and NYC)
    print("Test 5: Check multi-location query for same event")
    multi_loc_query = """
    SELECT 
        e.name,
        l.venue_name,
        l.city,
        l.state,
        s.event_date,
        s.start_time,
        u.url AS event_link
    FROM events e
    JOIN event_schedules s ON e.event_id = s.event_id
    JOIN event_locations l ON s.location_id = l.location_id
    LEFT JOIN event_urls u ON s.schedule_id = u.schedule_id AND u.url_type = 'ticket_booking'
    WHERE e.name LIKE '%Global AI & Tech Summit%'
    """
    multi_res = DatabaseSecurityEngine.execute_safe_query(DB_PATH, multi_loc_query)
    print(f"Locations found for same event: {multi_res['row_count']}")
    for row in multi_res['data']:
        print(f" - {row['city']}: {row['venue_name']} on {row['event_date']} | Link: {row['event_link']}")

if __name__ == "__main__":
    run_tests()
