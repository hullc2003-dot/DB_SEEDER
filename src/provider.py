from __future__ import annotations
from typing import Any, Optional, List
import os
import httpx
import logging
from tenacity import (
    retry,
    stop_after_attempt,
    wait_random_exponential,
    retry_if_exception_type,
)

from .config import ProviderConfig
from .provider_usage import save_usage, ProviderUsage
# Fixed potential typo in your import to match previous file name
from .provider_router import ProviderRouter 

logger = logging.getLogger("ProviderLayer")

class ProviderLayer:
    def __init__(self, config: ProviderConfig, usage: ProviderUsage | None = None):
        self.config = config
        self.usage = usage
        self.openai_key = os.getenv("OPENAI_API_KEY")
        self.groq_key = os.getenv("GROQ_API_KEY")
        self.openrouter_key = os.getenv("OPENROUTER_API_KEY")

        self.router = ProviderRouter(
            use_openai=bool(self.openai_key),
            use_groq=bool(self.groq_key),
            use_openrouter=bool(self.openrouter_key),
            openai_key=self.openai_key,
            groq_key=self.groq_key,
            openrouter_key=self.openrouter_key,
            strategy=self.config.provider_router_strategy,
            usage=self.usage,
            debug=self.config.debug_routing,
        )

    def select_model(self, intent: str) -> str:
        try:
            model = self.router.select_model(intent)
            if model:
                return model
        except Exception as e:
            logger.warning(f"Router model selection failed: {e}")
        return "openai:gpt-4o"

    async def _http_post(self, url: str, headers: dict, body: dict) -> str:
        async with httpx.AsyncClient() as client:
            # Added explicit error handling for common status codes
            resp = await client.post(url, headers=headers, json=body, timeout=30.0)
            if resp.status_code == 429:
                raise httpx.HTTPStatusError("Rate limit exceeded", request=resp.request, response=resp)
            resp.raise_for_status()
            data = resp.json()
            return data["choices"][0]["message"]["content"]

    async def _call_openai(self, prompt: str) -> str:
        url = "https://api.openai.com/v1/chat/completions"
        headers = {"Authorization": f"Bearer {self.openai_key}"}
        body = {
            "model": "gpt-4o",
            "messages": [{"role": "user", "content": prompt}],
        }
        return await self._http_post(url, headers, body)

    async def _call_groq(self, prompt: str) -> str:
        url = "https://api.groq.com/openai/v1/chat/completions"
        headers = {"Authorization": f"Bearer {self.groq_key}"}
        body = {
            "model": "llama-3.3-70b-versatile",
            "messages": [{"role": "user", "content": prompt}],
        }
        return await self._http_post(url, headers, body)

    async def _call_openrouter(self, prompt: str) -> str:
        url = "https://openrouter.ai/api/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.openrouter_key}",
            "HTTP-Referer": "https://ask-dale.onrender.com",
            "X-Title": "AI Brain Agent",
        }
        body = {
            "model": "xiaomi/mimo-v2-flash",
            "messages": [{"role": "user", "content": prompt}],
        }
        return await self._http_post(url, headers, body)

    @retry(
        wait=wait_random_exponential(min=1, max=5),
        stop=stop_after_attempt(2),
        # Now catches 429 via HTTPStatusError if needed, but usually we want to fallback immediately
        retry=retry_if_exception_type((httpx.ConnectError, httpx.TimeoutException)),
        reraise=True,
    )
    async def _dispatch_call(self, provider: str, prompt: str) -> str:
        if provider == "openai":
            return await self._call_openai(prompt)
        if provider == "groq":
            return await self._call_groq(prompt)
        if provider == "openrouter":
            return await self._call_openrouter(prompt)
        raise ValueError(f"Unknown provider: {provider}")

    async def call_model(self, model_tag: str, prompt: str) -> str:
        """
        Ignores the passed model_tag for fallback logic and uses 
        the internal provider-specific model mapping.
        """
        available_providers = self.router.available_providers()
        if not available_providers:
            return "Error: All providers offline or out of quota."

        last_error = ""
        for provider in available_providers:
            try:
                # Dispatch using the provider's native designated model
                response = await self._dispatch_call(provider, prompt)
                
                # Usage Tracking
                tokens = max(1, (len(prompt) + len(response)) // 4)
                self._increment_usage(provider, tokens / self.config.tokens_per_minute)
                return response
            except Exception as e:
                last_error = str(e)
                logger.warning(f"Provider '{provider}' failed: {last_error}. Trying fallback...")
                continue

        return f"Service temporarily unavailable. (Last error: {last_error})"

    def _increment_usage(self, provider: str, minutes: float) -> None:
        if not self.usage:
            return
        attr = f"{provider}_minutes_used"
        if hasattr(self.usage, attr):
            setattr(self.usage, attr, getattr(self.usage, attr) + minutes)
            save_usage(self.usage)
