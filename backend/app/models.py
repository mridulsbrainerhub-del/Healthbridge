# from pydantic import BaseModel
# from typing import List, Optional


# class ChatMessage(BaseModel):
#     role: str
#     content: str
#     patient_context: Optional[dict] = None


# class ChatRequest(BaseModel):
#     message: str
#     conversation_history: Optional[List[ChatMessage]] = []
#     patient_context: Optional[dict] = None


# class ChatResponse(BaseModel):
#     response: str
#     patient_context: Optional[dict] = None


# class LuogoNascita(BaseModel):
#     codice_istat_comune: Optional[str] = None
#     descrizione_comune: Optional[str] = None


# class Indirizzo(BaseModel):
#     codice_istat_comune: Optional[str] = None
#     descrizione_comune: Optional[str] = None
#     indirizzo: Optional[str] = None


# class RegistryPatient(BaseModel):
#     codice_fiscale: str
#     cognome: str
#     nome: str
#     data_nascita: str
#     sesso: str
#     idac: Optional[str] = None
#     luogo_nascita: Optional[LuogoNascita] = None
#     residenza: Optional[Indirizzo] = None
#     domicilio: Optional[Indirizzo] = None


# class ClinicalEvent(BaseModel):
#     id_anag: Optional[str] = None
#     numero_episodio: Optional[str] = None
#     tipo_accesso: Optional[str] = None
#     data_accettazione: Optional[str] = None
#     data_dimissione: Optional[str] = None
#     struttura: Optional[str] = None
#     presidio: Optional[str] = None
#     diagnosi_acc: Optional[str] = None


# class ProtectedDischarge(BaseModel):
#     data: Optional[dict] = None


# class UnifiedPatient(BaseModel):
#     codice_fiscale: str
#     cognome: str
#     nome: str
#     data_nascita: str
#     sesso: str
#     idac: Optional[str] = None
#     luogo_nascita: Optional[LuogoNascita] = None
#     residenza: Optional[Indirizzo] = None
#     domicilio: Optional[Indirizzo] = None
#     clinical_events: List[ClinicalEvent] = []
#     protected_discharges: List[ProtectedDischarge] = []
#     sources: List[str] = []
#     last_updated: Optional[str] = None
#     validated: bool = False

#     def to_context_dict(self) -> dict:
#         data = {
#             "codice_fiscale": self.codice_fiscale,
#             "cognome": self.cognome,
#             "nome": self.nome,
#             "data_nascita": self.data_nascita,
#             "sesso": self.sesso,
#             "validated": self.validated,
#             "sources": self.sources,
#         }

#         if self.idac:
#             data["idac"] = self.idac

#         if self.luogo_nascita:
#             data["luogo_nascita"] = {
#                 "comune": self.luogo_nascita.descrizione_comune,
#                 "codice_istat": self.luogo_nascita.codice_istat_comune
#             }

#         if self.residenza:
#             data["residenza"] = {
#                 "comune": self.residenza.descrizione_comune,
#                 "indirizzo": self.residenza.indirizzo,
#                 "codice_istat": self.residenza.codice_istat_comune
#             }

#         if self.domicilio:
#             data["domicilio"] = {
#                 "comune": self.domicilio.descrizione_comune,
#                 "indirizzo": self.domicilio.indirizzo,
#                 "codice_istat": self.domicilio.codice_istat_comune
#             }

#         if self.clinical_events:
#             data["clinical_events"] = [
#                 {
#                     "tipo_accesso": e.tipo_accesso,
#                     "numero_episodio": e.numero_episodio,
#                     "data_accettazione": e.data_accettazione,
#                     "data_dimissione": e.data_dimissione,
#                     "struttura": e.struttura,
#                     "presidio": e.presidio,
#                     "diagnosi": e.diagnosi_acc
#                 }
#                 for e in self.clinical_events if e.numero_episodio
#             ]

#         if self.protected_discharges:
#             data["protected_discharges"] = [pd.data for pd in self.protected_discharges if pd.data]

#         return data
