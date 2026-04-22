import os

from claim_cloud_id.constants import DEFAULT_LOG_FILE


def get_dashboard_api_key() -> str:
    api_key = os.getenv("MERAKI_DASHBOARD_API_KEY")
    if not api_key:
        raise EnvironmentError("MERAKI_DASHBOARD_API_KEY is not set")
    return api_key


def get_org_id(cli_org_id: str | None) -> str:
    return cli_org_id or os.getenv("MERAKI_ORG_ID") or ""


def get_log_file_path(cli_log_file: str | None) -> str:
    if cli_log_file:
        return cli_log_file
    env_log_file = os.getenv("MERAKI_LOG_FILE")
    if env_log_file:
        return env_log_file
    return DEFAULT_LOG_FILE


def get_action_past_tense(action: str) -> str:
    if action == "claim":
        return "claimed"
    if action == "release":
        return "released"
    return "checked"
