import json
import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from openai import OpenAI

from ..config import (
    OPENAI_API_KEY,
    MODEL_NAME,
)
from ..schemas.ai.chats import ChatRequest, ChatResponse
from ..utils import get_chronic_care_system_prompt
from ..auth.dependencies import require_clinical_or_admin
from ..auth.audit import log_action
from ..db.database import SessionLocal
from ..services.chronic_care_repo import ChronicCareRepository
from ..services.patient_query_service import PatientQueryService


logger = logging.getLogger(__name__)


router = APIRouter(
    prefix="/chat",
    tags=["Chat"]
)


client = OpenAI(api_key=OPENAI_API_KEY)


# =========================================================
# LANGUAGE DETECTION
# =========================================================

def detect_language(text: str) -> str:

    italian_keywords = [
        "dimmi",
        "dammi",
        "mostra",
        "mostrami",
        "puoi",
        "potresti",
        "per favore",
        "grazie",
        "ciao",
        "buongiorno",
        "buonasera",
        "paziente",
        "pazienti",
        "informazioni",
    ]

    if any(
        keyword in text.lower()
        for keyword in italian_keywords
    ):
        return "it"

    return "en"


# =========================================================
# GENERAL QUERY DETECTION
# =========================================================

def is_general_query(text: str) -> bool:

    text_lower = text.lower()

    general_keywords = [
        "your service",
        "your services",
        "you provide",
        "you offering",
        "what do you do",
        "what can you",
        "how can you help",
        "help me",
        "assist me",
        "i tuoi servizi",
        "cosa fai",
        "come puoi aiutarmi",
        "what services",
        "quali servizi",
        "your capabilities",
        "le tue capacità",
        "hello",
        "hi",
        "ciao",
        "buongiorno",
        "buonasera",
    ]

    return any(
        keyword in text_lower
        for keyword in general_keywords
    )


# =========================================================
# SYSTEM PROMPT
# =========================================================

def build_system_prompt(patient_count: int) -> str:
    return get_chronic_care_system_prompt(patient_count)


# =========================================================
# FIND SPECIFIC PATIENT
# =========================================================

def find_patient_in_query(
    patients: dict,
    query: str,
) -> Optional[dict]:

    query_lower = query.lower()

    # First try patient code
    for patient in patients.values():

        patient_code = patient.get(
            "patient_id",
            ""
        ).lower()

        if (
            patient_code
            and patient_code in query_lower
        ):
            return patient

    # Then try full name
    for patient in patients.values():

        full_name = patient.get(
            "full_name",
            ""
        ).lower()

        if (
            full_name
            and full_name in query_lower
        ):
            return patient

    return None


# =========================================================
# LLM QUERY CLASSIFIER
# =========================================================

def classify_patient_query(query: str) -> dict:
    """
    Ask the LLM to classify a patient-data question.

    The LLM does NOT generate SQL.

    It only selects one of our approved
    read-only query types.
    """

    system_prompt = """
You classify healthcare patient-data questions.

You are NOT allowed to generate SQL.

Return ONLY valid JSON.

Allowed query types:

1. condition

{
    "query_type": "condition",
    "value": "condition name"
}

2. medication

{
    "query_type": "medication",
    "value": "medication name"
}

3. alert

{
    "query_type": "alert",
    "severity": "high|medium|low|null",
    "unresolved_only": true|false
}

4. none

{
    "query_type": "none"
}

Choose "none" if the question does not clearly
match one of the supported patient-data queries.

Examples:

User: Which patients have diabetes?

Output:
{"query_type":"condition","value":"diabetes"}

User: Who is taking insulin?

Output:
{"query_type":"medication","value":"insulin"}

User: Show me unresolved high severity alerts.

Output:
{"query_type":"alert","severity":"high","unresolved_only":true}

User: Hello

Output:
{"query_type":"none"}
"""

    response = client.chat.completions.create(
        model=MODEL_NAME,
        messages=[
            {
                "role": "system",
                "content": system_prompt,
            },
            {
                "role": "user",
                "content": query,
            },
        ],
        temperature=0,
        max_tokens=200,
    )

    content = response.choices[0].message.content

    if not content:
        return {
            "query_type": "none"
        }

    try:

        result = json.loads(content)

    except json.JSONDecodeError:

        logger.warning(
            "LLM returned invalid query classification: %s",
            content,
        )

        return {
            "query_type": "none"
        }

    allowed_types = {
        "condition",
        "medication",
        "alert",
        "none",
    }

    if result.get("query_type") not in allowed_types:

        return {
            "query_type": "none"
        }

    return result


