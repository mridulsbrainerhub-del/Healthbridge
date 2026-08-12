from app.db.database import SessionLocal
from app.services.chronic_care_repo import ChronicCareRepository
from app.services.patient_query_service import PatientQueryService


db = SessionLocal()

try:
    repository = ChronicCareRepository(db)
    query_service = PatientQueryService(repository)

    results = query_service.find_by_condition("diabetes")

    print(results)

finally:
    db.close()