"""
Seeds the demo relational database 'data/events.db' with India-based events,
    tickets, seats, locations, dates, availability, and event URLs.
"""

import sqlite3
from pathlib import Path
from app.config import DATA_DIR

DB_PATH = DATA_DIR / "events.db"


def init_database():
    if DB_PATH.exists():
        DB_PATH.unlink()

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute("""
    CREATE TABLE events (
        event_id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        category TEXT NOT NULL,
        description TEXT,
        organizer TEXT NOT NULL
    )
    """)

    cursor.execute("""
    CREATE TABLE event_locations (
        location_id INTEGER PRIMARY KEY AUTOINCREMENT,
        venue_name TEXT NOT NULL,
        address TEXT NOT NULL,
        city TEXT NOT NULL,
        state TEXT NOT NULL,
        country TEXT NOT NULL DEFAULT 'India',
        postal_code TEXT,
        capacity INTEGER NOT NULL,
        CHECK (country = 'India')
    )
    """)

    cursor.execute("""
    CREATE TABLE event_schedules (
        schedule_id INTEGER PRIMARY KEY AUTOINCREMENT,
        event_id INTEGER NOT NULL,
        location_id INTEGER NOT NULL,
        event_date TEXT NOT NULL,
        start_time TEXT NOT NULL,
        end_time TEXT NOT NULL,
        doors_open TEXT,
        status TEXT DEFAULT 'SCHEDULED',
        FOREIGN KEY (event_id) REFERENCES events(event_id),
        FOREIGN KEY (location_id) REFERENCES event_locations(location_id)
    )
    """)

    cursor.execute("""
    CREATE TABLE tickets (
        ticket_id INTEGER PRIMARY KEY AUTOINCREMENT,
        schedule_id INTEGER NOT NULL,
        tier_name TEXT NOT NULL,
        price REAL NOT NULL,
        currency TEXT DEFAULT 'INR',
        perks TEXT,
        FOREIGN KEY (schedule_id) REFERENCES event_schedules(schedule_id)
    )
    """)

    cursor.execute("""
    CREATE TABLE seats (
        seat_id INTEGER PRIMARY KEY AUTOINCREMENT,
        location_id INTEGER NOT NULL,
        schedule_id INTEGER NOT NULL,
        seat_code TEXT NOT NULL,
        section TEXT NOT NULL,
        row_num TEXT NOT NULL,
        seat_number INTEGER NOT NULL,
        tier_name TEXT NOT NULL,
        is_accessible INTEGER DEFAULT 0,
        FOREIGN KEY (location_id) REFERENCES event_locations(location_id),
        FOREIGN KEY (schedule_id) REFERENCES event_schedules(schedule_id)
    )
    """)

    cursor.execute("""
    CREATE TABLE availability (
        availability_id INTEGER PRIMARY KEY AUTOINCREMENT,
        schedule_id INTEGER NOT NULL,
        ticket_id INTEGER NOT NULL,
        total_allocated INTEGER NOT NULL,
        tickets_sold INTEGER NOT NULL,
        tickets_available INTEGER NOT NULL,
        status TEXT NOT NULL,
        last_updated TEXT NOT NULL,
        FOREIGN KEY (schedule_id) REFERENCES event_schedules(schedule_id),
        FOREIGN KEY (ticket_id) REFERENCES tickets(ticket_id)
    )
    """)

    cursor.execute("""
    CREATE TABLE event_urls (
        url_id INTEGER PRIMARY KEY AUTOINCREMENT,
        event_id INTEGER NOT NULL,
        schedule_id INTEGER,
        url_type TEXT NOT NULL,
        url TEXT NOT NULL,
        label TEXT NOT NULL,
        FOREIGN KEY (event_id) REFERENCES events(event_id),
        FOREIGN KEY (schedule_id) REFERENCES event_schedules(schedule_id)
    )
    """)

    cursor.executemany("""
    INSERT INTO events (event_id, name, category, description, organizer)
    VALUES (?, ?, ?, ?, ?)
    """, [
        (1, "Global AI & Tech Summit 2026", "Technology", "Premier conference uniting Indian enterprise AI leaders, generative agents, and machine learning researchers.", "OpenTech India Alliance"),
        (2, "Neon Nights Music & Jazz Festival", "Music & Arts", "Three days of jazz fusion, soul, and contemporary rhythm at Jio World Garden.", "Starline Entertainment India"),
        (3, "Cybersecurity & Cloud Defense Expo", "Technology", "National summit on zero-trust architecture, threat hunting, and infrastructure protection.", "CyberGuard Institute India"),
        (4, "World Symphony Gala", "Classical Music", "The Madras Philharmonic performing Beethoven, Brahms, and contemporary concertos.", "Symphonic Arts Foundation"),
        (5, "International Culinary & Wine Expo", "Food & Hospitality", "Tasting pavilion, masterclasses from Indian and international chefs, and vineyard showcases in Goa.", "Epicurean Guild India"),
    ])

    cursor.executemany("""
    INSERT INTO event_locations (location_id, venue_name, address, city, state, country, postal_code, capacity)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, [
        (1, "Bangalore International Exhibition Centre", "10th Mile, Tumkur Road, Madavara", "Bengaluru", "Karnataka", "India", "562123", 15000),
        (2, "HITEX Exhibition Centre", "Izzat Nagar, Madhapur", "Hyderabad", "Telangana", "India", "500084", 12000),
        (3, "Jio World Garden", "G Block, Bandra Kurla Complex", "Mumbai", "Maharashtra", "India", "400051", 8000),
        (4, "India Expo Centre & Mart", "Knowledge Park II, Greater Noida", "New Delhi", "Delhi", "India", "201306", 20000),
        (5, "The Music Academy Madras", "168 TTK Road, Royapettah", "Chennai", "Tamil Nadu", "India", "600014", 1600),
        (6, "Kala Academy Goa", "Campal, Panaji", "Goa", "Goa", "India", "403001", 3500),
    ])

    cursor.executemany("""
    INSERT INTO event_schedules (schedule_id, event_id, location_id, event_date, start_time, end_time, doors_open, status)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, [
        (1, 1, 1, "2026-11-15", "09:00 AM", "06:00 PM", "08:00 AM", "SCHEDULED"),
        (2, 1, 2, "2026-12-05", "09:00 AM", "06:00 PM", "08:00 AM", "SCHEDULED"),
        (3, 2, 3, "2026-11-20", "05:00 PM", "11:30 PM", "04:00 PM", "SCHEDULED"),
        (4, 3, 4, "2026-11-28", "08:30 AM", "05:00 PM", "07:30 AM", "SCHEDULED"),
        (5, 4, 5, "2026-12-18", "07:30 PM", "10:15 PM", "06:45 PM", "SCHEDULED"),
        (6, 5, 6, "2026-12-12", "11:00 AM", "08:00 PM", "10:00 AM", "SCHEDULED"),
    ])

    cursor.executemany("""
    INSERT INTO tickets (ticket_id, schedule_id, tier_name, price, currency, perks)
    VALUES (?, ?, ?, ?, ?, ?)
    """, [
        (1, 1, "All-Access VIP Pass", 74999.00, "INR", "Keynotes, VIP Lounge, Speaker Dinners, Workshop Recordings"),
        (2, 1, "Standard Conference Pass", 24999.00, "INR", "Full Expo access, Keynote Hall, Networking sessions"),
        (3, 1, "Virtual Livestream Pass", 4999.00, "INR", "Interactive live broadcast and Q&A stream access"),
        (4, 2, "All-Access VIP Pass", 69999.00, "INR", "Keynotes, Hyderabad Mixer, Workshop Labs"),
        (5, 2, "Standard Conference Pass", 22999.00, "INR", "Full Expo access, Keynote Hall, Tech Stage"),
        (6, 3, "VIP Front Row Lounge", 8999.00, "INR", "Reserved front-stage seating, complimentary beverages, private bar"),
        (7, 3, "General Lawn Admission", 2499.00, "INR", "Open garden access, festival food court"),
        (8, 3, "Backstage Artist Pass", 14999.00, "INR", "Artist meet-and-greet, backstage hospitality terrace"),
        (9, 4, "Executive Security Pass", 18999.00, "INR", "CISO roundtables, hands-on red team labs, banquet lunch"),
        (10, 4, "Standard Expo Pass", 7999.00, "INR", "Vendor hall, keynote stages, career hub"),
        (11, 5, "Orchestra Front Center", 6500.00, "INR", "Prime acoustic center seating, reception"),
        (12, 5, "Balcony Tier Center", 3200.00, "INR", "Elevated panoramic acoustics and stage visibility"),
        (13, 6, "Chef Table Experience", 12999.00, "INR", "Chef table seating, paired tastings, masterclass"),
        (14, 6, "General Tasting Pass", 3999.00, "INR", "Pavilion tastings and public demos"),
    ])

    def _seats(location_id, schedule_id, prefix, section, row, count, tier, accessible_count=2):
        rows = []
        for i in range(1, count + 1):
            rows.append((
                location_id,
                schedule_id,
                f"{prefix}-{i:02d}",
                section,
                row,
                i,
                tier,
                1 if i <= accessible_count else 0,
            ))
        return rows

    seats_data = []
    seats_data += _seats(1, 1, "BLR-VIP-A", "Grand Hall VIP", "Row-A", 10, "All-Access VIP Pass", 3)
    seats_data += _seats(1, 1, "BLR-STD-C", "Keynote Main Hall", "Row-C", 16, "Standard Conference Pass", 2)
    seats_data += _seats(2, 2, "HYD-VIP-A", "HITEX VIP Gallery", "Row-A", 10, "All-Access VIP Pass", 2)
    seats_data += _seats(2, 2, "HYD-STD-B", "HITEX Main Arena", "Row-B", 14, "Standard Conference Pass", 2)
    seats_data += _seats(3, 3, "MUM-VIP-1", "Front Terrace Lounge", "Row-1", 8, "VIP Front Row Lounge", 2)
    seats_data += _seats(3, 3, "MUM-LAWN-B", "Garden Lawn East", "Zone-B", 15, "General Lawn Admission", 1)
    seats_data += _seats(4, 4, "DEL-EXE-A", "Executive Briefing Hall", "Row-A", 12, "Executive Security Pass", 2)
    seats_data += _seats(4, 4, "DEL-STD-D", "Expo Floor Seating", "Row-D", 16, "Standard Expo Pass", 2)
    seats_data += _seats(5, 5, "CHN-ORCH-A", "Orchestra Hall Center", "Row-A", 12, "Orchestra Front Center", 3)
    seats_data += _seats(5, 5, "CHN-BALC-C", "Balcony Tier Center", "Row-C", 14, "Balcony Tier Center", 1)
    seats_data += _seats(6, 6, "GOA-CHEF-A", "Chef Table Pavilion", "Row-A", 8, "Chef Table Experience", 2)
    seats_data += _seats(6, 6, "GOA-TASTE-C", "Tasting Court", "Row-C", 16, "General Tasting Pass", 2)

    cursor.executemany("""
    INSERT INTO seats (location_id, schedule_id, seat_code, section, row_num, seat_number, tier_name, is_accessible)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, seats_data)

    cursor.executemany("""
    INSERT INTO availability (availability_id, schedule_id, ticket_id, total_allocated, tickets_sold, tickets_available, status, last_updated)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, [
        (1, 1, 1, 150, 138, 12, "LIMITED", "2026-10-23 09:30:00"),
        (2, 1, 2, 800, 520, 280, "AVAILABLE", "2026-10-23 09:30:00"),
        (3, 1, 3, 2000, 850, 1150, "AVAILABLE", "2026-10-23 09:30:00"),
        (4, 2, 4, 200, 165, 35, "AVAILABLE", "2026-10-23 09:30:00"),
        (5, 2, 5, 1000, 710, 290, "AVAILABLE", "2026-10-23 09:30:00"),
        (6, 3, 6, 80, 72, 8, "LIMITED", "2026-10-23 09:30:00"),
        (7, 3, 7, 1200, 940, 260, "AVAILABLE", "2026-10-23 09:30:00"),
        (8, 3, 8, 25, 25, 0, "SOLD_OUT", "2026-10-23 09:30:00"),
        (9, 4, 9, 300, 245, 55, "AVAILABLE", "2026-10-23 09:30:00"),
        (10, 4, 10, 1500, 1100, 400, "AVAILABLE", "2026-10-23 09:30:00"),
        (11, 5, 11, 120, 114, 6, "LIMITED", "2026-10-23 09:30:00"),
        (12, 5, 12, 450, 310, 140, "AVAILABLE", "2026-10-23 09:30:00"),
        (13, 6, 13, 40, 31, 9, "LIMITED", "2026-10-23 09:30:00"),
        (14, 6, 14, 600, 220, 380, "AVAILABLE", "2026-10-23 09:30:00"),
    ])

    cursor.executemany("""
    INSERT INTO event_urls (url_id, event_id, schedule_id, url_type, url, label)
    VALUES (?, ?, ?, ?, ?, ?)
    """, [
        (1, 1, 1, "ticket_booking", "https://events.example.com/ai-summit-2026-bengaluru/tickets", "Book AI Summit (Bengaluru) Tickets"),
        (2, 1, 1, "official_site", "https://events.example.com/ai-summit-2026-bengaluru", "Official AI Summit Bengaluru Portal"),
        (3, 1, 1, "venue_map", "https://events.example.com/ai-summit-2026-bengaluru/seat-map", "Bengaluru Seat Map"),
        (4, 1, 2, "ticket_booking", "https://events.example.com/ai-summit-2026-hyderabad/tickets", "Book AI Summit (Hyderabad) Tickets"),
        (5, 1, 2, "official_site", "https://events.example.com/ai-summit-2026-hyderabad", "Official AI Summit Hyderabad Portal"),
        (6, 1, 2, "venue_map", "https://events.example.com/ai-summit-2026-hyderabad/seat-map", "Hyderabad Seat Map"),
        (7, 2, 3, "ticket_booking", "https://events.example.com/neon-nights-jazz-mumbai/tickets", "Book Neon Nights Jazz Festival Tickets"),
        (8, 2, 3, "venue_map", "https://events.example.com/neon-nights-jazz-mumbai/seat-map", "View Jio World Garden Seat Map"),
        (9, 3, 4, "ticket_booking", "https://events.example.com/cyber-defense-expo-delhi/register", "Register for Cybersecurity & Cloud Defense Expo"),
        (10, 3, 4, "schedule_info", "https://events.example.com/cyber-defense-expo-delhi/agenda", "Cyber Defense Expo Full Agenda"),
        (11, 3, 4, "venue_map", "https://events.example.com/cyber-defense-expo-delhi/seat-map", "Delhi Expo Seat Map"),
        (12, 4, 5, "ticket_booking", "https://events.example.com/world-symphony-gala-chennai/seats", "Reserve World Symphony Gala Seats"),
        (13, 4, 5, "official_site", "https://events.example.com/world-symphony-gala-chennai", "World Symphony Gala Program & Details"),
        (14, 4, 5, "venue_map", "https://events.example.com/world-symphony-gala-chennai/seat-map", "Music Academy Seat Map"),
        (15, 5, 6, "ticket_booking", "https://events.example.com/culinary-wine-expo-goa/tickets", "Book Culinary & Wine Expo Tickets"),
        (16, 5, 6, "official_site", "https://events.example.com/culinary-wine-expo-goa", "Culinary Expo Goa Official Site"),
        (17, 5, 6, "venue_map", "https://events.example.com/culinary-wine-expo-goa/seat-map", "Goa Pavilion Seat Map"),
    ])

    conn.commit()
    cursor.execute("PRAGMA user_version = 2")
    conn.commit()
    conn.close()
    print(f"[SUCCESS] India demo database initialized at: {DB_PATH}")