# =========================================================
# CHAT ENDPOINT
# =========================================================

@router.post(
    "",
    response_model=ChatResponse
)
async def chat(
    request: ChatRequest,
    current_user=Depends(
        require_clinical_or_admin
    ),
):

    db = SessionLocal()

    try:

        logger.info(
            f"Received query: {request.message}"
        )

        # ---------------------------------------------------------
        # PostgreSQL repository + query service
        # ---------------------------------------------------------

        chronic_repo = ChronicCareRepository(db)

        query_service = PatientQueryService(
            chronic_repo
        )

        # IMPORTANT:
        # Load ALL patients here.
        #
        # We use this only for:
        # - counting patients
        # - finding a specific patient by name/code
        #
        # We do NOT send all of these patients
        # to the LLM for general patient queries.

        patients = chronic_repo.get_all_patients()

        patient_count = len(patients)

        logger.info(
            f"Loaded {patient_count} patients directly "
            f"from PostgreSQL"
        )

        # ---------------------------------------------------------
        # Language
        # ---------------------------------------------------------

        lang = detect_language(
            request.message
        )

        if lang == "en":

            lang_instruction = (
                "\n\n"
                "**IMPORTANT: Respond in ENGLISH.**"
            )

        else:

            lang_instruction = (
                "\n\n"
                "**IMPORTANTE: Rispondi in ITALIANO.**"
            )

        # ---------------------------------------------------------
        # Check previous patient context
        # ---------------------------------------------------------

        active_patient_context = (
            request.patient_context
        )

        if (
            not active_patient_context
            and request.conversation_history
        ):

            for msg in reversed(
                request.conversation_history
            ):

                if msg.patient_context:

                    active_patient_context = (
                        msg.patient_context
                    )

                    break

        # =========================================================
        # CASE 1: FOLLOW-UP QUESTION
        # =========================================================

        if active_patient_context:

            patient_context = (
                active_patient_context
            )

            context = (
                "\n\n"
                "**Patient Data (from PostgreSQL):**\n"
                "```json\n"
                + json.dumps(
                    patient_context,
                    ensure_ascii=False,
                    indent=2
                )
                + "\n```"
            )
            messages = [
                {
                    "role": "system",
                    "content": (
                        build_system_prompt(
                            patient_count
                        )
                        + lang_instruction
                        + context
                    ),
                }
            ]

            for msg in request.conversation_history:

                messages.append(
                    {
                        "role": msg.role,
                        "content": msg.content,
                    }
                )

            messages.append(
                {
                    "role": "user",
                    "content": request.message,
                }
            )

            response = (
                client.chat.completions.create(
                    model=MODEL_NAME,
                    messages=messages,
                    temperature=0.3,
                    max_tokens=1000,
                )
            )

            return ChatResponse(
                response=(
                    response
                    .choices[0]
                    .message
                    .content
                ),
                patient_context=patient_context,
            )

        # =========================================================
        # CASE 2: GENERAL QUESTION
        # =========================================================

        if is_general_query(
            request.message
        ):

            messages = [
                {
                    "role": "system",
                    "content": (
                        build_system_prompt(
                            patient_count
                        )
                        + lang_instruction
                    ),
                }
            ]

            for msg in request.conversation_history:

                messages.append(
                    {
                        "role": msg.role,
                        "content": msg.content,
                    }
                )

            messages.append(
                {
                    "role": "user",
                    "content": request.message,
                }
            )

            response = (
                client.chat.completions.create(
                    model=MODEL_NAME,
                    messages=messages,
                    temperature=0.3,
                    max_tokens=500,
                )
            )

            return ChatResponse(
                response=(
                    response
                    .choices[0]
                    .message
                    .content
                ),
                patient_context=None,
            )

        # =========================================================
        # CASE 3: SPECIFIC PATIENT
        # =========================================================

        patient = find_patient_in_query(
            patients,
            request.message,
        )

        if patient:

            logger.info(
                "Patient found directly from PostgreSQL: "
                f"{patient.get('patient_id')}"
            )

            context = (
                "\n\n"
                "**Patient Data (from PostgreSQL):**\n"
                "`json\n"
                + json.dumps(
                    patient,
                    ensure_ascii=False,
                    indent=2
                )
                + "\n```"
            )

            messages = [
                {
                    "role": "system",
                    "content": (
                        build_system_prompt(
                            patient_count
                        )
                        + lang_instruction
                        + context
                    ),
                }
            ]

            for msg in request.conversation_history:

                messages.append(
                    {
                        "role": msg.role,
                        "content": msg.content,
                    }
                )

            messages.append(
                {
                    "role": "user",
                    "content": request.message,
                }
            )

            response = (
                client.chat.completions.create(
                    model=MODEL_NAME,
                    messages=messages,
                    temperature=0.3,
                    max_tokens=1000,
                )
            )

            await log_action(
                db,
                current_user["id"],
                current_user["username"],
                "chat_query",
                details={
                    "message_preview": (
                        request.message[:100]
                    ),
                    "patient_id": patient.get(
                        "patient_id"
                    ),
                    "source": "postgresql",
                },
            )

            return ChatResponse(
                response=(
                    response
                    .choices[0]
                    .message
                    .content
                ),
                patient_context=patient,
            )

        # =========================================================
        # CASE 4: MULTI-PATIENT QUERY
        # =========================================================

        # Ask the LLM only to classify the question.
        # It does NOT access PostgreSQL.
        # It does NOT generate SQL.

        query_type = classify_patient_query(
            request.message
        )

        logger.info(
            f"Patient query classification: "
            f"{query_type}"
        )

        query_kind = query_type.get(
            "query_type"
        )

        query_results = {}

        # ---------------------------------------------------------
        # CONDITION QUERY
        # ---------------------------------------------------------

        if query_kind == "condition":

            condition = query_type.get(
                "value"
            )

            if condition:

                query_results = (
                    query_service.find_by_condition(
                        condition
                    )
                )

        # ---------------------------------------------------------
        # MEDICATION QUERY
        # ---------------------------------------------------------

        elif query_kind == "medication":

            medication = query_type.get(
                "value"
            )

            if medication:

                query_results = (
                    query_service.find_by_medication(
                        medication
                    )
                )

        # ---------------------------------------------------------
        # ALERT QUERY
        # ---------------------------------------------------------

        elif query_kind == "alert":

            severity = query_type.get(
                "severity"
            )

            unresolved_only = query_type.get(
                "unresolved_only",
                False,
            )

            query_results = (
                query_service.find_with_alerts(
                    severity=severity,
                    unresolved_only=unresolved_only,
                )
            )

        # ---------------------------------------------------------
        # NO MATCHING QUERY
        # ---------------------------------------------------------

        if not query_results:

            return ChatResponse(
                response=(
                    "I could not find any patients "
                    "matching that query."
                ),
                patient_context=None,
            )

        # ---------------------------------------------------------
        # Send ONLY the filtered PostgreSQL data
        # to the final LLM.
        # ---------------------------------------------------------

        context = (
                "\n\n"
                "**Relevant Patient Data (from PostgreSQL):**\n"
                "```json\n"
                + json.dumps(
                    query_results,
                    ensure_ascii=False,
                    indent=2
                )
                + "\n```"
            )

        messages = [
            {
                "role": "system",
                "content": (
                    build_system_prompt(
                        patient_count
                    )
                    + lang_instruction
                    + context
                ),
            }
        ]

        for msg in request.conversation_history:

            messages.append(
                {
                    "role": msg.role,
                    "content": msg.content,
                }
            )

        messages.append(
            {
                "role": "user",
                "content": request.message,
            }
        )

        response = (
            client.chat.completions.create(
                model=MODEL_NAME,
                messages=messages,
                temperature=0.3,
                max_tokens=1000,
            )
        )

        await log_action(
            db,
            current_user["id"],
            current_user["username"],
            "chat_query",
            details={
                "message_preview": (
                    request.message[:100]
                ),
                "query_type": query_kind,
                "source": "postgresql",
            },
        )

        return ChatResponse(
            response=(
                response
                .choices[0]
                .message
                .content
            ),
            patient_context=None,
        )

    # =========================================================
    # ERROR HANDLING
    # =========================================================

    except HTTPException:

        raise

    except Exception as e:

        logger.exception(
            "Error in chat endpoint"
        )

        raise HTTPException(
            status_code=500,
            detail=str(e),
        )

    finally:

        db.close()