import json
from datetime import date, datetime
from pathlib import Path

from sqlalchemy.orm import Session

from app.db.database import SessionLocal
from app.models.patient import Patient
from app.models.condition import Condition
from app.models.allergy import Allergy
from app.models.insurance import Insurance
from app.models.medication import Medication
from app.models.lab import Lab
from app.models.alerts import Alert
from app.models.visit import Visit
from app.models.care_plan import CarePlan
from app.models.vital import Vital


JSON_FILE = Path(__file__).parent / "chronic-care-patients.json"


def parse_date(value):
    if not value:
        return None
    return date.fromisoformat(value)


def parse_datetime(value):
    if not value:
        return None

    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except Exception:
        return None


def split_blood_pressure(bp):
    if not bp:
        return None, None

    try:
        systolic, diastolic = bp.split("/")
        return int(systolic), int(diastolic)
    except Exception:
        return None, None


def main():
    db: Session = SessionLocal()

    try:
        with open(JSON_FILE, "r", encoding="utf-8") as file:
            data = json.load(file)

        patients = data["patients"]

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
                    f"Patient {patient_data['patient_id']} not found."
                )
                continue

            patient_id = patient.id


            insurance_data = patient_data.get("insurance")

            if insurance_data:
                existing_insurance = (
                    db.query(Insurance)
                    .filter(Insurance.patient_id == patient_id)
                    .first()
                )

                if existing_insurance is None:
                    insurance = Insurance(
                        patient_id=patient_id,
                        provider=insurance_data.get("provider"),
                        policy_number=insurance_data.get("policy_number"),
                    )

                    db.add(insurance)

            conditions = patient_data.get("conditions", [])

            for condition_name in conditions:

                existing_condition = (
                    db.query(Condition)
                    .filter(
                        Condition.patient_id == patient_id,
                        Condition.condition_name == condition_name,
                    )
                    .first()
                )

                if existing_condition:
                    continue

                condition = Condition(
                    patient_id=patient_id,
                    condition_name=condition_name,
                    status=True,
                )

                db.add(condition)

                
            allergies = patient_data.get("allergies", [])

            for allergy_name in allergies:

                existing_allergy = (
                    db.query(Allergy)
                    .filter(
                        Allergy.patient_id == patient_id,
                        Allergy.allergy_name == allergy_name,
                    )
                    .first()
                )

                if existing_allergy:
                    continue

                allergy = Allergy(
                    patient_id=patient_id,
                    allergy_name=allergy_name,
                )

                db.add(allergy)

            medications = patient_data.get("medications", [])

            for medication_data in medications:

                medication_name = medication_data.get("name")
                dosage = medication_data.get("dose")
                frequency = medication_data.get("frequency")
                adherence_notes = medication_data.get("adherence_notes")

                existing_medication = (
                    db.query(Medication)
                    .filter(
                        Medication.patient_id == patient_id,
                        Medication.medication_name == medication_name,
                    )
                    .first()
                )

                if existing_medication:
                    continue

                medication = Medication(
                    patient_id=patient_id,
                    medication_name=medication_name,
                    dosage=dosage,
                    frequency=frequency,
                    adherence_notes=adherence_notes,
                    start_date=None,
                    end_date=None,
                )

                db.add(medication)

            labs = patient_data.get("labs", [])

            for lab_data in labs:

                test_name = lab_data.get("test")
                test_date = parse_date(lab_data.get("date"))

                existing_lab = (
                    db.query(Lab)
                    .filter(
                        Lab.patient_id == patient_id,
                        Lab.test_name == test_name,
                        Lab.test_date == test_date,
                    )
                    .first()
                )

                if existing_lab:
                    continue

                lab = Lab(
                    patient_id=patient_id,
                    test_name=test_name,
                    value=lab_data.get("value"),
                    unit=lab_data.get("unit"),
                    reference_range=lab_data.get("reference_range"),
                    test_date=test_date,
                )

                db.add(lab)


            alerts = patient_data.get("alerts", [])

            for alert_data in alerts:

                existing_alert = (
                    db.query(Alert)
                    .filter(
                        Alert.patient_id == patient_id,
                        Alert.message == alert_data.get("message"),
                        Alert.created_at == parse_datetime(
                            alert_data.get("date")
                        ),
                    )
                    .first()
                )

                if existing_alert:
                    continue

                alert = Alert(
                    patient_id=patient_id,
                    severity=alert_data.get("severity"),
                    message=alert_data.get("message"),
                    resolved=alert_data.get("resolved", False),
                    created_at=parse_datetime(
                        alert_data.get("date")
                    ),
                )

                db.add(alert)


            visits = patient_data.get("visits", [])

            for visit_data in visits:

                existing_visit = (
                    db.query(Visit)
                    .filter(
                        Visit.patient_id == patient_id,
                        Visit.visit_date == parse_date(
                            visit_data.get("date")
                        ),
                        Visit.visit_type == visit_data.get("type"),
                    )
                    .first()
                )

                if existing_visit:
                    continue

                visit = Visit(
                    patient_id=patient_id,
                    visit_date=parse_date(
                        visit_data.get("date")
                    ),
                    visit_type=visit_data.get("type"),
                    summary=visit_data.get("summary"),
                )

                db.add(visit)

            care_plan_data = patient_data.get("care_plan")

            if care_plan_data:

                existing_care_plan = (
                    db.query(CarePlan)
                    .filter(
                        CarePlan.patient_id == patient_id
                    )
                    .first()
                )

                if existing_care_plan is None:

                    goals = care_plan_data.get("goals")

                    if isinstance(goals, list):
                        goals = "\n".join(goals)

                    care_plan = CarePlan(
                        patient_id=patient_id,
                        next_appointment=parse_date(
                            care_plan_data.get("next_appointment")
                        ),
                        goals=goals,
                    )

                    db.add(care_plan)

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

        db.commit()

        print("Data imported successfully.")

    except Exception:
        db.rollback()
        import traceback
        traceback.print_exc()
    finally:
        db.close()


if __name__ == "__main__":
    main()