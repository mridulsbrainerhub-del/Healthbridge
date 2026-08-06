import httpx
import logging
from typing import Optional, List

from ..schemas.ai.registry import ProtectedDischarge

logger = logging.getLogger(__name__)


class BOFClient:
    """BOF API Client for protected discharges (dimissioni protette)."""

    def __init__(self, base_url: str, token: Optional[str] = None,
                 timeout: int = 10, enabled: bool = True):
        self.base_url = base_url if base_url else "https://bof.asst-brianza.it/api/v1/index.php"
        self.token = token
        self.timeout = timeout
        # Only enable if we have both URL and token
        self.enabled = enabled and token is not None
        self._api_available: Optional[bool] = None

        logger.info(f"BOFClient initialized: enabled={self.enabled}, has_token={token is not None}, timeout={timeout}s, url={self.base_url}")

    async def get_protected_discharges(self, fiscal_code: str) -> List[ProtectedDischarge]:
        if not self.enabled:
            logger.debug(f"BOF API disabled, skipping request for {fiscal_code}")
            return []

        logger.info(f"BOF API calling: {self.base_url} for {fiscal_code}")

        try:
            async with httpx.AsyncClient(timeout=self.timeout, verify=False) as client:
                response = await client.post(
                    self.base_url,
                    json={
                        "action": "dimissioniprotette.getpatitient",
                        "token": self.token,
                        "data": fiscal_code.upper()
                    }
                )
                logger.info(f"BOF API response status: {response.status_code}")

                if response.status_code == 200:
                    result = response.json()
                    self._api_available = True

                    # API returns: {"status": 1, "error": null, "data": <data or null>}
                    if result.get("status") == 1 and result.get("data"):
                        data = result["data"]
                        if isinstance(data, list):
                            logger.info(f"BOF: Found {len(data)} protected discharge(s) for {fiscal_code}")
                            return [ProtectedDischarge(data=item) for item in data if item]
                        elif isinstance(data, dict):
                            logger.info(f"BOF: Found 1 protected discharge for {fiscal_code}")
                            return [ProtectedDischarge(data=data)]

                    logger.info(f"BOF: No protected discharge data for {fiscal_code}")
                    return []
                else:
                    logger.warning(f"BOF API returned status {response.status_code}")
                    return []

        except httpx.TimeoutException:
            logger.warning(f"BOF API timeout for {fiscal_code}")
            self._api_available = False
            return []
        except httpx.ConnectError as e:
            logger.warning(f"BOF API connection error: {e}")
            self._api_available = False
            return []
        except Exception as e:
            logger.error(f"BOF API error ({type(e).__name__}): {e}")
            self._api_available = False
            return []

    def is_available(self) -> bool:
        if self._api_available is not None:
            return self._api_available
        return self.enabled
