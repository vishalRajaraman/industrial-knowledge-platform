from dataclasses import dataclass
import json
import os
from typing import Literal


SystemRole = Literal["field_tech", "manager", "engineer"]
SYSTEM_ROLES: tuple[SystemRole, ...] = ("field_tech", "manager", "engineer")


@dataclass(frozen=True, slots=True)
class GatewayUser:
    username: str
    password: str
    role: SystemRole


DEFAULT_USER_DIRECTORY: dict[str, GatewayUser] = {
    "field.tech": GatewayUser(username="field.tech", password="field-tech-pass", role="field_tech"),
    "manager": GatewayUser(username="manager", password="manager-pass", role="manager"),
    "engineer": GatewayUser(username="engineer", password="engineer-pass", role="engineer"),
}


def _load_users_from_env() -> dict[str, GatewayUser]:
    raw_value = os.getenv("API_GATEWAY_USERS_JSON", "").strip()
    if not raw_value:
        return DEFAULT_USER_DIRECTORY

    try:
        records = json.loads(raw_value)
    except json.JSONDecodeError:
        return DEFAULT_USER_DIRECTORY

    if not isinstance(records, list):
        return DEFAULT_USER_DIRECTORY

    loaded_users: dict[str, GatewayUser] = {}
    for record in records:
        if not isinstance(record, dict):
            continue

        username = record.get("username")
        password = record.get("password")
        role = record.get("role")
        if username in {None, ""} or password in {None, ""} or role not in SYSTEM_ROLES:
            continue

        loaded_users[str(username)] = GatewayUser(
            username=str(username),
            password=str(password),
            role=role,
        )

    return loaded_users or DEFAULT_USER_DIRECTORY


USER_DIRECTORY: dict[str, GatewayUser] = _load_users_from_env()
