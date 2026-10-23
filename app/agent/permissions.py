import time
import uuid
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field
from app.agent.registry import ToolRegistry

class PermissionTicket(BaseModel):
    ticket_id: str = Field(default_factory=lambda: str(uuid.uuid4())[:8])
    tool_name: str
    args: Dict[str, Any]
    description: str
    risk_level: str  # "LOW", "MEDIUM", "HIGH", "CRITICAL"
    status: str = "PENDING"  # PENDING, APPROVED, REJECTED, EXECUTED, EXPIRED
    created_at: float = Field(default_factory=time.time)
    expires_at: float = Field(default_factory=lambda: time.time() + 300)  # 5 min TTL

    def is_expired(self) -> bool:
        return time.time() > self.expires_at

class PermissionGatekeeper:
    """
    Human-In-The-Loop (HITL) authorization governor.
    Guarantees mutating agent actions cannot run without explicit user confirmation.
    """
    def __init__(self):
        self._tickets: Dict[str, PermissionTicket] = {}

    def create_ticket(
        self,
        tool_name: str,
        args: Dict[str, Any],
        description: str,
        risk_level: str = "MEDIUM"
    ) -> PermissionTicket:
        ticket = PermissionTicket(
            tool_name=tool_name,
            args=args,
            description=description,
            risk_level=risk_level
        )
        self._tickets[ticket.ticket_id] = ticket
        return ticket

    def get_ticket(self, ticket_id: str) -> Optional[PermissionTicket]:
        ticket = self._tickets.get(ticket_id)
        if ticket and ticket.status == "PENDING" and ticket.is_expired():
            ticket.status = "EXPIRED"
        return ticket

    def list_pending(self) -> List[PermissionTicket]:
        now = time.time()
        pending = []
        for ticket in self._tickets.values():
            if ticket.status == "PENDING":
                if ticket.is_expired():
                    ticket.status = "EXPIRED"
                else:
                    pending.append(ticket)
        return pending

    def approve_ticket(self, ticket_id: str) -> bool:
        ticket = self.get_ticket(ticket_id)
        if not ticket:
            return False
        if ticket.status != "PENDING":
            return False
        ticket.status = "APPROVED"
        return True

    def reject_ticket(self, ticket_id: str) -> bool:
        ticket = self.get_ticket(ticket_id)
        if not ticket:
            return False
        if ticket.status != "PENDING":
            return False
        ticket.status = "REJECTED"
        return True

    def execute_ticket(self, ticket_id: str, vector_store) -> Dict[str, Any]:
        ticket = self.get_ticket(ticket_id)
        if not ticket:
            return {"status": "ERROR", "message": "Ticket not found."}
        if ticket.status != "APPROVED":
            return {"status": "ERROR", "message": f"Ticket is not approved (Current status: {ticket.status})."}

        try:
            result = ToolRegistry.execute_mutating(ticket.tool_name, ticket.args, vector_store)
            ticket.status = "EXECUTED"
            return result
        except Exception as e:
            return {"status": "ERROR", "message": f"Execution failed: {str(e)}"}

# Global gatekeeper singleton
gatekeeper = PermissionGatekeeper()
