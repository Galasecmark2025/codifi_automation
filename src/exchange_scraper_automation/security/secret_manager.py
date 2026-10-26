# secret_manager.py

from cryptography.fernet import Fernet, InvalidToken

from exchange_scraper_automation.observability.logger import Logger


class SecretManager:
    """Encrypt and decrypt application secrets using Fernet."""

    PREFIX = "fernet:"

    def __init__(self, encryption_key: str) -> None:
        if not encryption_key:
            Logger.error("SFTP encryption key is not configured.")

        try:
            self._fernet = Fernet(encryption_key.encode("ascii"))
        except (ValueError, UnicodeEncodeError) as error:
            Logger.error("Invalid Fernet encryption key.")

    def encrypt(self, plaintext: str) -> str:
        """Encrypt a plaintext secret for storage."""

        if not isinstance(plaintext, str) or not plaintext:
            Logger.error("Secret must be a non-empty string.")

        if plaintext.startswith(self.PREFIX):
            Logger.error("Secret appears to be already encrypted.")

        encrypted = self._fernet.encrypt(plaintext.encode("utf-8")).decode("ascii")

        return f"{self.PREFIX}{encrypted}"

    def decrypt(self, encrypted_value: str) -> str:
        """Decrypt a Fernet-encrypted secret."""

        if not encrypted_value.startswith(self.PREFIX):
            Logger.error("Expected a Fernet-encrypted secret.")

        token = encrypted_value[len(self.PREFIX) :]

        try:
            return self._fernet.decrypt(token.encode("ascii")).decode("utf-8")
        except (InvalidToken, UnicodeEncodeError) as error:
            Logger.error(
                "Unable to decrypt secret. Verify the key and encrypted value."
            )

    def decrypt_if_encrypted(self, value: str) -> str:
        """Temporarily support both encrypted and legacy plaintext values."""

        if value.startswith(self.PREFIX):
            return self.decrypt(value)

        return value
