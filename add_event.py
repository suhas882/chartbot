"""
Administrative Utility to add a new event into the relational database 'data/events.db'.
Automatically handles relational foreign keys across:
- events
- event_locations
- event_schedules
- tickets
- seats
- availability
- event_urls
"""

import sqlite3
import argparse
import json
import sys
from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

from app.config import DATA_DIR

DB_PATH = DATA_DIR / "events.db"

def add_new_event(
    name: str,
    category: str,
    description: str,
    organizer: str,
    venue_name: str,
    city: str,
    state: str,
    address: str,
    event_date: str,               # YYYY-MM-DD
    start_time: str = "09:00 AM",
    end_time: str = "05:00 PM",
    doors_open: str = "08:00 AM",
    capacity: int = 5000,
    ticket_tiers: Optional[List[Dict[str, Any]]] = None,
    booking_url: Optional[str] = None,
    official_url: Optional[str] = None,
    seat_prefix: Optional[str] = None
) -> Dict[str, Any]:
    """
    Inserts a complete event with venue, schedule, tickets, seats, availability, and URLs.
    """
    if not DB_PATH.exists():
        raise FileNotFoundError(f"Database not found at {DB_PATH}. Run 'python init_event_db.py' first.")

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    try:
        # 1. Insert into events
        cursor.execute("""
            INSERT INTO events (name, category, description, organizer, internal_production_cost, profit_margin_target, organizer_bank_account)
            VALUES (?, ?, ?, ?, 50000.0, 0.35, 'ADMIN-AUTO-SEEDED')
        """, (name, category, description, organizer))
        event_id = cursor.lastrowid

        # 2. Check if location exists or create new
        cursor.execute("SELECT location_id FROM event_locations WHERE venue_name = ? AND city = ?", (venue_name, city))
        loc_row = cursor.fetchone()
        if loc_row:
            location_id = loc_row[0]
        else:
            cursor.execute("""
                INSERT INTO event_locations (venue_name, address, city, state, postal_code, capacity, venue_security_alarm_code, manager_private_phone)
                VALUES (?, ?, ?, ?, '00000', ?, 'SEC-GEN-AUTO', '+1-800-555-0100')
            """, (venue_name, address, city, state, capacity))
            location_id = cursor.lastrowid

        # 3. Insert into event_schedules
        cursor.execute("""
            INSERT INTO event_schedules (event_id, location_id, event_date, start_time, end_time, doors_open, status)
            VALUES (?, ?, ?, ?, ?, ?, 'SCHEDULED')
        """, (event_id, location_id, event_date, start_time, end_time, doors_open))
        schedule_id = cursor.lastrowid

        # Default ticket tiers if none provided
        if not ticket_tiers:
            ticket_tiers = [
                {"tier_name": "General Admission", "price": 49.99, "allocated": 300, "perks": "Standard event access"},
                {"tier_name": "VIP Premium Pass", "price": 149.99, "allocated": 50, "perks": "Front row access, lounge access"}
            ]

        # Clean prefix for seat generation
        if not seat_prefix:
            seat_prefix = "".join([w[0].upper() for w in name.split()[:2]]) or "EV"

        seat_count = 0
        total_tickets_added = len(ticket_tiers)

        for t in ticket_tiers:
            tier_name = t.get("tier_name", "General Admission")
            price = float(t.get("price", 50.0))
            allocated = int(t.get("allocated", 100))
            perks = t.get("perks", "Full access")
            
            # 4. Insert into tickets
            cursor.execute("""
                INSERT INTO tickets (schedule_id, tier_name, price, currency, perks, internal_markup_rate, merchant_fee_cut)
                VALUES (?, ?, ?, 'USD', ?, 0.12, 0.03)
            """, (schedule_id, tier_name, price, perks))
            ticket_id = cursor.lastrowid

            # 5. Insert into availability
            sold = int(allocated * 0.25) # Simulate 25% initial booking
            available = allocated - sold
            status = "AVAILABLE" if available > 10 else "LIMITED"
            cursor.execute("""
                INSERT INTO availability (schedule_id, ticket_id, total_allocated, tickets_sold, tickets_available, status, last_updated, reserve_override_pin, broker_allocation_ratio)
                VALUES (?, ?, ?, ?, ?, ?, ?, 'PIN-AUTO', 0.05)
            """, (schedule_id, ticket_id, allocated, sold, available, status, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))

            # 6. Generate Seats for this tier (generate sample 10 seats per tier for demonstration)
            sample_seats = min(allocated, 10)
            for s in range(1, sample_seats + 1):
                seat_code = f"{seat_prefix}-{tier_name[:3].upper()}-{s:02d}"
                cursor.execute("""
                    INSERT INTO seats (location_id, schedule_id, seat_code, section, row_num, seat_number, tier_name, is_accessible)
                    VALUES (?, ?, ?, ?, 'Row-A', ?, ?, 0)
                """, (location_id, schedule_id, seat_code, f"{tier_name} Section", s, tier_name))
                seat_count += 1

        # 7. Insert Event URLs
        slug = name.lower().replace(" ", "-").replace("&", "and")
        if not booking_url:
            booking_url = f"https://events.example.com/{slug}/tickets"
        if not official_url:
            official_url = f"https://events.example.com/{slug}"

        cursor.execute("""
            INSERT INTO event_urls (event_id, schedule_id, url_type, url, label)
            VALUES (?, ?, 'ticket_booking', ?, ?)
        """, (event_id, schedule_id, booking_url, f"Book {name} Tickets"))

        cursor.execute("""
            INSERT INTO event_urls (event_id, schedule_id, url_type, url, label)
            VALUES (?, ?, 'official_site', ?, ?)
        """, (event_id, schedule_id, official_url, f"Official {name} Website"))

        conn.commit()

        return {
            "success": True,
            "event_id": event_id,
            "name": name,
            "category": category,
            "venue": f"{venue_name}, {city}, {state}",
            "date": event_date,
            "schedule_id": schedule_id,
            "ticket_tiers_count": total_tickets_added,
            "sample_seats_generated": seat_count,
            "booking_url": booking_url
        }

    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()

