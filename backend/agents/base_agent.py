"""
BaseAgent — Abstract base class for all agents.
Provides:
  - OpenAI-compatible LLM client (works with Groq, xAI Grok, OpenAI, etc.)
  - Self-correction with 3-tier resilience (primary -> retry -> fallback)
  - JSON extraction with regex fallback
  - Event emission for SSE streaming
"""
import json
import re
import time
from abc import ABC, abstractmethod
from typing import Any, Callable, Dict, Optional

from openai import OpenAI, PermissionDeniedError, AuthenticationError
from backend.config import GROQ_API_KEY, GROQ_MODEL, GROQ_TEMPERATURE, GROQ_MAX_TOKENS, LLM_BASE_URL


def _build_client() -> OpenAI:
    """Build an OpenAI-compatible client based on config."""
    kwargs = {"api_key": GROQ_API_KEY}

    if LLM_BASE_URL:
        # Custom endpoint (xAI, local, etc.)
        kwargs["base_url"] = LLM_BASE_URL
    else:
        # Default to Groq
        kwargs["base_url"] = "https://api.groq.com/openai/v1"

    return OpenAI(**kwargs)


class BaseAgent(ABC):
    """Base class every agent inherits from."""

    def __init__(
        self,
        name: str,
        role: str,
        color: str,
        emit: Optional[Callable] = None,
    ):
        self.name = name
        self.role = role
        self.color = color  # hex color for UI
        self._emit = emit or (lambda *a, **kw: None)
        self.client = _build_client()
        self.model = GROQ_MODEL
        self.temperature = GROQ_TEMPERATURE
        self.max_tokens = GROQ_MAX_TOKENS

    # -- Public interface --

    @abstractmethod
    def run(self, input_data: Any) -> Any:
        """Execute this agent's task. Must be implemented by subclasses."""
        ...

    # -- LLM helpers --

    def call_llm(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> str:
        """
        Call LLM with self-correction.
        Tier 1: Normal call.
        Tier 2: Retry with stricter prompt on failure.
        Returns the raw text response.
        """
        temp = temperature or self.temperature
        tokens = max_tokens or self.max_tokens

        for attempt in range(2):
            try:
                self.emit_log(f"Calling LLM (attempt {attempt + 1})...")
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                    temperature=temp,
                    max_tokens=tokens,
                )
                text = response.choices[0].message.content
                self.emit_log(f"LLM responded ({len(text)} chars)")
                return text

            except Exception as e:
                self.emit_log(f"LLM error (attempt {attempt + 1}): {str(e)[:120]}")
                # Auth/permission failures are non-recoverable for this run.
                if isinstance(e, (PermissionDeniedError, AuthenticationError)):
                    raise
                if attempt == 0:
                    # Retry with a stricter prompt nudge
                    user_prompt = (
                        user_prompt
                        + "\n\nIMPORTANT: Your previous response failed to parse. "
                        "Please respond with ONLY the requested format, no extra text."
                    )
                    time.sleep(1)
                else:
                    raise

    def parse_json(self, text: str, fallback: Dict) -> Dict:
        """
        Extract JSON from LLM output with multiple strategies:
        1. Direct parse
        2. Extract ```json ... ``` block
        3. Find first { ... } substring
        4. Return fallback
        """
        # Strategy 1: Direct parse
        try:
            return json.loads(text.strip())
        except json.JSONDecodeError:
            pass

        # Strategy 2: Fenced code block
        match = re.search(r"```(?:json)?\s*\n?(.*?)\n?\s*```", text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(1).strip())
            except json.JSONDecodeError:
                pass

        # Strategy 3: First { ... } or [ ... ]
        match = re.search(r"(\{[\s\S]*\})", text)
        if match:
            try:
                return json.loads(match.group(1))
            except json.JSONDecodeError:
                pass

        # Strategy 4: Fallback
        self.emit_log("JSON parse failed -- using fallback structure")
        return fallback

    # -- Logging / SSE --

    def emit_log(self, message: str):
        """Emit a log message for the activity feed."""
        self._emit(
            "log",
            {
                "agent": self.name,
                "color": self.color,
                "message": message,
                "timestamp": time.time(),
            },
        )

    def emit_status(self, status: str):
        """Emit agent status change (idle / working / done / error)."""
        self._emit(
            "status",
            {
                "agent": self.name,
                "status": status,
                "color": self.color,
            },
        )
