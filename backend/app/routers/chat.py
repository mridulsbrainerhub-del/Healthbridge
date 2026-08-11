import json
import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException

from openai import OpenAI

from ..config import (
    OPENAI_API_KEY,
    MODEL_NAME,
    PATIENT_DATA_SCHEMA,
)
from ..schemas.ai.chats import ChatRequest, ChatResponse
from ..utils import get_chronic_care_system_prompt
from ..auth.dependencies import require_clinical_or_admin
from ..auth.audit import log_action
from ..db.database import SessionLocal
from ..services.chronic_care_repo import ChronicCareRepository


logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/chat",
    tags=["Chat"]
)

client = OpenAI(api_key=OPENAI_API_KEY)


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

    if any(keyword in text.lower() for keyword in italian_keywords):
        return "it"

    return "en"


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

    return any(keyword in text_lower for keyword in general_keywords)


def build_system_prompt(patient_count: int) -> str:
    return get_chronic_care_system_prompt(patient_count)


def find_patient_in_query(
    patients: dict,
    query: str,
) -> Optional[dict]:

    query_lower = query.lower()

    # First try patient code
    for patient in patients.values():
        patient_code = patient.get("patient_id", "").lower()

        if patient_code and patient_code in query_lower:
            return patient

    # Then try full name
    for patient in patients.values():
        full_name = patient.get("full_name", "").lower()

        if full_name and full_name in query_lower:
            return patient

    return None


@router.post("", response_model=ChatResponse)
async def chat(
    request: ChatRequest,
    current_user=Depends(require_clinical_or_admin),
):
    db = SessionLocal()
    try:
        logger.info(f"Received query: {request.message}")

        # ---------------------------------------------------------
        # Get patient data directly from PostgreSQL
        # ---------------------------------------------------------

        chronic_repo = ChronicCareRepository(db)

        patients = chronic_repo.get_all_patients()

        patient_count = len(patients)

        logger.info(
            f"Loaded {patient_count} patients directly from PostgreSQL"
        )

        # ---------------------------------------------------------
        # Language
        # ---------------------------------------------------------

        lang = detect_language(request.message)

        if lang == "en":
            lang_instruction = (
                "\n\n**IMPORTANT: Respond in ENGLISH.**"
            )
        else:
            lang_instruction = (
                "\n\n**IMPORTANTE: Rispondi in ITALIANO.**"
            )

        # ---------------------------------------------------------
        # Check previous patient context
        # ---------------------------------------------------------

        active_patient_context = request.patient_context

        if (
            not active_patient_context
            and request.conversation_history
        ):
            for msg in reversed(request.conversation_history):
                if msg.patient_context:
                    active_patient_context = msg.patient_context
                    break

        # ---------------------------------------------------------
        # CASE 1: Follow-up question
        # ---------------------------------------------------------

        if active_patient_context:
            patient_context = active_patient_context

            context = (
                "\n\n**Patient Data (from PostgreSQL):**\n"
                "```json\n"
                f"{json.dumps(patient_context, ensure_ascii=False, indent=2)}"
                "\n```"
            )

            messages = [
                {
                    "role": "system",
                    "content": (
                        build_system_prompt(patient_count)
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

            response = client.chat.completions.create(
                model=MODEL_NAME,
                messages=messages,
                temperature=0.3,
                max_tokens=1000,
            )

            return ChatResponse(
                response=response.choices[0].message.content,
                patient_context=patient_context,
            )

        # ---------------------------------------------------------
        # CASE 2: General question
        # ---------------------------------------------------------

        if is_general_query(request.message):

            messages = [
                {
                    "role": "system",
                    "content": (
                        build_system_prompt(patient_count)
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

            response = client.chat.completions.create(
                model=MODEL_NAME,
                messages=messages,
                temperature=0.3,
                max_tokens=500,
            )

            return ChatResponse(
                response=response.choices[0].message.content,
                patient_context=None,
            )

        # ---------------------------------------------------------
        # CASE 3: Find patient directly in PostgreSQL data
        # ---------------------------------------------------------

        patient = find_patient_in_query(
            patients,
            request.message,
        )

        if patient:

            logger.info(
                f"Patient found directly from PostgreSQL: "
                f"{patient.get('patient_id')}"
            )

            context = (
                "\n\n**Patient Data (directly from PostgreSQL):**\n"
                "```json\n"
                f"{json.dumps(patient, ensure_ascii=False, indent=2)}"
                "\n```"
            )

            messages = [
                {
                    "role": "system",
                    "content": (
                        build_system_prompt(patient_count)
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

            response = client.chat.completions.create(
                model=MODEL_NAME,
                messages=messages,
                temperature=0.3,
                max_tokens=1000,
            )

            await log_action(
                db,
                current_user["id"],
                current_user["username"],
                "chat_query",
                details={
                    "message_preview": request.message[:100],
                    "patient_id": patient.get("patient_id"),
                    "source": "postgresql",
                },
            )

            return ChatResponse(
                response=response.choices[0].message.content,
                patient_context=patient,
            )

        # ---------------------------------------------------------
        # CASE 4: No specific patient found
        # ---------------------------------------------------------

        # For questions involving multiple patients, give the LLM
        # the complete PostgreSQL dataset.

        context = (
            "\n\n**Patient Data (directly from PostgreSQL):**\n"
            "```json\n"
            f"{json.dumps(patients, ensure_ascii=False, indent=2)}"
            "\n```"
        )

        messages = [
            {
                "role": "system",
                "content": (
                    build_system_prompt(patient_count)
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

        response = client.chat.completions.create(
            model=MODEL_NAME,
            messages=messages,
            temperature=0.3,
            max_tokens=1000,
        )

        return ChatResponse(
            response=response.choices[0].message.content,
            patient_context=None,
        )

    except HTTPException:
        raise

    except Exception as e:
        logger.exception("Error in chat endpoint")

        raise HTTPException(
            status_code=500,
            detail=str(e),
        )