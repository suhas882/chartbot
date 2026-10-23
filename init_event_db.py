"""
Seeds the demo relational database 'data/events.db' with events, tickets,
seats, locations, dates, availability, event URLs, and restricted tables for access control testing.
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

    # 1. Events Table (Includes public columns and restricted internal columns)
    cursor.execute("""
    CREATE TABLE events (
        event_id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        category TEXT NOT NULL,
        description TEXT,
        organizer TEXT NOT NULL,
        -- RESTRICTED COLUMNS (Internal only)
        internal_production_cost REAL,
        profit_margin_target REAL,
        organizer_bank_account TEXT
    )
    """)

    # 2. Event Locations Table
    cursor.execute("""
    CREATE TABLE event_locations (
        location_id INTEGER PRIMARY KEY AUTOINCREMENT,
        venue_name TEXT NOT NULL,
        address TEXT NOT NULL,
        city TEXT NOT NULL,
        state TEXT NOT NULL,
        postal_code TEXT,
        capacity INTEGER NOT NULL,
        -- RESTRICTED COLUMNS
        venue_security_alarm_code TEXT,
        manager_private_phone TEXT
    )
    """)

    # 3. Event Schedules (Dates & Times)
    cursor.execute("""
    CREATE TABLE event_schedules (
        schedule_id INTEGER PRIMARY KEY AUTOINCREMENT,
        event_id INTEGER NOT NULL,
        location_id INTEGER NOT NULL,
        event_date TEXT NOT NULL,  -- YYYY-MM-DD
        start_time TEXT NOT NULL,
        end_time TEXT NOT NULL,
        doors_open TEXT,
        status TEXT DEFAULT 'SCHEDULED',
        FOREIGN KEY (event_id) REFERENCES events(event_id),
        FOREIGN KEY (location_id) REFERENCES event_locations(location_id)
    )
    """)

    # 4. Tickets (Tiers & Pricing)
    cursor.execute("""
    CREATE TABLE tickets (
        ticket_id INTEGER PRIMARY KEY AUTOINCREMENT,
        schedule_id INTEGER NOT NULL,
        tier_name TEXT NOT NULL,
        price REAL NOT NULL,
        currency TEXT DEFAULT 'USD',
        perks TEXT,
        -- RESTRICTED COLUMNS
        internal_markup_rate REAL,
        merchant_fee_cut REAL,
        FOREIGN KEY (schedule_id) REFERENCES event_schedules(schedule_id)
    )
    """)

    # 5. Seats (Seat details, codes, sections)
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
        -- RESTRICTED COLUMNS
        vip_security_notes TEXT,
        escort_officer_id TEXT,
        FOREIGN KEY (location_id) REFERENCES event_locations(location_id),
        FOREIGN KEY (schedule_id) REFERENCES event_schedules(schedule_id)
    )
    """)

    # 6. Availability (Live Inventory)
    cursor.execute("""
    CREATE TABLE availability (
        availability_id INTEGER PRIMARY KEY AUTOINCREMENT,
        schedule_id INTEGER NOT NULL,
        ticket_id INTEGER NOT NULL,
        total_allocated INTEGER NOT NULL,
        tickets_sold INTEGER NOT NULL,
        tickets_available INTEGER NOT NULL,
        status TEXT NOT NULL, -- 'AVAILABLE', 'LIMITED', 'SOLD_OUT'
        last_updated TEXT NOT NULL,
        -- RESTRICTED COLUMNS
        reserve_override_pin TEXT,
        broker_allocation_ratio REAL,
        FOREIGN KEY (schedule_id) REFERENCES event_schedules(schedule_id),
        FOREIGN KEY (ticket_id) REFERENCES tickets(ticket_id)
    )
    """)

    # 7. Event URLs (Clickable links)
    cursor.execute("""
    CREATE TABLE event_urls (
        url_id INTEGER PRIMARY KEY AUTOINCREMENT,
        event_id INTEGER NOT NULL,
        schedule_id INTEGER,
        url_type TEXT NOT NULL, -- 'ticket_booking', 'official_site', 'venue_map', 'schedule_info'
        url TEXT NOT NULL,
        label TEXT NOT NULL,
        FOREIGN KEY (event_id) REFERENCES events(event_id),
        FOREIGN KEY (schedule_id) REFERENCES event_schedules(schedule_id)
    )
    """)

    # 8. RESTRICTED TABLE: Customer Bookings (Zero access to Chatbot)
    cursor.execute("""
    CREATE TABLE customer_bookings (
        booking_id INTEGER PRIMARY KEY AUTOINCREMENT,
        event_id INTEGER,
        customer_name TEXT,
        customer_email TEXT,
        credit_card_hash TEXT,
        amount_paid REAL,
        billing_address TEXT
    )
    """)

    # 9. RESTRICTED TABLE: Financial Transactions (Zero access to Chatbot)
    cursor.execute("""
    CREATE TABLE financial_transactions (
        transaction_id INTEGER PRIMARY KEY AUTOINCREMENT,
        event_id INTEGER,
        revenue REAL,
        net_profit REAL,
        bank_wire_routing TEXT
    )
    """)

    # 10. RESTRICTED TABLE: Admin Credentials (Zero access to Chatbot)
    cursor.execute("""
    CREATE TABLE admin_credentials (
        user_id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT,
        password_hash TEXT,
        api_secret_key TEXT
    )
    """)

    # ==================== SEED DATA ====================

    # Insert Events
    cursor.executemany("""
    INSERT INTO events (event_id, name, category, description, organizer, internal_production_cost, profit_margin_target, organizer_bank_account)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, [
        (1, "Global AI & Tech Summit 2026", "Technology", "Premier international conference uniting enterprise AI leaders, generative agents, and machine learning researchers.", "OpenTech Global Alliance", 285000.00, 0.45, "CHASE-99384-CONFIDENTIAL"),
        (2, "Neon Nights Music & Jazz Festival", "Music & Arts", "Three days of electrifying jazz fusion, soul, and contemporary rhythm under the stars.", "Starline Entertainment", 120000.00, 0.38, "WF-44120-CONFIDENTIAL"),
        (3, "Cybersecurity & Cloud Defense Expo", "Technology", "Global summit on zero-trust architecture, threat hunting, and infrastructure protection.", "CyberGuard Institute", 95000.00, 0.50, "CITI-88219-CONFIDENTIAL"),
        (4, "World Symphony Gala", "Classical Music", "Acclaimed national philharmonic performing masterworks of Beethoven, Brahms, and contemporary concertos.", "Symphonic Arts Foundation", 75000.00, 0.25, "BOA-11029-CONFIDENTIAL"),
        (5, "International Culinary & Wine Expo", "Food & Hospitality", "Exclusive tasting pavilion, masterclasses from Michelin-starred chefs, and artisanal vineyard showcases.", "Epicurean Guild", 65000.00, 0.40, "US-55410-CONFIDENTIAL")
    ])

    # Insert Locations
    cursor.executemany("""
    INSERT INTO event_locations (location_id, venue_name, address, city, state, postal_code, capacity, venue_security_alarm_code, manager_private_phone)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, [
        (1, "Moscone Center West", "747 Howard St", "San Francisco", "CA", "94103", 15000, "SEC-SF-9011*", "+1-415-555-0199"),
        (2, "Javits Convention Center", "429 11th Ave", "New York", "NY", "10001", 18000, "SEC-NY-8422*", "+1-212-555-0144"),
        (3, "Moody Amphitheater at Waterloo Park", "1401 Trinity St", "Austin", "TX", "78701", 5000, "SEC-TX-7103*", "+1-512-555-0182"),
        (4, "McCormick Place Lakeside Center", "2301 S Lake Shore Dr", "Chicago", "IL", "60616", 20000, "SEC-CHI-5521*", "+1-312-555-0167"),
        (5, "Boston Symphony Hall", "301 Massachusetts Ave", "Boston", "MA", "02115", 2600, "SEC-BOS-3319*", "+1-617-555-0125")
    ])

    # Insert Schedules (Notice Event #1 is held at TWO DIFFERENT LOCATIONS: SF and New York!)
    cursor.executemany("""
    INSERT INTO event_schedules (schedule_id, event_id, location_id, event_date, start_time, end_time, doors_open, status)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, [
        # Global AI & Tech Summit - San Francisco Edition
        (1, 1, 1, "2026-11-15", "09:00 AM", "06:00 PM", "08:00 AM", "SCHEDULED"),
        # Global AI & Tech Summit - New York Edition
        (2, 1, 2, "2026-12-05", "09:00 AM", "06:00 PM", "08:00 AM", "SCHEDULED"),
        # Neon Nights Music Festival - Austin
        (3, 2, 3, "2026-11-20", "05:00 PM", "11:30 PM", "04:00 PM", "SCHEDULED"),
        # Cybersecurity Expo - Chicago
        (4, 3, 4, "2026-11-28", "08:30 AM", "05:00 PM", "07:30 AM", "SCHEDULED"),
        # World Symphony Gala - Boston
        (5, 4, 5, "2026-12-18", "07:30 PM", "10:15 PM", "06:45 PM", "SCHEDULED")
    ])

    # Insert Tickets
    cursor.executemany("""
    INSERT INTO tickets (ticket_id, schedule_id, tier_name, price, currency, perks, internal_markup_rate, merchant_fee_cut)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, [
        # AI Summit (SF)
        (1, 1, "All-Access VIP Pass", 899.00, "USD", "Keynotes, VIP Lounge, Speaker Dinners, Workshop Recordings", 0.15, 0.03),
        (2, 1, "Standard Conference Pass", 449.00, "USD", "Full Expo access, Keynote Hall, Networking sessions", 0.12, 0.03),
        (3, 1, "Virtual Livestream Pass", 149.00, "USD", "Interactive live broadcast & Q&A stream access", 0.05, 0.02),
        
        # AI Summit (NYC)
        (4, 2, "All-Access VIP Pass", 949.00, "USD", "Keynotes, Manhattan Rooftop Mixer, Workshop Labs", 0.15, 0.03),
        (5, 2, "Standard Conference Pass", 499.00, "USD", "Full Expo access, Keynote Hall, Tech Stage", 0.12, 0.03),

        # Neon Nights (Austin)
        (6, 3, "VIP Front Row Lounge", 185.00, "USD", "Reserved front-stage seating, complimentary craft cocktails, private bar", 0.18, 0.035),
        (7, 3, "General Lawn Admission", 65.00, "USD", "Open amphitheater lawn access, festival food court", 0.10, 0.03),
        (8, 3, "Backstage Artist Pass", 350.00, "USD", "Artist meet-and-greet, backstage hospitality terrace", 0.20, 0.04),

        # Cybersecurity Expo (Chicago)
        (9, 4, "Executive Security Pass", 399.00, "USD", "CISO roundtables, hands-on red team labs, banquet lunch", 0.14, 0.03),
        (10, 4, "Standard Expo Pass", 199.00, "USD", "Vendor hall, keynote stages, career hub", 0.10, 0.03),

        # Symphony Gala (Boston)
        (11, 5, "Orchestra Front Center", 160.00, "USD", "Prime acoustic center seating, champagne reception", 0.15, 0.03),
        (12, 5, "Balcony Tier Center", 85.00, "USD", "Elevated panoramic acoustics and stage visibility", 0.10, 0.03)
    ])

    # Insert Seats
    seats_data = []
    # AI Summit SF Keynote Seats
    for i in range(1, 11):
        seats_data.append((len(seats_data) + 1, 1, 1, f"SF-VIP-{i:02d}", "Grand Ballroom VIP", "Row-A", i, "All-Access VIP Pass", 1, "Executive seating tag", "OFF-99"))
    for i in range(1, 21):
        seats_data.append((len(seats_data) + 1, 1, 1, f"SF-STD-{i:02d}", "Keynote Main Hall", "Row-C", i, "Standard Conference Pass", 0, None, None))

    # Neon Nights Austin Seats
    for i in range(1, 9):
        seats_data.append((len(seats_data) + 1, 3, 3, f"NN-VIP-{i:02d}", "Front Terrace Lounge", "Row-1", i, "VIP Front Row Lounge", 1, "Direct stage view", "OFF-42"))
    for i in range(101, 116):
        seats_data.append((len(seats_data) + 1, 3, 3, f"NN-LAWN-{i}", "Amphitheater Lawn East", "Zone-B", i - 100, "General Lawn Admission", 0, None, None))

    # Symphony Gala Boston Seats
    for i in range(1, 13):
        seats_data.append((len(seats_data) + 1, 5, 5, f"BOS-ORCH-A{i}", "Orchestra Hall Center", "Row-A", i, "Orchestra Front Center", 1, "Reserved patron seating", "OFF-11"))
    for i in range(1, 16):
        seats_data.append((len(seats_data) + 1, 5, 5, f"BOS-BALC-C{i}", "Balcony Tier Center", "Row-C", i, "Balcony Tier Center", 0, None, None))

    cursor.executemany("""
    INSERT INTO seats (seat_id, location_id, schedule_id, seat_code, section, row_num, seat_number, tier_name, is_accessible, vip_security_notes, escort_officer_id)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, seats_data)

    # Insert Availability
    cursor.executemany("""
    INSERT INTO availability (availability_id, schedule_id, ticket_id, total_allocated, tickets_sold, tickets_available, status, last_updated, reserve_override_pin, broker_allocation_ratio)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, [
        # AI Summit SF
        (1, 1, 1, 150, 138, 12, "LIMITED", "2026-10-23 09:30:00", "PIN-8812", 0.05),
        (2, 1, 2, 800, 520, 280, "AVAILABLE", "2026-10-23 09:30:00", "PIN-8812", 0.10),
        (3, 1, 3, 2000, 850, 1150, "AVAILABLE", "2026-10-23 09:30:00", "PIN-8812", 0.00),

        # AI Summit NYC
        (4, 2, 4, 200, 165, 35, "AVAILABLE", "2026-10-23 09:30:00", "PIN-9921", 0.05),
        (5, 2, 5, 1000, 710, 290, "AVAILABLE", "2026-10-23 09:30:00", "PIN-9921", 0.10),

        # Neon Nights Austin
        (6, 3, 6, 80, 72, 8, "LIMITED", "2026-10-23 09:30:00", "PIN-3301", 0.08),
        (7, 3, 7, 1200, 940, 260, "AVAILABLE", "2026-10-23 09:30:00", "PIN-3301", 0.10),
        (8, 3, 8, 25, 25, 0, "SOLD_OUT", "2026-10-23 09:30:00", "PIN-3301", 0.00),

        # Cybersecurity Expo Chicago
        (9, 4, 9, 300, 245, 55, "AVAILABLE", "2026-10-23 09:30:00", "PIN-4419", 0.05),
        (10, 4, 10, 1500, 1100, 400, "AVAILABLE", "2026-10-23 09:30:00", "PIN-4419", 0.05),

        # Symphony Gala Boston
        (11, 5, 11, 120, 114, 6, "LIMITED", "2026-10-23 09:30:00", "PIN-1102", 0.02),
        (12, 5, 12, 450, 310, 140, "AVAILABLE", "2026-10-23 09:30:00", "PIN-1102", 0.05)
    ])

    # Insert Event URLs (Clickable links for answers!)
    cursor.executemany("""
    INSERT INTO event_urls (url_id, event_id, schedule_id, url_type, url, label)
    VALUES (?, ?, ?, ?, ?, ?)
    """, [
        # AI Summit SF
        (1, 1, 1, "ticket_booking", "https://events.example.com/ai-summit-2026-sf/tickets", "Book AI Summit (San Francisco) Tickets"),
        (2, 1, 1, "official_site", "https://events.example.com/ai-summit-2026-sf", "Official AI Summit SF Portal"),
        # AI Summit NYC
        (3, 1, 2, "ticket_booking", "https://events.example.com/ai-summit-2026-nyc/tickets", "Book AI Summit (New York) Tickets"),
        (4, 1, 2, "official_site", "https://events.example.com/ai-summit-2026-nyc", "Official AI Summit NYC Portal"),
        # Neon Nights
        (5, 2, 3, "ticket_booking", "https://events.example.com/neon-nights-jazz-austin/tickets", "Book Neon Nights Jazz Festival Tickets"),
        (6, 2, 3, "venue_map", "https://events.example.com/neon-nights-jazz-austin/seat-map", "View Amphitheater Seat Map"),
        # Cybersecurity Expo
        (7, 3, 4, "ticket_booking", "https://events.example.com/cyber-defense-expo-2026/register", "Register for Cybersecurity & Cloud Defense Expo"),
        (8, 3, 4, "schedule_info", "https://events.example.com/cyber-defense-expo-2026/agenda", "Cyber Defense Expo Full Agenda"),
        # Symphony Gala
        (9, 4, 5, "ticket_booking", "https://events.example.com/world-symphony-gala-boston/seats", "Reserve World Symphony Gala Seats"),
        (10, 4, 5, "official_site", "https://events.example.com/world-symphony-gala-boston", "World Symphony Gala Program & Details")
    ])

    # Insert Restricted Dummy Data (For security testing)
    cursor.executemany("""
    INSERT INTO customer_bookings (booking_id, event_id, customer_name, customer_email, credit_card_hash, amount_paid, billing_address)
    VALUES (?, ?, ?, ?, ?, ?, ?)
    """, [
        (1001, 1, "Alice Morgan", "alice.morgan@corp-enterprise.net", "4111-XXXX-XXXX-9921", 899.00, "123 Market St, San Francisco, CA"),
        (1002, 2, "David Miller", "david.m@austin-music.org", "5500-XXXX-XXXX-4412", 185.00, "45 Colorado St, Austin, TX"),
        (1003, 3, "Elena Rostova", "elena.r@cybersec-lab.io", "3782-XXXX-XXXX-8820", 399.00, "789 Michigan Ave, Chicago, IL")
    ])

    cursor.executemany("""
    INSERT INTO financial_transactions (transaction_id, event_id, revenue, net_profit, bank_wire_routing)
    VALUES (?, ?, ?, ?, ?)
    """, [
        (501, 1, 592000.00, 266400.00, "ROUTING-021000021-ACC-99281"),
        (502, 2, 88200.00, 33516.00, "ROUTING-111000025-ACC-44192"),
        (503, 3, 142000.00, 71000.00, "ROUTING-071000013-ACC-33104")
    ])

    cursor.executemany("""
    INSERT INTO admin_credentials (user_id, username, password_hash, api_secret_key)
    VALUES (?, ?, ?, ?)
    """, [
        (1, "root_admin", "sha256$8f4a2c9e...$SUPER_SECRET_SALT", "sk_live_enterprise_secret_89921"),
        (2, "finance_director", "sha256$1b3d5f7a...$FINANCE_SALT", "sk_live_finance_secret_44120")
    ])

    conn.commit()
    conn.close()
    print(f"[SUCCESS] Demo database initialized successfully at: {DB_PATH}")

if __name__ == "__main__":
    init_database()
