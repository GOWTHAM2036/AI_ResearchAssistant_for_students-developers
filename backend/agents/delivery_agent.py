"""Delivery Agent: sends the final briefing over email when requested."""
from typing import Any, Callable, Optional

from backend.agents.base_agent import BaseAgent
from backend.tools.email_tool import send_email


class DeliveryAgent(BaseAgent):
    def __init__(self, emit: Optional[Callable] = None):
        super().__init__(
            name="Delivery",
            role="Email Distribution",
            color="#dc2626",
            emit=emit,
        )

    def run(self, input_data: Any) -> dict:
        """
        Input: {"topic": ..., "html": ..., "email": "user@example.com"}
        Output: {"delivered": bool, "message": str, "email": str, "html": str}
        """
        self.emit_status("working")

        topic = input_data.get("topic", "Research Briefing")
        html = input_data.get("html", "<p>No briefing generated.</p>")
        email = (input_data.get("email", "") or "").strip()

        if email:
            self.emit_log(f"Delivering briefing to: {email}")
            subject = f"AI Research Briefing: {topic}"

            result = send_email(
                to_address=email,
                subject=subject,
                html_body=html,
            )

            if result.get("success"):
                self.emit_log(f"Email delivery success: {result['message']}")
                self.emit_status("done")
                return {
                    "delivered": True,
                    "message": result["message"],
                    "email": email,
                    "html": html,
                }

            self.emit_log(f"Email delivery warning: {result['message']}")
            self.emit_log("Briefing is still available in the UI below.")
            self.emit_status("done")
            return {
                "delivered": False,
                "message": result["message"],
                "email": email,
                "html": html,
            }

        self.emit_log("No email address provided - skipping delivery")
        self.emit_log("Briefing rendered in the UI below")
        self.emit_status("done")
        return {
            "delivered": False,
            "message": "No email provided - briefing available in UI",
            "email": "",
            "html": html,
        }
