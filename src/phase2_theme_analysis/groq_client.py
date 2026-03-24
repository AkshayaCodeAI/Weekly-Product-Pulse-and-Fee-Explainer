from __future__ import annotations

import json
import logging
import time

from groq import Groq, APIError, RateLimitError

from src.config import GROQ_API_KEY, GROQ_MODEL

logger = logging.getLogger(__name__)

_MAX_RETRIES = 3
_BACKOFF_BASE = 2  # seconds


class GroqClientError(Exception):
    """Raised when the Groq API call fails after all retries."""


def _get_client() -> Groq:
    if not GROQ_API_KEY:
        raise GroqClientError(
            "GROQ_API_KEY is not set. Add it to your .env file."
        )
    return Groq(api_key=GROQ_API_KEY)


def chat_completion(
    system_prompt: str,
    user_prompt: str,
    temperature: float = 0.3,
    max_tokens: int = 2048,
) -> dict:
    """
    Send a chat completion request to Groq with JSON mode enabled.

    Returns the parsed JSON dict from the assistant's response.
    Retries up to 3 times with exponential backoff on transient errors.
    """
    client = _get_client()

    for attempt in range(1, _MAX_RETRIES + 1):
        try:
            response = client.chat.completions.create(
                model=GROQ_MODEL,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=temperature,
                max_tokens=max_tokens,
                response_format={"type": "json_object"},
            )

            raw = response.choices[0].message.content
            return json.loads(raw)

        except RateLimitError:
            if attempt == _MAX_RETRIES:
                raise GroqClientError(
                    "Groq rate limit exceeded after all retries. "
                    "Wait a moment and try again."
                )
            wait = _BACKOFF_BASE**attempt
            logger.warning("Rate limited (attempt %d/%d), retrying in %ds", attempt, _MAX_RETRIES, wait)
            time.sleep(wait)

        except json.JSONDecodeError as e:
            if attempt == _MAX_RETRIES:
                raise GroqClientError(
                    f"Groq returned malformed JSON after {_MAX_RETRIES} attempts: {e}"
                )
            logger.warning("Malformed JSON (attempt %d/%d), retrying", attempt, _MAX_RETRIES)
            time.sleep(_BACKOFF_BASE)

        except APIError as e:
            if attempt == _MAX_RETRIES:
                raise GroqClientError(f"Groq API error after {_MAX_RETRIES} attempts: {e}")
            wait = _BACKOFF_BASE**attempt
            logger.warning("API error (attempt %d/%d), retrying in %ds", attempt, _MAX_RETRIES, wait)
            time.sleep(wait)
