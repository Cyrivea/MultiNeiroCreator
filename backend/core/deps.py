from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials

from core.security import bearer_scheme, decode_token


def verify_token(credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme)) -> dict:
    return decode_token(credentials)