def interactive_mode():
    print("=" * 60)
    print(" 🎟️  EVENT PROVISIONING WIZARD")
    print("=" * 60)
    name = input("Event Name (e.g., Quantum Computing Expo 2026): ").strip()
    if not name:
        print("Event name is required.")
        return
    category = input("Category (Technology, Music, Science, Business): ").strip() or "Technology"
    description = input("Description: ").strip() or f"Annual conference for {name}."
    organizer = input("Organizer: ").strip() or "Global Event Systems"
    venue_name = input("Venue Name (e.g., Seattle Convention Center): ").strip() or "Metro Convention Hall"
    city = input("City (e.g., Seattle): ").strip() or "Seattle"
    state = input("State (e.g., WA): ").strip() or "WA"
    address = input("Address: ").strip() or "1000 Convention Blvd"
    event_date = input("Event Date (YYYY-MM-DD, e.g., 2026-12-10): ").strip() or "2026-12-10"
    start_time = input("Start Time (default 09:00 AM): ").strip() or "09:00 AM"
    end_time = input("End Time (default 05:00 PM): ").strip() or "05:00 PM"
    
    print("\nAdding default ticket tiers ($69 Standard, $199 VIP)...")
    res = add_new_event(
        name=name,
        category=category,
        description=description,
        organizer=organizer,
        venue_name=venue_name,
        city=city,
        state=state,
        address=address,
        event_date=event_date,
        start_time=start_time,
        end_time=end_time
    )
    print("\n✅ Event successfully added to database!")
    print(json.dumps(res, indent=2))

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Add new events into Chartbot relational database")
    parser.add_argument("--interactive", action="store_true", help="Launch interactive CLI wizard")
    parser.add_argument("--sample", action="store_true", help="Add a sample event for testing")
    parser.add_argument("--file", type=str, help="Load event from JSON file")

    args = parser.parse_args()

    if args.interactive:
        interactive_mode()
    elif args.file:
        with open(args.file, "r", encoding="utf-8") as f:
            data = json.load(f)
        res = add_new_event(**data)
        print("✅ Added event from JSON:")
        print(json.dumps(res, indent=2))
    elif args.sample:
        print("Inserting sample event: 'Quantum Computing Expo 2026'...")
        res = add_new_event(
            name="Quantum Computing World Expo 2026",
            category="Technology",
            description="Leading summit on quantum processors, superconducting qubits, and cryptographic quantum resilience.",
            organizer="Quantum Frontiers Institute",
            venue_name="Seattle Convention Center",
            city="Seattle",
            state="WA",
            address="705 Pike St",
            event_date="2026-12-12",
            start_time="09:00 AM",
            end_time="05:30 PM",
            ticket_tiers=[
                {"tier_name": "Full Access Pass", "price": 549.00, "allocated": 400, "perks": "All keynotes, quantum lab workshops"},
                {"tier_name": "Student / Academic Pass", "price": 129.00, "allocated": 100, "perks": "Student poster sessions & keynotes"}
            ],
            seat_prefix="QC"
        )
        print("✅ Sample event added:")
        print(json.dumps(res, indent=2))
    else:
        parser.print_help()
