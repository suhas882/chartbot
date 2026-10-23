import re
from typing import Tuple, List, Dict, Any

class PIIScrubber:
    """
    Local privacy-by-design scanner detecting and redacting sensitive PII entities.
    Operates 100% locally with zero cloud dependencies.
    """
    PATTERNS = {
        "EMAIL": re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,7}\b'),
        "PHONE": re.compile(r'(?:\+?\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b'),
        "SSN": re.compile(r'\b\d{3}-\d{2}-\d{4}\b'),
        "CREDIT_CARD": re.compile(r'\b(?:\d{4}[-\s]?){3}\d{4}\b'),
        "API_KEY": re.compile(r'(?i)(?:api_key|bearer|token|secret)[\s:=]+[\'"]?([a-zA-Z0-9_\-]{16,})[\'"]?'),
        "IP_ADDRESS": re.compile(r'\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b')
    }

    @classmethod
    def sanitize(cls, text: str) -> Tuple[str, List[Dict[str, Any]]]:
        redacted_entities = []
        sanitized = text

        for label, pattern in cls.PATTERNS.items():
            matches = list(pattern.finditer(sanitized))
            # Process in reverse order to preserve string offsets
            for match in reversed(matches):
                val = match.group(0)
                redacted_entities.append({
                    "entity_type": label,
                    "original_length": len(val),
                    "start": match.start(),
                    "end": match.end()
                })
                sanitized = sanitized[:match.start()] + f"[REDACTED_{label}]" + sanitized[match.end():]

        return sanitized, redacted_entities

    @classmethod
    def scrub(cls, text: str) -> Tuple[str, List[Dict[str, Any]]]:
        return cls.sanitize(text)

    @classmethod
    def contains_pii(cls, text: str) -> bool:
        for pattern in cls.PATTERNS.values():
            if pattern.search(text):
                return True
        return False
