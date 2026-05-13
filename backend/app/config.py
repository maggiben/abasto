from decimal import Decimal
from functools import lru_cache
import json

from pydantic import AliasChoices, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_DEFAULT_CORS_CSV = "http://localhost:3000,http://127.0.0.1:3000"
_DEFAULT_CORS_ORIGIN_REGEX = r"^https?://(localhost|127\.0\.0\.1)(:\d+)?$"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "Abasto API"
    debug: bool = False

    # Staff-only POST /admin/sales/reset-all wipes POS tickets and web orders and restores stock.
    # Keep false in production unless you intentionally accept data loss from the admin UI.
    allow_reset_sales: bool = Field(default=False, validation_alias=AliasChoices("ALLOW_RESET_SALES", "allow_reset_sales"))

    # Stored as CSV so env/docker compose need not use JSON (list[str] is JSON-decoded by
    # pydantic-settings before validators run, which breaks comma-separated CORS_ORIGINS).
    cors_origins_csv: str = Field(
        default=_DEFAULT_CORS_CSV,
        validation_alias=AliasChoices("CORS_ORIGINS", "cors_origins"),
    )
    cors_origin_regex: str = Field(
        default=_DEFAULT_CORS_ORIGIN_REGEX,
        validation_alias=AliasChoices("CORS_ORIGIN_REGEX", "cors_origin_regex"),
    )

    database_url: str = "postgresql+asyncpg://abasto:abasto@localhost:5432/abasto"

    jwt_secret: str = "change-me-in-production-use-long-random-string"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60 * 24
    bootstrap_admin_email: str | None = None
    bootstrap_admin_password: str | None = None

    # Applied when checkout request does not override tax_rate_percent (e.g. 10 means 10%).
    default_tax_rate_percent: Decimal = Decimal("0")

    # USB thermal receipt printer (runs on same host as the API, e.g. Raspberry Pi).
    printer_enabled: bool = False
    printer_usb_vendor: int = 0x0483
    printer_usb_product: int = 0x070B
    # python-escpos capability profile name (see escpos capabilities.json), not the hardware model.
    printer_profile: str = "default"
    printer_prefer_escpos: bool = False
    receipt_store_name: str = "ABASTO"

    @field_validator("printer_usb_vendor", "printer_usb_product", mode="before")
    @classmethod
    def parse_usb_id(cls, v: object) -> int:
        if isinstance(v, str):
            s = v.strip().lower()
            if s.startswith("0x"):
                return int(s, 16)
            return int(s, 10)
        if isinstance(v, int):
            return v
        raise TypeError("USB id must be int or hex string")

    @field_validator("cors_origins_csv", mode="before")
    @classmethod
    def parse_cors_csv(cls, v: object) -> str:
        if v is None:
            return _DEFAULT_CORS_CSV
        if isinstance(v, list):
            parts = [str(x).strip() for x in v if str(x).strip()]
            return ",".join(parts) if parts else _DEFAULT_CORS_CSV
        s = str(v).strip()
        if not s:
            return _DEFAULT_CORS_CSV
        if s.startswith("["):
            try:
                decoded = json.loads(s)
            except json.JSONDecodeError:
                return s
            if isinstance(decoded, list):
                parts = [str(x).strip() for x in decoded if str(x).strip()]
                return ",".join(parts) if parts else _DEFAULT_CORS_CSV
        return s

    @property
    def cors_origins(self) -> list[str]:
        return [s.strip() for s in self.cors_origins_csv.split(",") if s.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
