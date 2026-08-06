import json
import logging
from typing import Optional, List, Dict, Any
from datetime import datetime
from pathlib import Path

from ..schemas.ai.registry import UnifiedPatient, ClinicalEvent
from .date_utils import normalize_oracle_date
from .registry_client import RegistryClient
from .bof_client import BOFClient

logger = logging.getLogger(__name__)


class PatientService:
    def __init__(self, aurora_data_path: str, registry_client: Optional[RegistryClient] = None,
                 bof_client: Optional[BOFClient] = None):
        self.aurora_data_path = aurora_data_path
        self.registry_client = registry_client
        self.bof_client = bof_client
        self._aurora_patients: Dict[str, Dict[str, Any]] = {}
        self._aurora_events: Dict[str, List[ClinicalEvent]] = {}
        self._unified_cache: Dict[str, UnifiedPatient] = {}
        self._load_aurora_data()
        logger.info(f"PatientService: loaded {len(self._aurora_patients)} patients")

    def _load_aurora_data(self):
        try:
            path = Path(self.aurora_data_path)
            if not path.exists():
                logger.error(f"Aurora data file not found: {self.aurora_data_path}")
                return

            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)

            if "results" in data and len(data["results"]) > 0:
                items = data["results"][0].get("items", [])
                self._parse_aurora_items(items)
        except Exception as e:
            logger.error(f"Failed to load Aurora data: {e}")

    def _parse_aurora_items(self, items: List[Dict[str, Any]]):
        for item in items:
            fiscal_code = item.get("cf", "").upper().strip()
            if not fiscal_code:
                continue

            if fiscal_code not in self._aurora_patients:
                self._aurora_patients[fiscal_code] = {
                    "codice_fiscale": fiscal_code,
                    "cognome": item.get("cognome", ""),
                    "nome": item.get("nome", ""),
                    "sesso": item.get("sesso", ""),
                    "data_nascita": normalize_oracle_date(item.get("data_nascita", "")),
                    "id_anag": item.get("id_anag", "")
                }
                self._aurora_events[fiscal_code] = []

            event = ClinicalEvent(
                id_anag=item.get("id_anag"),
                numero_episodio=item.get("numero_episodio"),
                tipo_accesso=item.get("tipo_accesso"),
                data_accettazione=normalize_oracle_date(item.get("data_accettazione", "")),
                data_dimissione=normalize_oracle_date(item.get("data_dimissione", "")) if item.get("data_dimissione") else None,
                struttura=item.get("struttura"),
                presidio=item.get("presidio"),
                diagnosi_acc=item.get("diagnosi_acc") if item.get("diagnosi_acc") else None
            )
            self._aurora_events[fiscal_code].append(event)

    def get_all_patients_summary(self) -> List[Dict[str, Any]]:
        summaries = []
        for cf, patient in self._aurora_patients.items():
            events = self._aurora_events.get(cf, [])
            summaries.append({
                "codice_fiscale": cf,
                "cognome": patient.get("cognome", ""),
                "nome": patient.get("nome", ""),
                "sesso": patient.get("sesso", ""),
                "data_nascita": patient.get("data_nascita", ""),
                "event_count": len(events),
                "last_event": events[-1].data_accettazione if events else None
            })
        return summaries

    def search_by_name(self, name: str) -> List[Dict[str, Any]]:
        name_lower = name.lower().strip()
        matches = []
        for cf, patient in self._aurora_patients.items():
            full_name = f"{patient.get('nome', '')} {patient.get('cognome', '')}".lower()
            if name_lower in full_name or full_name in name_lower:
                matches.append({
                    "codice_fiscale": cf,
                    "cognome": patient.get("cognome", ""),
                    "nome": patient.get("nome", ""),
                    "data_nascita": patient.get("data_nascita", ""),
                    "sesso": patient.get("sesso", "")
                })
        return matches

    async def build_unified_patient(self, fiscal_code: str) -> Optional[UnifiedPatient]:
        """
        Build unified patient following strict data flow:
        1. VALIDATE patient existence via Central Registry API (HARD GATE)
        2. Enrich with Aurora clinical events
        3. Enrich with BOF protected discharges

        If patient not found in Registry -> return None (no data)
        """
        fiscal_code = fiscal_code.upper().strip()

        if fiscal_code in self._unified_cache:
            return self._unified_cache[fiscal_code]

        # STEP 1: HARD GATE - Validate patient existence via Central Registry
        # Registry API is the SOURCE OF TRUTH for patient existence
        registry_patient = None
        if self.registry_client:
            registry_patient = await self.registry_client.get_patient(fiscal_code)

        if not registry_patient:
            # Patient not found in Central Registry = Patient does not exist
            logger.info(f"Patient {fiscal_code} not found in Central Registry - rejecting request")
            return None

        # STEP 2: Enrich with Aurora clinical events
        clinical_events = self._aurora_events.get(fiscal_code, [])

        # STEP 3: Enrich with BOF protected discharges
        protected_discharges = []
        if self.bof_client:
            protected_discharges = await self.bof_client.get_protected_discharges(fiscal_code)

        # Build sources list
        sources = ["registry"]
        if clinical_events:
            sources.append("aurora")
        if protected_discharges:
            sources.append("bof")

        # Build unified patient from Registry (source of truth) + enrichment data
        unified = UnifiedPatient(
            codice_fiscale=registry_patient.codice_fiscale,
            cognome=registry_patient.cognome,
            nome=registry_patient.nome,
            data_nascita=registry_patient.data_nascita,
            sesso=registry_patient.sesso,
            idac=registry_patient.idac,
            luogo_nascita=registry_patient.luogo_nascita,
            residenza=registry_patient.residenza,
            domicilio=registry_patient.domicilio,
            clinical_events=clinical_events,
            protected_discharges=protected_discharges,
            sources=sources,
            last_updated=datetime.now().isoformat(),
            validated=True  # Always true since we validated via Registry
        )

        self._unified_cache[fiscal_code] = unified
        return unified

    def patient_exists(self, fiscal_code: str) -> bool:
        return fiscal_code.upper().strip() in self._aurora_patients

    def get_patient_count(self) -> int:
        return len(self._aurora_patients)

    def get_all_fiscal_codes(self) -> List[str]:
        return list(self._aurora_patients.keys())

    def get_status(self) -> Dict[str, Any]:
        return {
            "aurora_patients": len(self._aurora_patients),
            "cached_unified": len(self._unified_cache),
            "registry_available": self.registry_client.is_available() if self.registry_client else None,
            "bof_available": self.bof_client.is_available() if self.bof_client else False
        }
