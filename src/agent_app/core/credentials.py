from __future__ import annotations
import keyring
from typing import Optional
class CredentialStore:
    def __init__(self, service_name: str = "agentforpc") -> None:
        self.service_name = service_name
    def set_secret(self, name: str, value: str) -> None:
        keyring.set_password(self.service_name, name, value)
    def get_secret(self, name: str) -> Optional[str]:
        return keyring.get_password(self.service_name, name)
