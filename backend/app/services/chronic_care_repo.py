# import json
# from typing import Any

# from sqlalchemy.orm import Session

# from app.models.patient import Patient
# from app.models.condition import Condition
# from app.models.allergy import Allergy
# from app.models.insurance import Insurance
# from app.models.medication import Medication
# from app.models.lab import Lab
# from app.models.alerts import Alert
# from app.models.visit import Visit
# from app.models.care_plan import CarePlan
# from app.models.vital import Vital


# class ChronicCareRepository:

#     def __init__(self, db: Session):
#         self.db = db

#     def get_all_patients(self) -> dict[str, dict[str, Any]]:
#         """
#         Load all chronic-care patient data from PostgreSQL.

#         Returns the same general dictionary structure that the
#         existing JSON-based chatbot expects.
#         """

#         patients = self.db.query(Patient).all()

#         result = {}

#         for patient in patients:
#             patient_id = patient.patient_code

#             patient_data = {
#                 "patient_id": patient.patient_code,
#                 "full_name": f"{patient.first_name} {patient.last_name}".strip(),
#                 "date_of_birth": (
#                     patient.date_of_birth.isoformat()
#                     if patient.date_of_birth
#                     else None
#                 ),
#                 "sex": patient.sex,
#                 "contact": {
#                     "phone": patient.phone,
#                     "email": patient.email,
#                     "address": patient.address,
#                 },
#                 "assigned_nurse": patient.assigned_nurse,
#                 "assigned_doctor": patient.assigned_doctor,
#                 "care_program": patient.care_program,
#                 "enrollment_date": (
#                     patient.enrollment_date.isoformat()
#                     if patient.enrollment_date
#                     else None
#                 ),
#             }

#             # --------------------------------
#             # Conditions
#             # --------------------------------

#             conditions = (
#                 self.db.query(Condition)
#                 .filter(Condition.patient_id == patient.id)
#                 .all()
#             )

#             patient_data["conditions"] = [
#                 condition.condition_name
#                 for condition in conditions
#             ]

#             # --------------------------------
#             # Allergies
#             # --------------------------------

#             allergies = (
#                 self.db.query(Allergy)
#                 .filter(Allergy.patient_id == patient.id)
#                 .all()
#             )

#             patient_data["allergies"] = [
#                 allergy.allergy_name
#                 for allergy in allergies
#             ]

#             # --------------------------------
#             # Insurance
#             # --------------------------------

#             insurance = (
#                 self.db.query(Insurance)
#                 .filter(Insurance.patient_id == patient.id)
#                 .first()
#             )

#             if insurance:
#                 patient_data["insurance"] = {
#                     "provider": insurance.provider,
#                     "policy_number": insurance.policy_number,
#                 }
#             else:
#                 patient_data["insurance"] = {}

#             # --------------------------------
#             # Medications
#             # --------------------------------

#             medications = (
#                 self.db.query(Medication)
#                 .filter(Medication.patient_id == patient.id)
#                 .all()
#             )

#             patient_data["medications"] = [
#                 {
#                     "name": medication.medication_name,
#                     "dose": medication.dosage,
#                     "frequency": medication.frequency,
#                     "adherence_notes": medication.adherence_notes,
#                 }
#                 for medication in medications
#             ]

#             # --------------------------------
#             # Labs
#             # --------------------------------

#             labs = (
#                 self.db.query(Lab)
#                 .filter(Lab.patient_id == patient.id)
#                 .all()
#             )

#             patient_data["labs"] = [
#                 {
#                     "date": (
#                         lab.test_date.isoformat()
#                         if lab.test_date
#                         else None
#                     ),
#                     "test": lab.test_name,
#                     "value": lab.value,
#                     "unit": lab.unit,
#                     "reference_range": lab.reference_range,
#                 }
#                 for lab in labs
#             ]

#             # --------------------------------
#             # Alerts
#             # --------------------------------

#             alerts = (
#                 self.db.query(Alert)
#                 .filter(Alert.patient_id == patient.id)
#                 .all()
#             )

#             patient_data["alerts"] = [
#                 {
#                     "date": (
#                         alert.created_at.date().isoformat()
#                         if alert.created_at
#                         else None
#                     ),
#                     "severity": alert.severity,
#                     "message": alert.message,
#                     "resolved": alert.resolved,
#                 }
#                 for alert in alerts
#             ]

