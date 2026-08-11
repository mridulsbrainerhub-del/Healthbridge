from app.db.database import SessionLocal
from app.services.chronic_care_repo import ChronicCareRepository


def main():
    db = SessionLocal()

    try:
        repository = ChronicCareRepository(db)

        patients = repository.get_all_patients()

        print("=" * 50)
        print(f"Patients loaded from PostgreSQL: {len(patients)}")
        print("=" * 50)

        for patient_id, patient in patients.items():

            print(f"\nPatient: {patient['full_name']}")
            print(f"ID: {patient_id}")
            print(f"Conditions: {len(patient['conditions'])}")
            print(f"Allergies: {len(patient['allergies'])}")
            print(f"Medications: {len(patient['medications'])}")
            print(f"Labs: {len(patient['labs'])}")
            print(f"Vitals: {len(patient['vitals_history'])}")
            print(f"Alerts: {len(patient['alerts'])}")
            print(f"Visits: {len(patient['visit_history'])}")

    finally:
        db.close()


if __name__ == "__main__":
    main()