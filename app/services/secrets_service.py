"""Authoritative encrypted secrets management service for JobPilot."""

import json
import logging
import os
import urllib.request
import urllib.error
from pathlib import Path
from typing import Any, Dict, Optional, Tuple
from sqlalchemy.orm import sessionmaker

from app.db.models.setting import AppSetting
from app.db.session import SessionLocal, get_db_session
from app.repositories.settings_repository import SettingsRepository

logger = logging.getLogger(__name__)

try:
    from cryptography.fernet import Fernet
    _CRYPTO_AVAILABLE = True
except ImportError:
    Fernet = None
    _CRYPTO_AVAILABLE = False


class SecretsService:
    """Provides authenticated AES-128-CBC / HMAC-SHA256 encryption for application secrets."""

    DEFAULT_KEY_DIR = Path.home() / ".jobpilot"
    DEFAULT_KEY_FILE = ".key"

    def __init__(
        self,
        key_path: Optional[str] = None,
        session_factory: Optional[sessionmaker] = None,
    ):
        self._session_factory = session_factory or SessionLocal
        if key_path:
            self._key_path = Path(key_path)
        else:
            self._key_path = self.DEFAULT_KEY_DIR / self.DEFAULT_KEY_FILE

        self._fernet: Optional[Any] = None

    def _ensure_crypto(self) -> None:
        """Enforces fail-secure policy: rejects operation if cryptography is unavailable."""
        if not _CRYPTO_AVAILABLE or Fernet is None:
            raise RuntimeError(
                "Security dependency unavailable. Credentials cannot be stored securely. "
                "Please install 'cryptography' package."
            )

    def _get_fernet(self) -> Any:
        """Initializes or loads the 256-bit Fernet key with strict POSIX 0600 permissions."""
        self._ensure_crypto()
        if self._fernet is not None:
            return self._fernet

        self._key_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            os.chmod(str(self._key_path.parent), 0o700)
        except Exception:
            pass

        if not self._key_path.exists():
            key = Fernet.generate_key()
            # Write with 0600 permissions
            flags = os.O_WRONLY | os.O_CREAT | os.O_TRUNC
            fd = os.open(str(self._key_path), flags, 0o600)
            with os.fdopen(fd, "wb") as f:
                f.write(key)
        else:
            try:
                os.chmod(str(self._key_path), 0o600)
            except Exception:
                pass

        with open(self._key_path, "rb") as f:
            key_data = f.read().strip()

        self._fernet = Fernet(key_data)
        return self._fernet

    def get_secret(self, key: str, default: Optional[str] = None) -> Optional[str]:
        """Retrieves and decrypts a specific secret by key."""
        clean_key = f"secret.{key.strip()}"
        with get_db_session(self._session_factory) as session:
            repo = SettingsRepository(session)
            record = repo.get(clean_key)
            if record and isinstance(record, dict) and "encrypted" in record:
                try:
                    f = self._get_fernet()
                    decrypted_bytes = f.decrypt(record["encrypted"].encode("utf-8"))
                    return decrypted_bytes.decode("utf-8")
                except Exception as exc:
                    logger.error("Failed to decrypt secret '%s': %s", key, exc)
                    return default

        return default

    def set_secret(self, key: str, value: str) -> bool:
        """Encrypts and persists a single secret into the database."""
        self._ensure_crypto()
        if not value:
            return False

        clean_key = f"secret.{key.strip()}"
        f = self._get_fernet()
        encrypted_token = f.encrypt(value.encode("utf-8")).decode("utf-8")

        with get_db_session(self._session_factory) as session:
            repo = SettingsRepository(session)
            repo.set(
                key=clean_key,
                value={"encrypted": encrypted_token},
                category="secrets",
                description=f"Encrypted secret for {key}",
            )
            session.commit()
            return True

    def get_platform_credentials(self, platform: str) -> Tuple[Optional[str], Optional[str]]:
        """Returns (username, password) for the given platform without leaking other secrets."""
        p = platform.strip().lower()
        if p == "linkedin":
            user = self.get_secret("linkedin_username")
            pwd = self.get_secret("linkedin_password")
            return user, pwd
        elif p == "naukri":
            user = self.get_secret("naukri_username")
            pwd = self.get_secret("naukri_password")
            return user, pwd
        elif p == "foundit":
            user = self.get_secret("foundit_username")
            pwd = self.get_secret("foundit_password")
            return user, pwd
        elif p == "glassdoor":
            user = self.get_secret("glassdoor_username")
            pwd = self.get_secret("glassdoor_password")
            return user, pwd
        return None, None

    def get_ai_secret(self, provider_id: str, default: Optional[str] = None) -> Optional[str]:
        """Returns the decrypted API key for a specific provider.

        Strictly enforces provider credential isolation:
        - First checks provider-scoped secret 'secret.ai.api_key.<provider>'.
        - Only falls back to legacy 'secret.llm_api_key' if:
          1) provider_id is empty/unspecified, OR
          2) provider_id matches the active provider configured in the database,
             AND that active provider does not yet have a scoped key.
        - NEVER returns another provider's key to an unconfigured provider.
        """
        p_clean = (provider_id or "").strip().lower()
        if p_clean:
            scoped = self.get_secret(f"ai.api_key.{p_clean}")
            if scoped:
                return scoped

            # Only fall back if p_clean matches the active configured provider in DB
            try:
                with get_db_session(self._session_factory) as session:
                    repo = SettingsRepository(session)
                    active_prov = (repo.get("ai.provider_id") or repo.get("ai.provider", "") or "").strip().lower()
                    if active_prov and active_prov == p_clean:
                        return self.get_secret("llm_api_key", default=default)
            except Exception:
                pass
            return default

        return self.get_secret("llm_api_key", default=default)

    def set_ai_secret(self, provider_id: str, value: str) -> bool:
        """Stores encrypted API key scoped to the specific provider."""
        p_clean = (provider_id or "").strip().lower()
        if p_clean:
            self.set_secret(f"ai.api_key.{p_clean}", value)

        # Only mirror to legacy global key if this provider is the active provider
        try:
            with get_db_session(self._session_factory) as session:
                repo = SettingsRepository(session)
                active_prov = (repo.get("ai.provider_id") or repo.get("ai.provider", "") or "").strip().lower()
                if not active_prov or active_prov == p_clean:
                    self.set_secret("llm_api_key", value)
        except Exception:
            pass

        return True

    def get_ai_credentials(self) -> Dict[str, Any]:
        """Returns scoped AI provider parameters with decrypted API key."""
        with get_db_session(self._session_factory) as session:
            repo = SettingsRepository(session)
            use_ai = repo.get("ai.use_AI", True)
            provider = repo.get("ai.provider", "openai")
            model = repo.get("ai.model", "llama3.1:8b")
            api_url = repo.get("ai.api_url", "http://localhost:11434/v1/")

        api_key = self.get_ai_secret(str(provider), default="") or ""
        return {
            "use_ai": use_ai,
            "provider": provider,
            "model": model,
            "api_url": api_url,
            "api_key": api_key,
        }

    def update_ai_credentials(
        self,
        use_ai: Optional[bool] = None,
        provider: Optional[str] = None,
        model: Optional[str] = None,
        api_url: Optional[str] = None,
        api_key: Optional[str] = None,
    ) -> None:
        """Updates AI configuration and persists encrypted API key if provided."""
        with get_db_session(self._session_factory) as session:
            repo = SettingsRepository(session)
            if use_ai is not None:
                repo.set("ai.use_AI", use_ai, category="ai")
            if provider is not None:
                repo.set("ai.provider", provider, category="ai")
            if model is not None:
                repo.set("ai.model", model, category="ai")
            if api_url is not None:
                repo.set("ai.api_url", api_url, category="ai")
            session.commit()

        if api_key and api_key != "••••••••":
            prov = provider or "ollama"
            self.set_ai_secret(prov, api_key)

    def mask_secret(self, val: Optional[str], prefix_len: int = 3, suffix_len: int = 4) -> str:
        """Generates a safe masked representation for UI rendering."""
        if not val:
            return ""
        if len(val) <= prefix_len + suffix_len:
            return "••••••••"
        return f"{val[:prefix_len]}••••••••{val[-suffix_len:]}"

    def test_ai_connection(
        self,
        provider: str,
        api_key: Optional[str] = None,
        api_url: Optional[str] = None,
        model: Optional[str] = None,
    ) -> Tuple[bool, str]:
        """Validates AI provider endpoint reachability via AIGateway without leaking secrets in logs."""
        from app.services.ai.gateway import AIGateway
        gateway = AIGateway(session_factory=self._session_factory)
        res = gateway.test_connection(
            provider_id=provider,
            base_url=api_url or ("http://localhost:11434/v1" if provider in ("ollama", "local") else "https://api.openai.com/v1"),
            api_key=api_key,
            model=model or "test-model",
        )
        return res.success, res.message

    def get_email_credentials(self, account_id: str = "default") -> Dict[str, Any]:
        """Loads email outreach credentials and server connection settings."""
        # Read user email default from candidate profile if unconfigured
        default_user = "candidate@example.com"
        try:
            from modules.config_loader import get_personal
            p = get_personal()
            if p and p.get("email"):
                default_user = p.get("email")
        except Exception:
            pass

        user = self.get_secret(f"email.{account_id}.user") or os.environ.get("EMAIL_USER") or os.environ.get("GMAIL_USER") or default_user
        password = self.get_secret(f"email.{account_id}.password") or os.environ.get("EMAIL_PASSWORD") or os.environ.get("GMAIL_APP_PASSWORD") or ""
        smtp_host = self.get_secret(f"email.{account_id}.smtp_host") or os.environ.get("EMAIL_SMTP_HOST") or "smtp.gmail.com"
        smtp_port = int(self.get_secret(f"email.{account_id}.smtp_port") or os.environ.get("EMAIL_SMTP_PORT") or 587)
        smtp_use_tls = str(self.get_secret(f"email.{account_id}.smtp_use_tls") or "true").lower() == "true"
        smtp_use_ssl = str(self.get_secret(f"email.{account_id}.smtp_use_ssl") or "false").lower() == "true"

        imap_host = self.get_secret(f"email.{account_id}.imap_host") or os.environ.get("EMAIL_IMAP_HOST") or "imap.gmail.com"
        imap_port = int(self.get_secret(f"email.{account_id}.imap_port") or os.environ.get("EMAIL_IMAP_PORT") or 993)
        imap_use_ssl = str(self.get_secret(f"email.{account_id}.imap_use_ssl") or "true").lower() == "true"

        provider_type = self.get_secret(f"email.{account_id}.provider") or "smtp_imap"
        sync_label = self.get_secret(f"email.{account_id}.sync_label") or os.environ.get("EMAIL_SYNC_LABEL") or "RPA-Developer-Application"

        return {
            "account_id": account_id,
            "provider": provider_type,
            "user": user,
            "password": password,
            "smtp_host": smtp_host,
            "smtp_port": smtp_port,
            "smtp_use_tls": smtp_use_tls,
            "smtp_use_ssl": smtp_use_ssl,
            "imap_host": imap_host,
            "imap_port": imap_port,
            "imap_use_ssl": imap_use_ssl,
            "sync_label": sync_label,
            "is_configured": bool(password and password != ""),
        }

    def set_email_credentials(
        self,
        user: str,
        password: Optional[str] = None,
        smtp_host: str = "smtp.gmail.com",
        smtp_port: int = 587,
        smtp_use_tls: bool = True,
        smtp_use_ssl: bool = False,
        imap_host: str = "imap.gmail.com",
        imap_port: int = 993,
        imap_use_ssl: bool = True,
        provider: str = "smtp_imap",
        sync_label: str = "RPA-Developer-Application",
        account_id: str = "default",
    ) -> None:
        """Saves encrypted email outreach credentials."""
        self.set_secret(f"email.{account_id}.provider", provider)
        self.set_secret(f"email.{account_id}.user", user.strip())
        self.set_secret(f"email.{account_id}.smtp_host", smtp_host.strip())
        self.set_secret(f"email.{account_id}.smtp_port", str(smtp_port))
        self.set_secret(f"email.{account_id}.smtp_use_tls", "true" if smtp_use_tls else "false")
        self.set_secret(f"email.{account_id}.smtp_use_ssl", "true" if smtp_use_ssl else "false")
        self.set_secret(f"email.{account_id}.imap_host", imap_host.strip())
        self.set_secret(f"email.{account_id}.imap_port", str(imap_port))
        self.set_secret(f"email.{account_id}.imap_use_ssl", "true" if imap_use_ssl else "false")
        self.set_secret(f"email.{account_id}.sync_label", sync_label.strip() if sync_label else "RPA-Developer-Application")

        if password and password != "••••••••":
            self.set_secret(f"email.{account_id}.password", password.strip())

    def test_email_connection(
        self,
        user: str,
        password: str,
        smtp_host: str = "smtp.gmail.com",
        smtp_port: int = 587,
        smtp_use_tls: bool = True,
        smtp_use_ssl: bool = False,
        imap_host: str = "imap.gmail.com",
        imap_port: int = 993,
        imap_use_ssl: bool = True,
    ) -> Tuple[bool, str]:
        """Tests SMTP and IMAP credentials with the server."""
        from app.services.email.smtp_imap_provider import GenericSmtpImapProvider
        prov = GenericSmtpImapProvider(
            smtp_host=smtp_host,
            smtp_port=smtp_port,
            smtp_user=user,
            smtp_password=password,
            smtp_use_ssl=smtp_use_ssl,
            smtp_use_tls=smtp_use_tls,
            imap_host=imap_host,
            imap_port=imap_port,
            imap_user=user,
            imap_password=password,
            imap_use_ssl=imap_use_ssl,
            timeout=10.0,
        )
        status = prov.test_connection()
        return status.success, status.message

