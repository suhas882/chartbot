"""
Comprehensive Event Database Natural Language Query Engine.
Interprets ANY natural-language question regarding events, tickets, seat details,
locations, venues, dates, schedules, availability, organizers, multi-location events,
and clickable event URLs.
Enforces backend access control via DatabaseSecurityEngine.
"""

import json
import re
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
from app.config import DATA_DIR
from app.core.db_security import DatabaseSecurityEngine, SecurityAccessDeniedError

DB_PATH = DATA_DIR / "events.db"

VALID_INTENTS = {
    "SPECIFIC_DATE_EVENTS",
    "MONTH_EVENTS",
    "MULTI_LOCATION_CHECK",
    "SEAT_DETAILS",
    "EVENT_URL",
    "TICKET_AVAILABILITY",
    "LIST_ALL_EVENTS",
    "EVENT_DETAILS_INFO",
    "VENUE_LOCATION",
    "DATE_SCHEDULE",
}

INTENT_CLASSIFY_PROMPT = """You classify questions about Indian events, tickets, seats, venues, dates, and booking URLs.
Return ONLY compact JSON:
{"intent":"ONE_INTENT","event":"","city":""}
intent must be one of:
SEAT_DETAILS, TICKET_AVAILABILITY, EVENT_URL, VENUE_LOCATION, DATE_SCHEDULE,
MULTI_LOCATION_CHECK, LIST_ALL_EVENTS, EVENT_DETAILS_INFO, MONTH_EVENTS, SPECIFIC_DATE_EVENTS
event: event name from the catalog if mentioned, else empty string.
city: Indian city if mentioned, else empty string.
Do not invent events that are not in the catalog.
"""

ANSWER_SYSTEM_PROMPT = """You are Chartbot, an events assistant for India.
Use ONLY the provided database records. Do not invent events, seats, prices, or URLs.
Rules:
1. Answer in clear markdown.
2. When a record has booking_url, event_link, official_url, venue_map_url, or url, include a markdown link [label](url).
3. Format INR prices as ₹ with thousands separators.
4. If seat_code is present, list the seat codes grouped by section.
5. Locations are in India. Include city and state.
6. If records are empty, say no matching public event data was found.
"""