#             # --------------------------------
#             # Visits
#             # --------------------------------

#             visits = (
#                 self.db.query(Visit)
#                 .filter(Visit.patient_id == patient.id)
#                 .all()
#             )

#             patient_data["visit_history"] = [
#                 {
#                     "date": (
#                         visit.visit_date.isoformat()
#                         if visit.visit_date
#                         else None
#                     ),
#                     "type": visit.visit_type,
#                     "summary": visit.summary,
#                 }
#                 for visit in visits
#             ]

#             # --------------------------------
#             # Care Plan
#             # --------------------------------

#             care_plan = (
#                 self.db.query(CarePlan)
#                 .filter(CarePlan.patient_id == patient.id)
#                 .first()
#             )

#             if care_plan:
#                 goals = []

#                 if care_plan.goals:
#                     try:
#                         parsed_goals = json.loads(care_plan.goals)

#                         if isinstance(parsed_goals, list):
#                             goals = parsed_goals
#                         else:
#                             goals = [care_plan.goals]

#                     except (json.JSONDecodeError, TypeError):
#                         goals = [care_plan.goals]

#                 patient_data["care_plan"] = {
#                     "goals": goals,
#                     "next_appointment": (
#                         care_plan.next_appointment.isoformat()
#                         if care_plan.next_appointment
#                         else None
#                     ),
#                 }
#             else:
#                 patient_data["care_plan"] = {}

#             # --------------------------------
#             # Vitals
#             # --------------------------------

#             vitals = (
#                 self.db.query(Vital)
#                 .filter(Vital.patient_id == patient.id)
#                 .order_by(Vital.recorded_at.asc())
#                 .all()
#             )

#             patient_data["vitals_history"] = []

#             for vital in vitals:

#                 blood_pressure = None

#                 if vital.systolic is not None and vital.diastolic is not None:
#                     blood_pressure = (
#                         f"{vital.systolic}/{vital.diastolic}"
#                     )

#                 patient_data["vitals_history"].append(
#                     {
#                         "date": (
#                             vital.recorded_at.date().isoformat()
#                             if vital.recorded_at
#                             else None
#                         ),
#                         "blood_pressure": blood_pressure,
#                         "heart_rate": vital.heart_rate,
#                         "glucose": (
#                             float(vital.glucose)
#                             if vital.glucose is not None
#                             else None
#                         ),
#                         "weight_kg": (
#                             float(vital.weight)
#                             if vital.weight is not None
#                             else None
#                         ),
#                         "spo2": vital.spo2,
#                         "notes": vital.notes,
#                     }
#                 )

#             result[patient_id] = patient_data

#         return result

#     def get_patient(
#         self,
#         patient_code: str
#     ) -> dict[str, Any] | None:
#         """
#         Load one patient and all related chronic-care data.
#         """

#         patients = self.get_all_patients()

#         return patients.get(patient_code)





#     def find_patients_by_condition(
#         self,
#         condition_name: str
#     ) -> dict[str, dict[str, Any]]:
#         """
#         Find patients who have a specific condition.

#         This is a read-only query.
#         """

#         conditions = (
#             self.db.query(Condition)
#             .filter(
#                 Condition.condition_name.ilike(
#                     f"%{condition_name}%"
#                 )
#             )
#             .all()
#         )

#         patient_ids = {
#             condition.patient_id
#             for condition in conditions
#         }

#         if not patient_ids:
#             return {}

#         patients = (
#             self.db.query(Patient)
#             .filter(Patient.id.in_(patient_ids))
#             .all()
#         )

#         result = {}

#         for patient in patients:
#             result[patient.patient_code] = {
#                 "patient_id": patient.patient_code,
#                 "full_name": (
#                     f"{patient.first_name} {patient.last_name}"
#                 ).strip(),
#                 "conditions": [
#                     condition.condition_name
#                     for condition in conditions
#                     if condition.patient_id == patient.id
#                 ],
#                 "assigned_nurse": patient.assigned_nurse,
#                 "assigned_doctor": patient.assigned_doctor,
#             }

#         return result




#     def find_patients_by_medication(
#         self,
#         medication_name: str
#     ) -> dict[str, dict[str, Any]]:
#         """
#         Find patients who are taking a specific medication.

