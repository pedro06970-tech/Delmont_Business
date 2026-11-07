import json
import os
import socket
from dataclasses import dataclass
from http.client import RemoteDisconnected
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

from app.core.config import settings


@dataclass(frozen=True)
class ConnectionResult:
    state: str


@dataclass(frozen=True)
class SendResult:
    provider_message_id: str | None
    provider_status: str


class WhatsMiauError(Exception):
    def __init__(
        self,
        category: str,
        message: str,
        *,
        http_status: int | None = None,
        safe_to_retry: bool = False,
        ambiguous: bool = False,
    ) -> None:
        super().__init__(message)
        self.category = category
        self.safe_message = message
        self.http_status = http_status
        self.safe_to_retry = safe_to_retry
        self.ambiguous = ambiguous


def resolve_credential(reference: str) -> str:
    value = os.environ.get(reference, "").strip()
    if not value:
        raise WhatsMiauError("missing_credential", "Credencial WhatsMiau não configurada.")
    return value


class WhatsMiauClient:
    def __init__(self, *, base_url: str | None = None, timeout: float | None = None) -> None:
        self.base_url = (base_url or settings.WHATSMIAU_BASE_URL).rstrip("/")
        self.timeout = timeout or settings.WHATSMIAU_HTTP_TIMEOUT_SECONDS

    def connection_state(self, instance_name: str, api_key: str) -> ConnectionResult:
        payload = self._request_json(
            "GET",
            f"/instance/connectionState/{quote(instance_name, safe='')}",
            api_key,
            operation="status",
        )
        state = payload.get("state")
        if not isinstance(state, str) and isinstance(payload.get("instance"), dict):
            state = payload["instance"].get("state")
        if not isinstance(state, str):
            raise WhatsMiauError(
                "invalid_response", "Resposta de status inválida da WhatsMiau."
            )
        return ConnectionResult(state=state)

    def send_text(
        self, instance_name: str, api_key: str, *, number: str, text: str
    ) -> SendResult:
        payload = self._request_json(
            "POST",
            f"/message/sendText/{quote(instance_name, safe='')}",
            api_key,
            body={"number": number.lstrip("+"), "text": text},
            operation="send",
        )
        message_id = self._message_id(payload)
        status = payload.get("status")
        return SendResult(
            provider_message_id=message_id,
            provider_status=status if isinstance(status, str) else "accepted",
        )

    @staticmethod
    def _message_id(payload: dict[str, Any]) -> str | None:
        key = payload.get("key")
        candidates = [
            key.get("id") if isinstance(key, dict) else None,
            payload.get("messageId"),
            payload.get("id"),
        ]
        return next((str(value) for value in candidates if value), None)

    def _request_json(
        self,
        method: str,
        path: str,
        api_key: str,
        *,
        body: dict[str, Any] | None = None,
        operation: str,
    ) -> dict[str, Any]:
        encoded = json.dumps(body).encode("utf-8") if body is not None else None
        request = Request(
            f"{self.base_url}{path}",
            data=encoded,
            method=method,
            headers={"apikey": api_key, "Content-Type": "application/json"},
        )
        try:
            with urlopen(request, timeout=self.timeout) as response:
                raw = response.read()
        except HTTPError as error:
            if error.code == 429:
                raise WhatsMiauError(
                    "rate_limited",
                    "A WhatsMiau recusou temporariamente o envio por limite de requisições.",
                    http_status=error.code,
                    safe_to_retry=True,
                )
            if operation == "send" and (error.code == 408 or error.code >= 500):
                raise WhatsMiauError(
                    "ambiguous_provider_error",
                    "A WhatsMiau retornou erro sem permitir confirmar o resultado do envio.",
                    http_status=error.code,
                    ambiguous=True,
                )
            raise WhatsMiauError(
                "permanent_provider_error",
                "A WhatsMiau rejeitou a requisição.",
                http_status=error.code,
            )
        except (socket.timeout, TimeoutError):
            raise WhatsMiauError(
                "timeout",
                "A resposta da WhatsMiau excedeu o tempo limite.",
                ambiguous=operation == "send",
                safe_to_retry=operation != "send",
            )
        except URLError as error:
            if isinstance(error.reason, (socket.timeout, TimeoutError)):
                raise WhatsMiauError(
                    "timeout",
                    "A resposta da WhatsMiau excedeu o tempo limite.",
                    ambiguous=operation == "send",
                    safe_to_retry=operation != "send",
                )
            if operation == "send" and not isinstance(
                error.reason, (ConnectionRefusedError, socket.gaierror)
            ):
                raise WhatsMiauError(
                    "connection_lost",
                    "A conexão com a WhatsMiau terminou sem confirmar o resultado do envio.",
                    ambiguous=True,
                )
            raise WhatsMiauError(
                "connection_failed",
                "Não foi possível conectar à WhatsMiau antes do envio.",
                safe_to_retry=True,
            )
        except (ConnectionError, RemoteDisconnected):
            raise WhatsMiauError(
                "connection_lost",
                "A conexão com a WhatsMiau foi encerrada sem confirmar o resultado.",
                ambiguous=operation == "send",
                safe_to_retry=operation != "send",
            )

        if not raw:
            return {}
        try:
            payload = json.loads(raw)
        except (UnicodeDecodeError, json.JSONDecodeError):
            if operation == "send":
                raise WhatsMiauError(
                    "ambiguous_response",
                    "A WhatsMiau aceitou a conexão, mas retornou uma resposta inválida.",
                    ambiguous=True,
                )
            raise WhatsMiauError("invalid_response", "Resposta inválida da WhatsMiau.")
        if not isinstance(payload, dict):
            raise WhatsMiauError("invalid_response", "Resposta inválida da WhatsMiau.")
        return payload