class EventDatabaseEngine:
    """
    Translates user questions into scoped, least-privilege SQL queries,
    runs them through the backend security engine, and produces grounded,
    actionable responses with clickable event links.
    """

    def __init__(self, db_path: Path = DB_PATH, llm_client=None):
        self.db_path = db_path
        self.llm = llm_client

    def inspect_restricted_intent(self, query: str) -> Optional[Dict[str, Any]]:
        """
        Checks if the user is asking for restricted tables or sensitive fields
        and generates a backend-enforced rejection before/during execution.
        """
        q_lower = query.lower()

        restricted_patterns = [
            ("customer bookings or personal details", r"\b(customer|customers|who booked|booking records|booking list|booked by|credit card|card number|cvv|billing address|buyer info|buyer details)\b"),
            ("internal company profit & costs", r"\b(profit margin|production cost|internal cost|net profit|company revenue|internal markup)\b"),
            ("admin credentials and security secrets", r"\b(admin password|password hash|api secret|alarm code|security pin|pin code|secret key)\b"),
            ("private contact details", r"\b(manager private phone|bank account|bank routing|wire routing)\b")
        ]

        for desc, pattern in restricted_patterns:
            if re.search(pattern, q_lower):
                return {
                    "is_restricted": True,
                    "category": desc,
                    "reason": f"Access Denied: Inquiries regarding {desc} are strictly prohibited by backend access control policy."
                }
        return None

    def _understand_with_llm(self, user_query: str) -> Dict[str, Any]:
        if not self.llm:
            return {}
        catalog = {"events": [], "cities": []}
        try:
            ev_res = DatabaseSecurityEngine.execute_safe_query(self.db_path, "SELECT name, category FROM events")
            catalog["events"] = ev_res.get("data", [])
            loc_res = DatabaseSecurityEngine.execute_safe_query(
                self.db_path, "SELECT DISTINCT city, state, venue_name FROM event_locations"
            )
            catalog["cities"] = loc_res.get("data", [])
        except Exception:
            pass

        prompt = (
            f"Event catalog: {json.dumps(catalog, ensure_ascii=True)}\n"
            f"Question: {user_query}\n"
            "JSON:"
        )
        try:
            raw = self.llm.generate(prompt, system_prompt=INTENT_CLASSIFY_PROMPT)
            match = re.search(r"\{.*\}", raw or "", re.DOTALL)
            if not match:
                return {}
            parsed = json.loads(match.group(0))
            intent = str(parsed.get("intent", "")).upper().strip()
            if intent not in VALID_INTENTS:
                return {}
            return {
                "intent": intent,
                "event": str(parsed.get("event") or "").strip(),
                "city": str(parsed.get("city") or "").strip(),
            }
        except Exception:
            return {}

    def _generate_with_llm(
        self,
        user_query: str,
        intent: str,
        records: List[Dict[str, Any]],
        fallback_text: str,
    ) -> Optional[str]:
        if not self.llm:
            return None
        safe_records = []
        for row in records[:20]:
            safe_records.append({k: v for k, v in row.items() if v is not None})
        prompt = (
            f"Intent: {intent}\n"
            f"Question: {user_query}\n"
            f"Database records JSON: {json.dumps(safe_records, ensure_ascii=True, default=str)}\n"
            "Write the user-facing answer now."
        )
        try:
            answer = (self.llm.generate(prompt, system_prompt=ANSWER_SYSTEM_PROMPT) or "").strip()
        except Exception:
            return None
        if len(answer) < 40:
            return None
        urls = {
            str(row[key])
            for row in records
            for key in ("booking_url", "event_link", "url", "official_url", "venue_map_url")
            if row.get(key)
        }
        if urls and not all(url in answer for url in urls):
            return fallback_text
        if intent == "SEAT_DETAILS" and any(str(row["seat_code"]) not in answer for row in records):
            return fallback_text
        if intent == "TICKET_AVAILABILITY" and any(
            str(row["tier_name"]) not in answer or str(row["tickets_available"]) not in answer
            for row in records
        ):
            return fallback_text
        return answer

    def execute_natural_query(self, user_query: str) -> Dict[str, Any]:
        """
        Main query entrypoint.
        Detects query topic, constructs least-privilege SQL, executes via DatabaseSecurityEngine,
        and generates response with clickable links and access transparency.
        """
        # Step 1: Pre-execution security check
        restricted_check = self.inspect_restricted_intent(user_query)
        if restricted_check:
            fake_restricted_sql = "SELECT customer_name, credit_card_hash, profit_margin_target FROM customer_bookings"
            try:
                DatabaseSecurityEngine.execute_safe_query(self.db_path, fake_restricted_sql)
            except SecurityAccessDeniedError as e:
                return {
                    "status": "SECURITY_BLOCKED",
                    "response": (
                        f"🛡️ **Access Denied by Backend Database Security Policy**\n\n"
                        f"Your request attempted to access **{restricted_check['category']}**.\n\n"
                        f"**Enforcement Details:**\n"
                        f"• Policy: `Zero-Trust Least Privilege Enforcement`\n"
                        f"• Reason: {restricted_check['reason']}\n"
                        f"• Intercepted by: `app.core.db_security.DatabaseSecurityEngine`\n\n"
                        f"The AI chatbot is granted read-only access solely to public event details, ticket availability, venue schedules, seat codes, and public booking URLs. "
                        f"Sensitive internal financials, customer PII, and credentials cannot be revealed."
                    ),
                    "sql_query": fake_restricted_sql,
                    "tables_accessed": ["customer_bookings (BLOCKED)"],
                    "columns_accessed": ["credit_card_hash (BLOCKED)", "profit_margin_target (BLOCKED)"],
                    "access_control": "DENIED (Backend Access Control Violation)",
                    "steps": [
                        "Analyzed question intent",
                        "Detected request for restricted/sensitive data",
                        "Submitted a deliberately unauthorized query to the database security engine",
                        "Security Engine raised SecurityAccessDeniedError: Table and column access blocked",
                        "Generated security refusal"
                    ],
                    "records": []
                }

        # Step 2: Llama/Ollama understands the question; SQL is still built from a whitelist planner
        q_lower = user_query.lower()
        llm_plan = self._understand_with_llm(user_query) or {}
        self._llm_plan = llm_plan
        intent, sql = self._plan_query(q_lower, user_query, llm_plan)

        # Step 3: Run safe query through DatabaseSecurityEngine
        try:
            query_result = DatabaseSecurityEngine.execute_safe_query(self.db_path, sql)
        except SecurityAccessDeniedError as e:
            return {
                "status": "SECURITY_BLOCKED",
                "response": f"🛡️ **Access Denied by Backend Database Security**: {e.reason}\n\n" + "\n".join([f"• {v}" for v in e.violations]),
                "sql_query": sql,
                "tables_accessed": [],
                "columns_accessed": [],
                "access_control": "DENIED (Backend Violation)",
                "steps": ["Parsed query", "Security policy violation detected", "Blocked execution"],
                "records": []
            }

        # Step 4: Grounded answer from live rows (Llama wording, DB facts; formatter fallback)
        response_text = self._format_response(intent, query_result["data"], user_query)
        llm_answer = self._generate_with_llm(user_query, intent, query_result["data"], response_text)
        if llm_answer:
            response_text = llm_answer

        return {
            "status": "SUCCESS",
            "intent": intent,
            "response": response_text,
            "sql_query": query_result["sql_executed"],
            "tables_accessed": query_result["tables_accessed"],
            "columns_accessed": query_result["columns_retrieved"],
            "access_control": "PASSED (Whitelisted Schema Only)",
            "row_count": query_result["row_count"],
            "records": query_result["data"],
            "steps": [
                f"Llama/Ollama understood intent: '{intent}'" if llm_plan.get("intent") else f"Keyword planner understood intent: '{intent}'",
                f"Generated scoped SQL accessing only whitelisted tables: {', '.join(query_result['tables_accessed'])}",
                "Backend security engine validated 0 restricted tables and 0 sensitive columns",
                f"Executed read-only SQLite query (Retrieved {query_result['row_count']} rows)",
                "Generated grounded answer with clickable event URLs from the database"
            ]
        }

    def _resolve_filters(self, q_lower: str) -> Dict[str, str]:
        """Dynamically extracts event name, city, month, venue, and category filters from text."""
        filters = {}

        # 1. Dynamic Event Name Filter from Database
        try:
            ev_res = DatabaseSecurityEngine.execute_safe_query(self.db_path, "SELECT event_id, name FROM events")
            db_events = ev_res.get("data", [])
        except Exception:
            db_events = []

        best_match_name = None
        highest_score = 0
        common_skip = {"expo", "summit", "festival", "gala", "world", "annual", "international", "2026", "2025", "the", "and", "for"}

        for ev in db_events:
            ev_name = ev["name"]
            ev_lower = ev_name.lower()
            
            # Exact substring match
            if ev_lower in q_lower:
                best_match_name = ev_name
                highest_score = 100
                break
            
            # Substring match without common words
            cleaned_ev_words = [w for w in re.findall(r'[a-zA-Z0-9]+', ev_lower) if w not in common_skip and len(w) >= 3]
            score = 0
            for w in cleaned_ev_words:
                if w in q_lower:
                    score += 2
            
            if score > highest_score and score >= 2:
                highest_score = score
                best_match_name = ev_name

        if best_match_name:
            safe_name = best_match_name.replace("'", "''")
            filters["event"] = f"e.name = '{safe_name}'"
        else:
            # Fallback keyword checks if DB query returned empty or didn't match
            if any(w in q_lower for w in ["ai summit", "global ai", "tech summit"]):
                filters["event"] = "e.name LIKE '%Global AI & Tech Summit%'"
            elif any(w in q_lower for w in ["neon", "jazz", "neon nights"]):
                filters["event"] = "e.name LIKE '%Neon Nights%'"
            elif any(w in q_lower for w in ["cyber", "cybersecurity", "cloud defense"]):
                filters["event"] = "e.name LIKE '%Cybersecurity%'"
            elif any(w in q_lower for w in ["symphony", "beethoven", "orchestra", "philharmonic"]):
                filters["event"] = "e.name LIKE '%World Symphony%'"
            elif any(w in q_lower for w in ["culinary", "wine", "epicurean", "tasting"]):
                filters["event"] = "e.name LIKE '%Culinary%' OR e.name LIKE '%Wine%'"

        # 2. Dynamic City Filter
        try:
            loc_res = DatabaseSecurityEngine.execute_safe_query(self.db_path, "SELECT DISTINCT city, venue_name FROM event_locations")
            db_locations = loc_res.get("data", [])
        except Exception:
            db_locations = []

        for loc in db_locations:
            city = loc.get("city")
            if city and city.lower() in q_lower:
                safe_city = city.replace("'", "''")
                filters["city"] = f"l.city LIKE '%{safe_city}%'"
                break

        # Fallback aliases for Indian cities
        if "city" not in filters:
            city_aliases = {
                "bengaluru": "Bengaluru",
                "bangalore": "Bengaluru",
                "blr": "Bengaluru",
                "hyderabad": "Hyderabad",
                "hyd": "Hyderabad",
                "mumbai": "Mumbai",
                "bombay": "Mumbai",
                "delhi": "New Delhi",
                "new delhi": "New Delhi",
                "noida": "New Delhi",
                "chennai": "Chennai",
                "madras": "Chennai",
                "goa": "Goa",
                "panaji": "Goa",
            }
            for alias, city in city_aliases.items():
                if re.search(rf"\b{re.escape(alias)}\b", q_lower):
                    filters["city"] = f"l.city LIKE '%{city}%'"
                    break

        # 3. Dynamic Venue Filter
        for loc in db_locations:
            v_name = loc.get("venue_name")
            if v_name:
                first_word = v_name.split()[0].lower()
                if len(first_word) >= 4 and first_word in q_lower:
                    safe_venue_token = v_name.split()[0].replace("'", "''")
                    filters["venue"] = f"l.venue_name LIKE '%{safe_venue_token}%'"
                    break

        # 4. Comprehensive Date & Month Resolution
        month_map = {
            "jan": ("01", "January"), "january": ("01", "January"),
            "feb": ("02", "February"), "february": ("02", "February"),
            "mar": ("03", "March"), "march": ("03", "March"),
            "apr": ("04", "April"), "april": ("04", "April"),
            "may": ("05", "May"),
            "jun": ("06", "June"), "june": ("06", "June"),
            "jul": ("07", "July"), "july": ("07", "July"),
            "aug": ("08", "August"), "august": ("08", "August"),
            "sep": ("09", "September"), "sept": ("09", "September"), "september": ("09", "September"),
            "oct": ("10", "October"), "october": ("10", "October"),
            "nov": ("11", "November"), "november": ("11", "November"),
            "dec": ("12", "December"), "december": ("12", "December")
        }

        # Pattern A: Day then Month (e.g., "25th nov", "25 november", "25th of nov", "25 nov")
        m_day_month = re.search(
            r'\b(\d{1,2})(?:st|nd|rd|th)?\s+(?:of\s+)?(jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|jul(?:y)?|aug(?:ust)?|sep(?:tember)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)\b',
            q_lower
        )

        # Pattern B: Month then Day (e.g., "nov 25th", "november 25", "nov 25")
        m_month_day = re.search(
            r'\b(jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|jul(?:y)?|aug(?:ust)?|sep(?:tember)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)\s+(\d{1,2})(?:st|nd|rd|th)?\b',
            q_lower
        )

        # Pattern C: ISO / standard date (e.g., "2026-11-25" or "11-25")
        m_iso = re.search(r'\b(?:202[4-9]-)?(\d{2})-(\d{2})\b', q_lower)

        if m_day_month:
            day_num = int(m_day_month.group(1))
            m_str = m_day_month.group(2).lower()
            m_code, m_name = month_map[m_str]
            formatted_date = f"-{m_code}-{day_num:02d}"
            filters["date"] = f"s.event_date LIKE '%{formatted_date}%'"
            filters["_parsed_date_str"] = f"{m_name} {day_num}"
            filters["_parsed_month_code"] = m_code
            filters["_parsed_month_name"] = m_name
        elif m_month_day:
            m_str = m_month_day.group(1).lower()
            day_num = int(m_month_day.group(2))
            m_code, m_name = month_map[m_str]
            formatted_date = f"-{m_code}-{day_num:02d}"
            filters["date"] = f"s.event_date LIKE '%{formatted_date}%'"
            filters["_parsed_date_str"] = f"{m_name} {day_num}"
            filters["_parsed_month_code"] = m_code
            filters["_parsed_month_name"] = m_name
        elif m_iso:
            m_code = m_iso.group(1)
            day_num = int(m_iso.group(2))
            formatted_date = f"-{m_code}-{day_num:02d}"
            filters["date"] = f"s.event_date LIKE '%{formatted_date}%'"
            filters["_parsed_date_str"] = f"Month {m_code}, Day {day_num}"
            filters["_parsed_month_code"] = m_code
        else:
            # Just Month (without specific day, e.g. "in november", "events in nov", "december schedule")
            for m_key, (m_code, m_name) in month_map.items():
                if re.search(rf'\b{m_key}\b', q_lower):
                    filters["month"] = f"s.event_date LIKE '%-{m_code}-%'"
                    filters["_parsed_month_name"] = m_name
                    filters["_parsed_month_code"] = m_code
                    break

        return filters

    def _combine_where_clauses(self, filters: Dict[str, str]) -> str:
        clauses = [v for k, v in filters.items() if not k.startswith("_")]
        if not clauses:
            return "1=1"
        return " AND ".join(clauses)

    def _apply_llm_filters(self, filters: Dict[str, str], llm_plan: Dict[str, Any]) -> Dict[str, str]:
        if not llm_plan:
            return filters
        event_hint = (llm_plan.get("event") or "").strip()
        city_hint = (llm_plan.get("city") or "").strip()
        if event_hint and "event" not in filters:
            try:
                ev_res = DatabaseSecurityEngine.execute_safe_query(self.db_path, "SELECT name FROM events")
                names = [r["name"] for r in ev_res.get("data", [])]
            except Exception:
                names = []
            hint_l = event_hint.lower()
            for name in names:
                if hint_l in name.lower() or name.lower() in hint_l:
                    safe_name = name.replace("'", "''")
                    filters["event"] = f"e.name = '{safe_name}'"
                    break
        if city_hint and "city" not in filters:
            try:
                loc_res = DatabaseSecurityEngine.execute_safe_query(
                    self.db_path, "SELECT DISTINCT city FROM event_locations"
                )
                cities = [r["city"] for r in loc_res.get("data", [])]
            except Exception:
                cities = []
            hint_l = city_hint.lower()
            for city in cities:
                if hint_l in city.lower() or city.lower() in hint_l:
                    safe_city = city.replace("'", "''")
                    filters["city"] = f"l.city LIKE '%{safe_city}%'"
                    break
        return filters

    def _plan_query(self, q_lower: str, user_query: str, llm_plan: Optional[Dict[str, Any]] = None) -> Tuple[str, str]:
        """
        Determines the exact SQL query and intent based on natural language understanding.
        SQL is never taken from the LLM; only intent and filters may be.
        """
        filters = self._resolve_filters(q_lower)
        filters = self._apply_llm_filters(filters, llm_plan or {})
        self._last_filters = filters
        where_clause = self._combine_where_clauses(filters)
        llm_intent = (llm_plan or {}).get("intent") if llm_plan else None

        def uses(intent_name: str, keywords: List[str]) -> bool:
            if llm_intent:
                return llm_intent == intent_name
            return any(w in q_lower for w in keywords)

        # 0. Specific Date Events (e.g. "any events on 25th nov", "events scheduled for nov 15", "events on 2026-11-20")
        if filters.get("date") and not any(w in q_lower for w in ["seat", "ticket", "cost", "price", "link", "url", "where"]):
            intent = "SPECIFIC_DATE_EVENTS"
            sql = f"""
            SELECT 
                e.name AS event_name,
                e.category,
                e.description,
                e.organizer,
                l.venue_name,
                l.city,
                l.state,
                l.country,
                s.event_date,
                s.start_time,
                s.end_time,
                (SELECT u.url FROM event_urls u WHERE u.event_id = e.event_id AND u.url_type = 'ticket_booking' LIMIT 1) AS booking_url
            FROM events e
            JOIN event_schedules s ON e.event_id = s.event_id
            JOIN event_locations l ON s.location_id = l.location_id
            WHERE {where_clause}
            ORDER BY s.event_date
            """
            return intent, sql

        # 0b. Month-only Events (e.g. "what events in november", "any events in dec")
        if filters.get("month") and not filters.get("event") and not any(w in q_lower for w in ["seat", "ticket", "cost", "price", "link", "url", "where"]):
            intent = "MONTH_EVENTS"
            sql = f"""
            SELECT 
                e.name AS event_name,
                e.category,
                e.description,
                e.organizer,
                l.venue_name,
                l.city,
                l.state,
                l.country,
                s.event_date,
                s.start_time,
                s.end_time,
                (SELECT u.url FROM event_urls u WHERE u.event_id = e.event_id AND u.url_type = 'ticket_booking' LIMIT 1) AS booking_url
            FROM events e
            JOIN event_schedules s ON e.event_id = s.event_id
            JOIN event_locations l ON s.location_id = l.location_id
            WHERE {where_clause}
            ORDER BY s.event_date
            """
            return intent, sql

        # 1. Multi-location event check
        if uses("MULTI_LOCATION_CHECK", ["two different locations", "multiple locations", "two locations", "different venues", "different cities", "both locations", "multi-location", "more than one city"]):
            intent = "MULTI_LOCATION_CHECK"
            sql = """
            SELECT 
                e.name AS event_name,
                e.category,
                l.venue_name,
                l.city,
                l.state,
                l.country,
                s.event_date,
                s.start_time,
                s.end_time,
                (SELECT u.url FROM event_urls u WHERE u.schedule_id = s.schedule_id AND u.url_type = 'ticket_booking' LIMIT 1) AS event_link
            FROM events e
            JOIN event_schedules s ON e.event_id = s.event_id
            JOIN event_locations l ON s.location_id = l.location_id
            WHERE e.name IN (
                SELECT e2.name FROM events e2 
                JOIN event_schedules s2 ON e2.event_id = s2.event_id 
                GROUP BY e2.name HAVING COUNT(DISTINCT s2.location_id) > 1
            )
            ORDER BY e.name, s.event_date
            """
            return intent, sql

        # 2. Seat Codes and Seat Details
        if uses("SEAT_DETAILS", ["seat code", "seat details", "seats", "seat numbers", "row", "section", "accessible", "wheelchair", "front row"]):
            intent = "SEAT_DETAILS"
            acc_filter = "AND st.is_accessible = 1" if any(w in q_lower for w in ["accessible", "wheelchair", "handicap"]) else ""
            sql = f"""
            SELECT DISTINCT 
                e.name AS event_name,
                l.venue_name,
                l.city,
                l.state,
                l.country,
                st.seat_code,
                st.section,
                st.row_num,
                st.seat_number,
                st.tier_name,
                st.is_accessible,
                 (SELECT u.url FROM event_urls u WHERE u.schedule_id = s.schedule_id AND u.url_type = 'venue_map' LIMIT 1) AS venue_map_url
            FROM seats st
            JOIN event_schedules s ON st.schedule_id = s.schedule_id
            JOIN events e ON s.event_id = e.event_id
            JOIN event_locations l ON st.location_id = l.location_id
            WHERE {where_clause} {acc_filter}
            ORDER BY st.section, st.seat_number
            LIMIT 50
            """
            return intent, sql

        # 3. Specific Event Link / Booking URL
        if uses("EVENT_URL", ["link", "url", "website", "book link", "ticket link", "registration link", "where to register", "how to book", "direct link"]):
            intent = "EVENT_URL"
            sql = f"""
            SELECT DISTINCT 
                e.name AS event_name,
                l.venue_name,
                l.city,
                s.event_date,
                u.url_type,
                u.label,
                u.url
            FROM event_urls u
            JOIN events e ON u.event_id = e.event_id
            LEFT JOIN event_schedules s ON u.schedule_id = s.schedule_id
            LEFT JOIN event_locations l ON s.location_id = l.location_id
            WHERE {where_clause}
            ORDER BY e.name, u.url_type
            """
            return intent, sql

        # 4. Ticket Availability & Pricing (Prioritized before generic questions)
        if uses("TICKET_AVAILABILITY", [
            "ticket", "tickets", "price", "prices", "cost", "how much", "cheapest",
            "cheap", "lowest", "affordable", "pass", "passes", "sold out", "admission",
            "tier", "tiers", "vip pass", "rate"
        ]):
            intent = "TICKET_AVAILABILITY"
            price_order = "ASC" if any(w in q_lower for w in ["cheapest", "lowest", "cheap", "affordable", "least"]) else "DESC"
            sold_out_filter = "AND a.status = 'SOLD_OUT'" if "sold out" in q_lower else ""
            sql = f"""
            SELECT 
                e.name AS event_name,
                l.venue_name,
                l.city,
                l.state,
                l.country,
                s.event_date,
                t.tier_name,
                t.price,
                t.currency,
                t.perks,
                a.tickets_available,
                a.tickets_sold,
                a.status AS availability_status,
                (SELECT u.url FROM event_urls u WHERE u.schedule_id = s.schedule_id AND u.url_type = 'ticket_booking' LIMIT 1) AS booking_url
            FROM events e
            JOIN event_schedules s ON e.event_id = s.event_id
            JOIN event_locations l ON s.location_id = l.location_id
            JOIN tickets t ON s.schedule_id = t.schedule_id
            JOIN availability a ON t.ticket_id = a.ticket_id
            WHERE {where_clause} {sold_out_filter}
            ORDER BY t.price {price_order}
            """
            return intent, sql

        # 5. Overview of All Available Events / Event Discovery
        if (uses("LIST_ALL_EVENTS", [
            "what events", "all events", "show events", "list events", "available events",
            "upcoming events", "what can i attend", "events list", "what is happening",
            "tell me what events", "any events", "show me events", "what conferences"
        ]) and "event" not in filters) or (llm_intent == "LIST_ALL_EVENTS" and "event" not in filters):
            intent = "LIST_ALL_EVENTS"
            sql = f"""
            SELECT 
                e.name AS event_name,
                e.category,
                e.description,
                e.organizer,
                l.venue_name,
                l.city,
                l.state,
                l.country,
                s.event_date,
                s.start_time,
                (SELECT u.url FROM event_urls u WHERE u.event_id = e.event_id AND u.url_type = 'ticket_booking' LIMIT 1) AS booking_url
            FROM events e
            JOIN event_schedules s ON e.event_id = s.event_id
            JOIN event_locations l ON s.location_id = l.location_id
            WHERE {where_clause}
            ORDER BY s.event_date
            """
            return intent, sql

        # 6. Organizer & Event Background Details
        if uses("EVENT_DETAILS_INFO", [
            "organizer", "who is organizing", "who organizes", "tell me about",
            "describe", "overview", "what is the event", "what is the summit",
            "what is the festival", "what is the expo", "what is the gala"
        ]) or (not llm_intent and filters.get("event") and any(w in q_lower for w in ["what is", "about", "info", "details"])):
            intent = "EVENT_DETAILS_INFO"
            sql = f"""
            SELECT 
                e.name AS event_name,
                e.category,
                e.description,
                e.organizer,
                l.venue_name,
                l.address,
                l.city,
                l.state,
                l.country,
                l.capacity,
                s.event_date,
                s.start_time,
                s.end_time,
                (SELECT u.url FROM event_urls u WHERE u.event_id = e.event_id AND u.url_type = 'official_site' LIMIT 1) AS official_url,
                (SELECT u.url FROM event_urls u WHERE u.event_id = e.event_id AND u.url_type = 'ticket_booking' LIMIT 1) AS booking_url
            FROM events e
            JOIN event_schedules s ON e.event_id = s.event_id
            JOIN event_locations l ON s.location_id = l.location_id
            WHERE {where_clause}
            ORDER BY s.event_date
            """
            return intent, sql

        # 7. Venue & Location Queries (Where, Address, Capacity)
        if uses("VENUE_LOCATION", ["where is", "where are", "venue", "location", "address", "city", "capacity", "how many people", "where will", "cities"]):
            intent = "VENUE_LOCATION"
            sql = f"""
            SELECT 
                e.name AS event_name,
                e.category,
                l.venue_name,
                l.address,
                l.city,
                l.state,
                l.postal_code,
                l.capacity,
                s.event_date,
                s.start_time,
                (SELECT u.url FROM event_urls u WHERE u.event_id = e.event_id AND u.url_type = 'ticket_booking' LIMIT 1) AS booking_url
            FROM events e
            JOIN event_schedules s ON e.event_id = s.event_id
            JOIN event_locations l ON s.location_id = l.location_id
            WHERE {where_clause}
            ORDER BY s.event_date
            """
            return intent, sql

        # 8. Date & Time Queries (When, Timing, Doors Open, Schedule)
        if uses("DATE_SCHEDULE", ["when is", "when are", "date", "dates", "timing", "what time", "schedule", "doors open", "when will", "november", "december"]):
            intent = "DATE_SCHEDULE"
            sql = f"""
            SELECT 
                e.name AS event_name,
                e.category,
                l.venue_name,
                l.city,
                l.state,
                l.country,
                s.event_date,
                s.start_time,
                s.end_time,
                s.doors_open,
                (SELECT u.url FROM event_urls u WHERE u.event_id = e.event_id AND u.url_type = 'ticket_booking' LIMIT 1) AS booking_url
            FROM events e
            JOIN event_schedules s ON e.event_id = s.event_id
            JOIN event_locations l ON s.location_id = l.location_id
            WHERE {where_clause}
            ORDER BY s.event_date
            """
            return intent, sql

        # 9. Fallback: Default to Event Details or Ticket Info
        intent = "EVENT_DETAILS_INFO" if filters.get("event") else "LIST_ALL_EVENTS"
        sql = f"""
        SELECT 
            e.name AS event_name,
            e.category,
            e.description,
            e.organizer,
            l.venue_name,
            l.city,
            l.state,
            l.country,
            s.event_date,
            s.start_time,
            (SELECT u.url FROM event_urls u WHERE u.event_id = e.event_id AND u.url_type = 'ticket_booking' LIMIT 1) AS booking_url
        FROM events e
        JOIN event_schedules s ON e.event_id = s.event_id
        JOIN event_locations l ON s.location_id = l.location_id
        WHERE {where_clause}
        ORDER BY s.event_date
        """
        return intent, sql

    @staticmethod
    def _loc_label(r: Dict[str, Any]) -> str:
        city = r.get("city") or ""
        state = r.get("state") or ""
        country = r.get("country") or "India"
        return f"{city}, {state}, {country}".strip(", ")

    @staticmethod
    def _price_label(r: Dict[str, Any]) -> str:
        amount = r.get("price") or 0
        currency = r.get("currency") or "INR"
        if currency == "INR":
            return f"₹{amount:,.0f}"
        return f"{amount:.2f} {currency}"

    def _format_response(self, intent: str, records: List[Dict[str, Any]], query: str) -> str:
        """Formats records into clean markdown with clickable links."""
        filters = getattr(self, "_last_filters", {})
        if not records:
            parsed_date = filters.get("_parsed_date_str")
            if parsed_date:
                month_code = filters.get("_parsed_month_code")
                month_name = filters.get("_parsed_month_name", "that month")
                alt_events = []
                if month_code:
                    try:
                        alt_res = DatabaseSecurityEngine.execute_safe_query(
                            self.db_path,
                            f"""
                            SELECT e.name, l.city, l.state, s.event_date,
                                   (SELECT u.url FROM event_urls u WHERE u.event_id = e.event_id AND u.url_type = 'ticket_booking' LIMIT 1) AS booking_url
                            FROM events e
                            JOIN event_schedules s ON e.event_id = s.event_id
                            JOIN event_locations l ON s.location_id = l.location_id
                            WHERE s.event_date LIKE '%-{month_code}-%'
                            ORDER BY s.event_date
                            """
                        )
                        alt_events = alt_res.get("data", [])
                    except Exception:
                        alt_events = []

                resp = f"📅 **No events are scheduled for {parsed_date}, 2026.**\n\n"
                if alt_events:
                    resp += f"Here are upcoming events scheduled in **{month_name}**:\n\n"
                    for a in alt_events:
                        link = f" • [Book Tickets]({a['booking_url']})" if a.get("booking_url") else ""
                        resp += f"• **{a['name']}** on **{a['event_date']}** in {a['city']}, {a.get('state', '')}, India{link}\n"
                else:
                    resp += "You can ask **'What events are available?'** to view all scheduled dates across 2026."
                return resp

            parsed_month = filters.get("_parsed_month_name")
            if parsed_month:
                return f"📅 **No events are scheduled in {parsed_month} 2026.** You can ask **'What events are available?'** to see all scheduled events."

            return (
                "No matching records were found in the database for your query. "
                "You can ask **'What events are available?'** to see all scheduled events."
            )

        # Case 0: Specific Date Events
        if intent == "SPECIFIC_DATE_EVENTS":
            date_label = filters.get("_parsed_date_str", records[0]['event_date'])
            text = f"### 🗓️ Events Scheduled for **{date_label}, 2026** ({len(records)} found)\n\n"
            for i, r in enumerate(records, 1):
                link_part = f" • [Book Tickets]({r['booking_url']})" if r.get("booking_url") else ""
                text += (
                    f"**{i}. {r['event_name']}** (`{r['category']}`)\n"
                    f"• **Organizer:** {r['organizer']}\n"
                    f"• **Location:** {r['venue_name']} ({self._loc_label(r)})\n"
                    f"• **Date & Time:** {r['event_date']} from {r['start_time']} to {r.get('end_time', 'End')}{link_part}\n"
                    f"• **Overview:** {r['description']}\n\n"
                )
            return text.strip()

        # Case 0b: Month Events
        elif intent == "MONTH_EVENTS":
            m_label = filters.get("_parsed_month_name", "that month")
            text = f"### 🗓️ Upcoming Events in **{m_label} 2026** ({len(records)} found)\n\n"
            for i, r in enumerate(records, 1):
                link_part = f" • [Book Tickets]({r['booking_url']})" if r.get("booking_url") else ""
                text += (
                    f"**{i}. {r['event_name']}** (`{r['category']}`)\n"
                    f"• **Organizer:** {r['organizer']}\n"
                    f"• **Location:** {r['venue_name']} ({self._loc_label(r)})\n"
                    f"• **Date & Time:** {r['event_date']} at {r['start_time']}{link_part}\n"
                    f"• **Overview:** {r['description']}\n\n"
                )
            return text.strip()

        # Case 1: Multi-location check
        elif intent == "MULTI_LOCATION_CHECK":
            event_name = records[0]["event_name"]
            text = f"Yes! **{event_name}** is scheduled to take place at **{len(records)} different locations**:\n\n"
            for i, r in enumerate(records, 1):
                url_part = f" • [Book Tickets / View Details]({r['event_link']})" if r.get('event_link') else ""
                text += (
                    f"**{i}. {r['city']} Edition**\n"
                    f"• **Venue:** {r['venue_name']} ({self._loc_label(r)})\n"
                    f"• **Date:** {r['event_date']} from {r['start_time']} to {r['end_time']}{url_part}\n\n"
                )
            text += "Each edition features regional keynote tracks and live workshop sessions."
            return text

        # Case 2: List All Available Events
        elif intent == "LIST_ALL_EVENTS":
            text = f"### 🗓️ Upcoming Events in the Database ({len(records)} found)\n\n"
            for i, r in enumerate(records, 1):
                link_part = f" • [Book Tickets]({r['booking_url']})" if r.get("booking_url") else ""
                text += (
                    f"**{i}. {r['event_name']}** (`{r['category']}`)\n"
                    f"• **Organizer:** {r['organizer']}\n"
                    f"• **Location:** {r['venue_name']} ({self._loc_label(r)})\n"
                    f"• **Date & Time:** {r['event_date']} at {r['start_time']}{link_part}\n"
                    f"• **Overview:** {r['description']}\n\n"
                )
            text += "You can ask for tickets, seat codes, pricing, or venue details for any of these events!"
            return text

        # Case 3: Event Information & Background
        elif intent == "EVENT_DETAILS_INFO":
            r = records[0]
            text = (
                f"### ℹ️ **{r['event_name']}**\n\n"
                f"• **Category:** `{r['category']}`\n"
                f"• **Organized By:** **{r['organizer']}**\n"
                f"• **Overview:** {r['description']}\n"
                f"• **Venue:** {r['venue_name']} ({r['address']}, {self._loc_label(r)})\n"
                f"• **Venue Capacity:** {r['capacity']:,} attendees\n"
                f"• **Scheduled Date:** **{r['event_date']}** ({r['start_time']} – {r['end_time']})\n"
            )
            if r.get("official_url"):
                text += f"• **Official Website:** [Visit Official Site]({r['official_url']})\n"
            if r.get("booking_url"):
                text += f"• **Ticket Booking:** [Book Tickets Here]({r['booking_url']})\n"
            return text

        # Case 4: Venue & Location
        elif intent == "VENUE_LOCATION":
            text = f"### 📍 Venue & Location Information\n\n"
            for r in records:
                link_part = f" • [View Event Details]({r['booking_url']})" if r.get("booking_url") else ""
                text += (
                    f"**{r['event_name']}**\n"
                    f"• **Venue:** **{r['venue_name']}**\n"
                    f"• **Address:** {r['address']}, {self._loc_label(r)} {r.get('postal_code', '')}\n"
                    f"• **Capacity:** {r['capacity']:,} guests\n"
                    f"• **Event Date:** {r['event_date']} at {r['start_time']}{link_part}\n\n"
                )
            return text.strip()

        # Case 5: Dates & Schedules
        elif intent == "DATE_SCHEDULE":
            text = f"### ⏰ Schedule & Date Information\n\n"
            for r in records:
                link_part = f" • [Book Tickets]({r['booking_url']})" if r.get("booking_url") else ""
                doors_part = f" (Doors open: {r['doors_open']})" if r.get("doors_open") else ""
                text += (
                    f"**{r['event_name']}**\n"
                    f"• **Date:** **{r['event_date']}**\n"
                    f"• **Time:** {r['start_time']} – {r['end_time']}{doors_part}\n"
                    f"• **Location:** {r['venue_name']} ({self._loc_label(r)}){link_part}\n\n"
                )
            return text.strip()

        # Case 6: Seat Codes and Seat Details
        elif intent == "SEAT_DETAILS":
            event_groups: Dict[Tuple[str, str, str], List[Dict[str, Any]]] = {}
            for r in records:
                event_key = (r["event_name"], r["venue_name"], r["city"])
                event_groups.setdefault(event_key, []).append(r)

            text = "### 💺 Seat Details & Codes\n\n"
            for (event_name, venue_name, city), event_rows in event_groups.items():
                sample_r = event_rows[0]
                text += f"**{event_name}** — {venue_name} ({self._loc_label(sample_r)})\n\n"
                sections: Dict[str, List[str]] = {}
                for r in event_rows:
                    code = f"`{r['seat_code']}` — {r['row_num']}, Seat #{r['seat_number']} · {r['tier_name']}"
                    if r.get("is_accessible"):
                        code += " ♿ Accessible"
                    sections.setdefault(r["section"], []).append(code)
                for section_name, codes in sections.items():
                    text += f"**{section_name}** ({len(codes)} seats)\n"
                    text += "• " + "\n• ".join(codes) + "\n\n"
                if sample_r.get("venue_map_url"):
                    text += f"🔗 **Venue Map & Seat Selection:** [Open seating map]({sample_r['venue_map_url']})\n\n"
            return text

        # Case 7: Event Link / URL
        elif intent == "EVENT_URL":
            sample_r = records[0]
            text = f"Here are the official links for **{sample_r['event_name']}**:\n\n"
            for r in records:
                link_label = r.get("label") or r.get("url_type", "Event Link")
                link_url = r.get("url")
                text += f"• **{link_label}:** [{link_url}]({link_url})\n"
            text += "\nYou can click the links above to book tickets or view venue guidelines directly."
            return text

        # Case 8: Ticket Availability & Pricing
        else:
            # Group records by event name
            events_dict: Dict[str, List[Dict[str, Any]]] = {}
            for r in records:
                events_dict.setdefault(r["event_name"], []).append(r)

            if len(events_dict) == 1:
                ev_name, ev_records = next(iter(events_dict.items()))
                sample_r = ev_records[0]
                text = f"### 🎟️ Ticket Availability for **{ev_name}**\n"
                text += f"**Venue:** {sample_r['venue_name']} ({self._loc_label(sample_r)}) | **Date:** {sample_r['event_date']}\n\n"
                for r in ev_records:
                    status_icon = "🟢" if r["availability_status"] == "AVAILABLE" else ("🟡" if r["availability_status"] == "LIMITED" else "🔴")
                    text += (
                        f"• **{r['tier_name']}**: **{self._price_label(r)}** {status_icon} *{r['availability_status']}*\n"
                        f"  - **Available:** {r['tickets_available']} tickets remaining ({r['tickets_sold']} sold)\n"
                        f"  - **Perks:** {r.get('perks', 'Standard Admission')}\n"
                    )
                if sample_r.get("booking_url"):
                    text += f"\n👉 **Direct Booking URL:** [Book Your Tickets Here]({sample_r['booking_url']})"
                return text
            else:
                # Multiple events matched (e.g. cheapest tickets or all tickets)
                text = f"### 🎟️ Ticket Pricing & Availability Across Events ({len(events_dict)} events found)\n\n"
                for ev_name, ev_records in events_dict.items():
                    sample_r = ev_records[0]
                    link_part = f" • [Book Tickets]({sample_r['booking_url']})" if sample_r.get("booking_url") else ""
                    text += f"**{ev_name}** ({sample_r['venue_name']}, {self._loc_label(sample_r)} - {sample_r['event_date']}){link_part}\n"
                    for r in ev_records[:3]:
                        status_icon = "🟢" if r["availability_status"] == "AVAILABLE" else ("🟡" if r["availability_status"] == "LIMITED" else "🔴")
                        text += f"• **{r['tier_name']}**: {self._price_label(r)} {status_icon} *{r['availability_status']}* ({r['tickets_available']} left)\n"
                    if len(ev_records) > 3:
                        text += f"• ...and {len(ev_records) - 3} more tiers\n"
                    text += "\n"
                return text.strip()
