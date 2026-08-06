from typing import List

from pydantic import BaseModel, Field


class LuogoNascita(BaseModel):
    codice_istat_comune: str | None = None
    descrizione_comune: str | None = None


class Indirizzo(BaseModel):
    codice_istat_comune: str | None = None
    descrizione_comune: str | None = None
    indirizzo: str | None = None


class RegistryPatient(BaseModel):
    codice_fiscale: str
    cognome: str
    nome: str
    data_nascita: str
    sesso: str

    idac: str | None = None
    luogo_nascita: LuogoNascita | None = None
    residenza: Indirizzo | None = None
    domicilio: Indirizzo | None = None


class ClinicalEvent(BaseModel):
    id_anag: str | None = None
    numero_episodio: str | None = None
    tipo_accesso: str | None = None
    data_accettazione: str | None = None
    data_dimissione: str | None = None
    struttura: str | None = None
    presidio: str | None = None
    diagnosi_acc: str | None = None


class ProtectedDischarge(BaseModel):
    data: dict | None = None


class UnifiedPatient(BaseModel):
    codice_fiscale: str
    cognome: str
    nome: str
    data_nascita: str
    sesso: str

    idac: str | None = None

    luogo_nascita: LuogoNascita | None = None
    residenza: Indirizzo | None = None
    domicilio: Indirizzo | None = None

    clinical_events: List[ClinicalEvent] = Field(default_factory=list)
    protected_discharges: List[ProtectedDischarge] = Field(default_factory=list)
    sources: List[str] = Field(default_factory=list)

    last_updated: str | None = None
    validated: bool = False

    def to_context_dict(self) -> dict:
        data = {
            "codice_fiscale": self.codice_fiscale,
            "cognome": self.cognome,
            "nome": self.nome,
            "data_nascita": self.data_nascita,
            "sesso": self.sesso,
            "validated": self.validated,
            "sources": self.sources,
        }

        if self.idac:
            data["idac"] = self.idac

        if self.luogo_nascita:
            data["luogo_nascita"] = {
                "comune": self.luogo_nascita.descrizione_comune,
                "codice_istat": self.luogo_nascita.codice_istat_comune,
            }

        if self.residenza:
            data["residenza"] = {
                "comune": self.residenza.descrizione_comune,
                "indirizzo": self.residenza.indirizzo,
                "codice_istat": self.residenza.codice_istat_comune,
            }

        if self.domicilio:
            data["domicilio"] = {
                "comune": self.domicilio.descrizione_comune,
                "indirizzo": self.domicilio.indirizzo,
                "codice_istat": self.domicilio.codice_istat_comune,
            }

        if self.clinical_events:
            data["clinical_events"] = [
                {
                    "tipo_accesso": event.tipo_accesso,
                    "numero_episodio": event.numero_episodio,
                    "data_accettazione": event.data_accettazione,
                    "data_dimissione": event.data_dimissione,
                    "struttura": event.struttura,
                    "presidio": event.presidio,
                    "diagnosi": event.diagnosi_acc,
                }
                for event in self.clinical_events
                if event.numero_episodio
            ]

        if self.protected_discharges:
            data["protected_discharges"] = [
                discharge.data
                for discharge in self.protected_discharges
                if discharge.data
            ]

        return data