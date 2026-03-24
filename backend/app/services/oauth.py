from google.oauth2 import id_token
from google.auth.transport import requests
from app.core.config import GOOGLE_CLIENT_ID


def verify_google_token(token: str):
    try:
        idinfo = id_token.verify_oauth2_token(
            token,
            requests.Request(),
            GOOGLE_CLIENT_ID
        )
        return idinfo
    except Exception:
        return None