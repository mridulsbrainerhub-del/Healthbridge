import json
from pathlib import Path
from datetime import datetime


def load_patients():
    """
    Load patients from the JSON file.
    """
    current_file = Path(__file__).resolve()
    project_root = current_file.parents[2]

    json_path = project_root / "backend" / "data" / "patients.json"

    print("=" * 60)
    print("Current File :", current_file)
    print("Project Root :", project_root)
    print("JSON Path    :", json_path)
    print("File Exists? :", json_path.exists())
    print("=" * 60)

    if not json_path.exists():
        raise FileNotFoundError(f"Could not find {json_path}")

    with open(json_path, "r", encoding="utf-8") as file:
        data = json.load(file)

    print(f"\nSuccessfully loaded {len(data)} patients.\n")

    return data


def convert_date(date_string):
    """
    Convert DD/MM/YYYY -> date object.
    """
    if not date_string:
        return None

    return datetime.strptime(date_string, "%d/%m/%Y").date()


def transform_patient(patient):
    """
    Convert one patient from JSON format
    to the database format.
    """

    patient_data = {
        # Primary Key
        "fiscal_code": patient.get("Codice_fiscale"),

        # Demographics
        "first_name": patient.get("Nome"),
        "last_name": patient.get("Cognome"),
        "birth_date": convert_date(patient.get("Data_nascita")),
        "sex": patient.get("Sesso"),

        # Address
        "residence_address": patient.get("Residenza"),
        "domicile_address": patient.get("Domicilio"),

        # Contact
        "phone_numbers": [str(patient["Recapito_telefonico"])]
        if patient.get("Recapito_telefonico")
        else [],

        "email": patient.get("Email"),

        # Primary Doctor
        "primary_doctor_name": patient.get("MMG_nome"),
        "primary_doctor_email": patient.get("MMG_email"),

        # Exemptions (stored as JSONB later)
        "exemptions": [patient["Esenzioni"]]
        if patient.get("Esenzioni")
        else [],

        # Disability
        "disability_status": patient.get("Invalidita") not in [None, "", "No"],
        "disability_details": patient.get("Invalidita"),

        # Psychiatry
        "cps_active": patient.get("In_carico_psichiatria") == "Si",

        # Addiction Services
        "noa_sert_active": patient.get("In_carico_dipendenze") == "Si",

        # Caregiver
        "caregiver_name": patient.get("Caregiver_nome"),
        "caregiver_relationship": None,
        "caregiver_phone": None,
    }

    return patient_data


if __name__ == "__main__":
    patients = load_patients()

    first_patient = patients[0]

    transformed_patient = transform_patient(first_patient)

    print("Original Patient\n")
    print(json.dumps(first_patient, indent=4))

    print("\n" + "=" * 60)

    print("\nTransformed Patient\n")
    print(json.dumps(transformed_patient, indent=4, default=str))