#         This is a read-only query.
#         """

#         medications = (
#             self.db.query(Medication)
#             .filter(
#                 Medication.medication_name.ilike(
#                     f"%{medication_name}%"
#                 )
#             )
#             .all()
#         )

#         patient_ids = {
#             medication.patient_id
#             for medication in medications
#         }

#         if not patient_ids:
#             return {}

#         patients = (
#             self.db.query(Patient)
#             .filter(Patient.id.in_(patient_ids))
#             .all()
#         )

#         result = {}

#         for patient in patients:
#             patient_medications = [
#                 {
#                     "name": medication.medication_name,
#                     "dose": medication.dosage,
#                     "frequency": medication.frequency,
#                 }
#                 for medication in medications
#                 if medication.patient_id == patient.id
#             ]

#             result[patient.patient_code] = {
#                 "patient_id": patient.patient_code,
#                 "full_name": (
#                     f"{patient.first_name} {patient.last_name}"
#                 ).strip(),
#                 "medications": patient_medications,
#                 "assigned_nurse": patient.assigned_nurse,
#                 "assigned_doctor": patient.assigned_doctor,
#             }

#         return result





#     def find_patients_by_medication(
#             self,
#             medication_name: str
#         ) -> dict[str, dict[str, Any]]:
#             """
#             Find patients who are taking a specific medication.
#             Read-only query.
#             """

#             medications = (
#                 self.db.query(Medication)
#                 .filter(
#                     Medication.medication_name.ilike(
#                         f"%{medication_name}%"
#                     )
#                 )
#                 .all()
#             )

#             patient_ids = {
#                 medication.patient_id
#                 for medication in medications
#             }

#             if not patient_ids:
#                 return {}

#             patients = (
#                 self.db.query(Patient)
#                 .filter(Patient.id.in_(patient_ids))
#                 .all()
#             )

#             result = {}

#             for patient in patients:
#                 patient_medications = [
#                     {
#                         "name": medication.medication_name,
#                         "dose": medication.dosage,
#                         "frequency": medication.frequency,
#                     }
#                     for medication in medications
#                     if medication.patient_id == patient.id
#                 ]

#                 result[patient.patient_code] = {
#                     "patient_id": patient.patient_code,
#                     "full_name": (
#                         f"{patient.first_name} {patient.last_name}"
#                     ).strip(),
#                     "medications": patient_medications,
#                     "assigned_nurse": patient.assigned_nurse,
#                     "assigned_doctor": patient.assigned_doctor,
#                 }

#             return result


#     def find_patients_with_alerts(
#         self,
#         severity: str | None = None,
#         unresolved_only: bool = False
#     ) -> dict[str, dict[str, Any]]:
#         """
#         Find patients with alerts.

#         Optional filters:
#         - severity: low, medium, high
#         - unresolved_only: only unresolved alerts

#         Read-only query.
#         """

#         query = self.db.query(Alert)

#         if severity:
#             query = query.filter(
#                 Alert.severity.ilike(severity)
#             )

#         if unresolved_only:
#             query = query.filter(
#                 Alert.resolved.is_(False)
#             )

#         alerts = query.all()

#         patient_ids = {
#             alert.patient_id
#             for alert in alerts
#         }

#         if not patient_ids:
#             return {}

#         patients = (
#             self.db.query(Patient)
#             .filter(Patient.id.in_(patient_ids))
#             .all()
#         )

#         result = {}

#         for patient in patients:
#             patient_alerts = [
#                 {
#                     "date": (
#                         alert.created_at.date().isoformat()
#                         if alert.created_at
#                         else None
#                     ),
#                     "severity": alert.severity,
#                     "message": alert.message,
#                     "resolved": alert.resolved,
#                 }
#                 for alert in alerts
#                 if alert.patient_id == patient.id
#             ]

#             result[patient.patient_code] = {
#                 "patient_id": patient.patient_code,
#                 "full_name": (
#                     f"{patient.first_name} {patient.last_name}"
#                 ).strip(),
#                 "alerts": patient_alerts,
#                 "assigned_nurse": patient.assigned_nurse,
#                 "assigned_doctor": patient.assigned_doctor,
#             }

#         return result