import httpx
import logging
from typing import Optional, Dict
from datetime import datetime, timedelta

from ..schemas.ai.registry import RegistryPatient, LuogoNascita, Indirizzo

logger = logging.getLogger(__name__)


class RegistryClient:
    """Client for Central Registry API - fully dynamic, no static data."""

    def __init__(self, base_url: str, timeout: int = 30, enabled: bool = True, cache_ttl_minutes: int = 30):
        self.base_url = base_url.rstrip("/") if base_url else "https://clumiddle.aodv.local/AC/pac/rest/paziente"
        self.timeout = timeout
        self.enabled = enabled
        self.cache_ttl = timedelta(minutes=cache_ttl_minutes)
        self._cache: Dict[str, tuple] = {}
        self._api_available: Optional[bool] = None

        logger.info(f"RegistryClient initialized: enabled={enabled}, timeout={timeout}s, url={self.base_url}")

    def _is_cache_valid(self, fiscal_code: str) -> bool:
        if fiscal_code not in self._cache:
            return False
        _, timestamp = self._cache[fiscal_code]
        return datetime.now() - timestamp < self.cache_ttl

    def _parse_response(self, data: dict) -> Optional[RegistryPatient]:
        try:
            luogo_nascita = None
            if data.get("LuogoNascita"):
                luogo_nascita = LuogoNascita(
                    codice_istat_comune=data["LuogoNascita"].get("CodiceISTATComune"),
                    descrizione_comune=data["LuogoNascita"].get("DescrizioneComune")
                )

            residenza = None
            if data.get("Residenza"):
                residenza = Indirizzo(
                    codice_istat_comune=data["Residenza"].get("CodiceISTATComune"),
                    descrizione_comune=data["Residenza"].get("DescrizioneComune"),
                    indirizzo=data["Residenza"].get("Indirizzo")
                )

            domicilio = None
            if data.get("Domicilio"):
                domicilio = Indirizzo(
                    codice_istat_comune=data["Domicilio"].get("CodiceISTATComune"),
                    descrizione_comune=data["Domicilio"].get("DescrizioneComune"),
                    indirizzo=data["Domicilio"].get("Indirizzo")
                )

            return RegistryPatient(
                codice_fiscale=data.get("CodiceFiscale", ""),
                cognome=data.get("Cognome", ""),
                nome=data.get("Nome", ""),
                data_nascita=data.get("DataNascita", ""),
                sesso=data.get("Sesso", ""),
                idac=data.get("IDAC"),
                luogo_nascita=luogo_nascita,
                residenza=residenza,
                domicilio=domicilio
            )
        except Exception as e:
            logger.error(f"Failed to parse Registry response: {e}")
            return None

    async def get_patient(self, fiscal_code: str) -> Optional[RegistryPatient]:
        fiscal_code = fiscal_code.upper().strip()

        if not self.enabled:
            logger.debug(f"Registry API disabled, skipping request for {fiscal_code}")
            return None

        # Check cache first
        if self._is_cache_valid(fiscal_code):
            patient, _ = self._cache[fiscal_code]
            logger.debug(f"Registry cache hit for {fiscal_code}")
            return patient

        # Call real API
        url = f"{self.base_url}/{fiscal_code}"
        logger.info(f"Calling Registry API: {url}")

        try:
            async with httpx.AsyncClient(timeout=self.timeout, verify=False) as client:
                response = await client.get(url, headers={"Accept": "application/json"})
                logger.info(f"Registry API response: {response.status_code}")

                if response.status_code == 200:
                    patient = self._parse_response(response.json())
                    self._cache[fiscal_code] = (patient, datetime.now())
                    self._api_available = True
                    return patient
                elif response.status_code == 404:
                    self._cache[fiscal_code] = (None, datetime.now())
                    self._api_available = True
                    logger.info(f"Patient {fiscal_code} not found in Registry")
                    return None
                else:
                    logger.warning(f"Registry API returned status {response.status_code}")
                    return None

        except httpx.TimeoutException:
            logger.warning(f"Registry API timeout for {fiscal_code}")
            self._api_available = False
            return None
        except httpx.ConnectError as e:
            logger.warning(f"Registry API connection error: {e}")
            self._api_available = False
            return None
        except Exception as e:
            logger.error(f"Registry API error ({type(e).__name__}): {e}")
            self._api_available = False
            return None

    def is_available(self) -> Optional[bool]:
        return self._api_available

    def clear_cache(self):
        self._cache.clear()