def ensure_india_demo_database() -> bool:
    """Rebuild the demo DB when it is missing or does not match the current schema."""
    if DB_PATH.exists():
        conn = sqlite3.connect(DB_PATH)
        try:
            rows = conn.execute("SELECT DISTINCT country FROM event_locations").fetchall()
            countries = {str(r[0]).strip() for r in rows}
            tables = {
                row[0] for row in conn.execute(
                    "SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT GLOB 'sqlite_*'"
                )
            }
            required_tables = {
                "events", "event_locations", "event_schedules", "tickets",
                "seats", "availability", "event_urls",
            }
            expected_columns = {
                "events": {"event_id", "name", "category", "description", "organizer"},
                "event_locations": {"location_id", "venue_name", "address", "city", "state", "country", "postal_code", "capacity"},
                "event_schedules": {"schedule_id", "event_id", "location_id", "event_date", "start_time", "end_time", "doors_open", "status"},
                "tickets": {"ticket_id", "schedule_id", "tier_name", "price", "currency", "perks"},
                "seats": {"seat_id", "location_id", "schedule_id", "seat_code", "section", "row_num", "seat_number", "tier_name", "is_accessible"},
                "availability": {"availability_id", "schedule_id", "ticket_id", "total_allocated", "tickets_sold", "tickets_available", "status", "last_updated"},
                "event_urls": {"url_id", "event_id", "schedule_id", "url_type", "url", "label"},
            }
            schema_version = conn.execute("PRAGMA user_version").fetchone()[0]
            has_current_columns = all(
                {row[1] for row in conn.execute(f"PRAGMA table_info({table})")} == columns
                for table, columns in expected_columns.items()
            )
            if schema_version == 2 and tables == required_tables and has_current_columns and countries == {"India"}:
                return False
        except sqlite3.Error:
            pass
        finally:
            conn.close()
    init_database()
    return True


if __name__ == "__main__":
    init_database()
