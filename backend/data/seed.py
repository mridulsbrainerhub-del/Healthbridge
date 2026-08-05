import json
from datetime import date
from pathlib import Path

from sqlalchemy.orm import Session

from app.db.database import SessionLocal
from app.models.patient import Patient

JSON_FILE = Path(__file__).parent / "chronic-care-patients.json"


def main():
    db: Session = SessionLocal()

    try:
        with open(JSON_FILE, "r", encoding="utf-8") as file:
            data = json.load(file)

        patients = data["patients"]

        inserted = 0

        for patient_data in patients:
            # Skip duplicate patient_code if already present
            existing_patient = (
                db.query(Patient)
                .filter(Patient.patient_code == patient_data["patient_id"])
                .first()
            )

            if existing_patient:
                print(f"Skipping {patient_data['patient_id']} (already exists)")
                continue

            name_parts = patient_data["full_name"].split(" ", 1)

            first_name = name_parts[0]
            last_name = name_parts[1] if len(name_parts) > 1 else ""

            patient = Patient(
                patient_code=patient_data["patient_id"],
                first_name=first_name,
                last_name=last_name,
                date_of_birth=date.fromisoformat(
                    patient_data["date_of_birth"]
                ),
                sex=patient_data["sex"],
                phone=patient_data["contact"]["phone"],
                email=patient_data["contact"]["email"],
                address=patient_data["contact"]["address"],
                assigned_nurse=patient_data["assigned_nurse"],
                assigned_doctor=patient_data["assigned_doctor"],
                care_program=patient_data["care_program"],
                enrollment_date=date.fromisoformat(
                    patient_data["enrollment_date"]
                ),
            )

            db.add(patient)
            inserted += 1

        db.commit()

        print("\n==============================")
        print(f"Successfully inserted {inserted} patients.")
        print("==============================")

    except Exception as e:
        db.rollback()
        print(f"Error: {e}")

    finally:
        db.close()


if __name__ == "__main__":
    main()