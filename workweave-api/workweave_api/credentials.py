from pydantic import SecretStr
from .config import Settings
from .providers import Vault


def get_secret_val(val) -> str:
    if isinstance(val, SecretStr):
        return val.get_secret_value()
    return str(val or "")


def get_company_credentials(vault: Vault, config: Settings, company_id: str) -> dict:
    data = vault.read()
    slack_token = data.get(f"company:{company_id}:slack:bot_token", "")
    slack_secret = data.get(f"company:{company_id}:slack:signing_secret", "")
    slack_app_id = data.get(f"company:{company_id}:slack:app_id", "")
    clickup_token = data.get(f"company:{company_id}:clickup:token", "")
    clickup_list_id = data.get(f"company:{company_id}:clickup:list_id", "")

    # Bootstrap from environment if configured and this company matches bootstrap_company_id
    if config.bootstrap_company_id and config.bootstrap_company_id == company_id:
        if not data.get(f"company:{company_id}:slack:disabled") and not slack_token and get_secret_val(config.slack_bot_token):
            slack_token = get_secret_val(config.slack_bot_token)
            vault.set(f"company:{company_id}:slack:bot_token", slack_token)
        if not data.get(f"company:{company_id}:slack:disabled") and not slack_secret and get_secret_val(config.slack_signing_secret):
            slack_secret = get_secret_val(config.slack_signing_secret)
            vault.set(f"company:{company_id}:slack:signing_secret", slack_secret)
        if not data.get(f"company:{company_id}:slack:disabled") and not slack_app_id and config.slack_app_id:
            slack_app_id = config.slack_app_id
            vault.set(f"company:{company_id}:slack:app_id", slack_app_id)
        if not data.get(f"company:{company_id}:clickup:disabled") and not clickup_token and get_secret_val(config.clickup_api_token):
            clickup_token = get_secret_val(config.clickup_api_token)
            vault.set(f"company:{company_id}:clickup:token", clickup_token)
        if not data.get(f"company:{company_id}:clickup:disabled") and not clickup_list_id and config.clickup_list_id:
            clickup_list_id = config.clickup_list_id
            vault.set(f"company:{company_id}:clickup:list_id", clickup_list_id)

    return {
        "slack_bot_token": slack_token,
        "slack_signing_secret": slack_secret,
        "slack_app_id": slack_app_id,
        "clickup_token": clickup_token,
        "clickup_list_id": clickup_list_id,
    }


def set_company_slack(vault: Vault, company_id: str, bot_token: str, signing_secret: str, app_id: str = ""):
    vault.set(f"company:{company_id}:slack:disabled", None)
    vault.set(f"company:{company_id}:slack:bot_token", bot_token.strip())
    vault.set(f"company:{company_id}:slack:signing_secret", signing_secret.strip())
    if app_id:
        vault.set(f"company:{company_id}:slack:app_id", app_id.strip())


def set_company_clickup(vault: Vault, company_id: str, token: str, list_id: str):
    vault.set(f"company:{company_id}:clickup:disabled", None)
    vault.set(f"company:{company_id}:clickup:token", token.strip())
    vault.set(f"company:{company_id}:clickup:list_id", list_id.strip())


def clear_company_credentials(vault: Vault, company_id: str, provider: str | None = None):
    if provider in (None, "slack"):
        vault.set(f"company:{company_id}:slack:disabled", "true")
        vault.set(f"company:{company_id}:slack:bot_token", None)
        vault.set(f"company:{company_id}:slack:signing_secret", None)
        vault.set(f"company:{company_id}:slack:app_id", None)
    if provider in (None, "clickup"):
        vault.set(f"company:{company_id}:clickup:disabled", "true")
        vault.set(f"company:{company_id}:clickup:token", None)
        vault.set(f"company:{company_id}:clickup:list_id", None)


def get_company_status(vault: Vault, config: Settings, company_id: str) -> dict:
    creds = get_company_credentials(vault, config, company_id)
    return {
        "slack": {
            "configured": bool(creds["slack_bot_token"] and creds["slack_signing_secret"]),
            "app_id": creds["slack_app_id"],
        },
        "clickup": {
            "configured": bool(creds["clickup_token"] and creds["clickup_list_id"]),
            "list_id": creds["clickup_list_id"],
        }
    }
