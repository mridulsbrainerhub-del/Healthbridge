import json
from datetime import datetime
from pathlib import Path

from sqlalchemy.orm import Session

from app.db.database import SessionLocal
from app.models.patient import Patient
from app.models.vital import Vital


JSON_FILE = Path(__file__).parent / "chronic-care-patients.json"


def main():
    db: Session = SessionLocal()

    try:
        with open(JSON_FILE, "r", encoding="utf-8") as file:
            data = json.load(file)

        patients = data["patients"]

        inserted = 0
        skipped = 0

        for patient_data in patients:

            patient = (
                db.query(Patient)
                .filter(
                    Patient.patient_code == patient_data["patient_id"]
                )
                .first()
            )

            if not patient:
                print(
                    f"Patient {patient_data['patient_id']} not found. Skipping."
                )
                continue

            patient_id = patient.id

            vitals = patient_data.get("vitals_history", [])

            for vital_data in vitals:

                blood_pressure = vital_data.get("blood_pressure")

                systolic = None
                diastolic = None

                if blood_pressure:
                    systolic, diastolic = map(
                        int,
                        blood_pressure.split("/")
                    )

                recorded_at = datetime.fromisoformat(
                    vital_data["date"] + "T00:00:00"
                )

                existing_vital = (
                    db.query(Vital)
                    .filter(
                        Vital.patient_id == patient_id,
                        Vital.recorded_at == recorded_at,
                    )
                    .first()
                )

                if existing_vital:
                    skipped += 1
                    continue

                vital = Vital(
                    patient_id=patient_id,
                    recorded_at=recorded_at,
                    systolic=systolic,
                    diastolic=diastolic,
                    heart_rate=vital_data.get("heart_rate"),
                    glucose=vital_data.get("glucose"),
                    weight=vital_data.get("weight_kg"),
                    spo2=vital_data.get("spo2"),
                    notes=vital_data.get("notes"),
                )

                db.add(vital)
                inserted += 1

        db.commit()

        print("==============================")
        print(f"Vitals inserted: {inserted}")
        print(f"Vitals skipped:  {skipped}")
        print("==============================")

    except Exception:
        db.rollback()
        raise

    finally:
        db.close()


if __name__ == "__main__":
    main()