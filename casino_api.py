import requests
import secrets
import string
import logging
from config import CASINO_API_URL, CASINO_API_TOKEN, CASINO_API_ENABLED

logger = logging.getLogger(__name__)


class CasinoAPI:
    def __init__(self):
        self.base_url = CASINO_API_URL
        self.token = CASINO_API_TOKEN
        self.enabled = CASINO_API_ENABLED

    def generate_password(self, length: int = 10) -> str:
        chars = string.ascii_letters + string.digits
        return "".join(secrets.choice(chars) for _ in range(length))

    def create_user(self, email: str, name: str = None):
        if not self.enabled:
            return None

        if not self.base_url or not self.token:
            logger.error("CASINO_API_URL or CASINO_API_TOKEN not configured")
            return None

        password = self.generate_password()

        try:
            response = requests.post(
                f"{self.base_url}/create-user",
                json={
                    "token": self.token,
                    "name": name or email.split('@')[0],
                    "email": email,
                    "password": password
                },
                timeout=20
            )

            if response.ok:
                logger.info(f"User created in casino: {email}")
                return {"email": email, "password": password}
            else:
                logger.error(f"API error: {response.status_code} {response.text}")
                return None
        except Exception as e:
            logger.error(f"API request error: {e}")
            return None


casino_api = CasinoAPI()