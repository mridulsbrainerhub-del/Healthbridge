from typing import Any

from .chronic_care_repo import ChronicCareRepository


class PatientQueryService:

    def __init__(self, repository: ChronicCareRepository):
        self.repository = repository

    def find_by_condition(
        self,
        condition: str
    ) -> dict[str, dict[str, Any]]:
        """
        Find patients by medical condition.
        Read-only operation.
        """
        return self.repository.find_patients_by_condition(condition)

    def find_by_medication(
        self,
        medication: str
    ) -> dict[str, dict[str, Any]]:
        """
        Find patients by medication.
        Read-only operation.
        """
        return self.repository.find_patients_by_medication(medication)

    def find_with_alerts(
        self,
        severity: str | None = None,
        unresolved_only: bool = False
    ) -> dict[str, dict[str, Any]]:
        """
        Find patients with alerts.
        Read-only operation.
        """
        return self.repository.find_patients_with_alerts(
            severity=severity,
            unresolved_only=unresolved_only
        )