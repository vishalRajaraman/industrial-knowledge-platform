from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from ..core.identity import SYSTEM_ROLES, SystemRole
from ..core.security import decode_access_token
from ..schemas.auth import AuthenticatedUser


bearer_scheme = HTTPBearer(auto_error=False)


def get_current_user(credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme)) -> AuthenticatedUser:
    if credentials is None or not credentials.credentials:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing bearer token")

    decoded = decode_access_token(credentials.credentials)
    username = decoded.get("sub")
    role = decoded.get("role")

    if not isinstance(username, str) or role not in SYSTEM_ROLES:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token payload")

    return AuthenticatedUser(username=username, role=role)


def require_roles(*allowed_roles: SystemRole):
    allowed_set = set(allowed_roles)

    def dependency(current_user: AuthenticatedUser = Depends(get_current_user)) -> AuthenticatedUser:
        if current_user.role not in allowed_set:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient role permissions")
        return current_user

    return dependency
