import json
import logging
import re
from typing import Optional

from fastapi import FastAPI, HTTPException, Depends, Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response as StarletteResponse
from openai import OpenAI

from .config import (
    OPENAI_API_KEY,
    MODEL_NAME,
    CHROMA_PERSIST_DIRECTORY,
    AURORA_DATA_PATH,
    PATIENT_DATA_SCHEMA,
    CHRONIC_CARE_DATA_PATH,
    REGISTRY_API_URL,
    REGISTRY_API_TIMEOUT,
    REGISTRY_API_ENABLED,
    BOF_API_URL,
    BOF_API_TOKEN,
    BOF_API_TIMEOUT,
    BOF_API_ENABLED,
    CONSOLIDATED_API_URL,
    CONSOLIDATED_API_TOKEN,
    CONSOLIDATED_API_TIMEOUT,
    CONSOLIDATED_API_ENABLED,
    get_config_summary
)
from app.schemas.ai.chats import ChatRequest, ChatResponse
from .vector_store import VectorStoreManager, create_rag_context
from .utils import get_system_prompt, get_chronic_care_system_prompt
from .services.registry_client import RegistryClient
from .services.bof_client import BOFClient
from .services.consolidated_client import ConsolidatedAPIClient
from .auth.database import get_pool, close_pool, get_db
from .auth.init_db import initialize_database
from .auth.router import router as auth_router
from .auth.admin_router import router as admin_router
from .auth.dependencies import require_clinical_or_admin, require_nurse, require_doctor
from .auth.audit import log_action

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Healthbridge Care API", version="3.0.0")

class ReflectOriginMiddleware(BaseHTTPMiddleware):
    """Reflects request Origin back — supports withCredentials on any port/domain."""
    async def dispatch(self, request: Request, call_next):
        origin = request.headers.get("origin")
        if request.method == "OPTIONS":
            response = StarletteResponse(status_code=204)
        else:
            response = await call_next(request)
        if origin:
            response.headers["Access-Control-Allow-Origin"] = origin
            response.headers["Access-Control-Allow-Credentials"] = "true"
            response.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, PATCH, DELETE, OPTIONS"
            response.headers["Access-Control-Allow-Headers"] = "Authorization, Content-Type, ngrok-skip-browser-warning"
            response.headers["Vary"] = "Origin"
        return response

app.add_middleware(ReflectOriginMiddleware)

app.include_router(auth_router, prefix="/auth", tags=["auth"])
app.include_router(admin_router, prefix="/admin", tags=["admin"])

client = OpenAI(api_key=OPENAI_API_KEY)

# RAG-based vector store as primary data source
vector_store: Optional[VectorStoreManager] = None


def build_system_prompt(patient_count: int) -> str:
    if PATIENT_DATA_SCHEMA == "chronic_care":
        return get_chronic_care_system_prompt(patient_count)
    return get_system_prompt(patient_count)

# External API clients for enrichment
registry_client: Optional[RegistryClient] = None
bof_client: Optional[BOFClient] = None

# Consolidated API client (AI1 via VPN) - when enabled, replaces Registry + BOF direct calls
consolidated_client: Optional[ConsolidatedAPIClient] = None


@app.on_event("startup")
async def startup_event():
    global vector_store, registry_client, bof_client, consolidated_client

    logger.info("Starting Healthbridge Care API v3.0 (RAG-based)")
    logger.info(f"Configuration: {json.dumps(get_config_summary(), indent=2)}")

    # Initialize PostgreSQL auth DB (creates tables + seeds admin if needed)
    try:
        pool = await get_pool()
        await initialize_database(pool)
        logger.info("Auth database initialized")
    except Exception as e:
        logger.error(f"Failed to initialize auth database: {e}")

    try:
        # Initialize Consolidated API client (AI1 via VPN)
        consolidated_client = ConsolidatedAPIClient(
            base_url=CONSOLIDATED_API_URL,
            token=CONSOLIDATED_API_TOKEN,
            timeout=CONSOLIDATED_API_TIMEOUT,
            enabled=CONSOLIDATED_API_ENABLED
        )

        if CONSOLIDATED_API_ENABLED:
            logger.info(f"Consolidated API enabled - enrichment via AI1 at {CONSOLIDATED_API_URL}")
        else:
            logger.info("Consolidated API disabled - using direct Registry and BOF APIs")

        # Initialize direct API clients (used when consolidated API is disabled)
        registry_client = RegistryClient(
            base_url=REGISTRY_API_URL,
            timeout=REGISTRY_API_TIMEOUT,
            enabled=REGISTRY_API_ENABLED and not CONSOLIDATED_API_ENABLED
        )

        bof_client = BOFClient(
            base_url=BOF_API_URL,
            token=BOF_API_TOKEN,
            timeout=BOF_API_TIMEOUT,
            enabled=BOF_API_ENABLED and not CONSOLIDATED_API_ENABLED
        )

        # Initialize RAG vector store
        data_path = CHRONIC_CARE_DATA_PATH if PATIENT_DATA_SCHEMA == "chronic_care" else AURORA_DATA_PATH
        logger.info(f"Initializing RAG vector store ({PATIENT_DATA_SCHEMA}) from: {data_path}")
        vector_store = VectorStoreManager(
            openai_client=client,
            persist_directory=CHROMA_PERSIST_DIRECTORY,
            aurora_data_path=AURORA_DATA_PATH,
            patient_data_schema=PATIENT_DATA_SCHEMA,
            chronic_care_data_path=CHRONIC_CARE_DATA_PATH
        )
        vector_store.initialize_collection()

        # Check if we need to rebuild the vector store
        current_count = vector_store.get_patient_count()
        expected_count = len(vector_store._patients)

        # Force rebuild to ensure new RAG structure is used
        needs_rebuild = current_count == 0 or current_count != expected_count

        # Also check if the vector store has the new structure (patient_json field)
        if not needs_rebuild and current_count > 0:
            try:
                sample = vector_store.collection.get(limit=1, include=["metadatas"])
                if sample['metadatas'] and 'patient_json' not in sample['metadatas'][0]:
                    logger.info("Vector store has old structure, forcing rebuild...")
                    needs_rebuild = True
            except Exception:
                needs_rebuild = True

        if needs_rebuild:
            logger.info(f"Building vector store: {expected_count} patients to index...")
            try:
                vector_store.clear_collection()
                indexed = vector_store.build_vector_store()
                logger.info(f"Vector store built with {indexed} patients")
            except Exception as embed_err:
                logger.warning(f"Failed to build embeddings: {embed_err}")
                logger.warning("RAG search will use in-memory fallback")
        else:
            logger.info(f"Vector store already contains {current_count} patients with correct structure")

        logger.info(f"Healthbridge Care API started - {vector_store.get_patient_count()} patients indexed")

    except Exception as e:
        logger.error(f"Failed to initialize services: {e}")


@app.get("/")
async def root():
    status = {"status": "healthy", "service": "Healthbridge Care API", "version": "3.0.0", "architecture": "RAG"}
    if vector_store:
        status["patients_indexed"] = vector_store.get_patient_count()
    return status


@app.get("/patients")
async def get_patients(current_user=Depends(require_clinical_or_admin)):
    if not vector_store:
        raise HTTPException(status_code=503, detail="Vector store not initialized")
    return vector_store.get_all_patients()


@app.get("/patients/{fiscal_code}")
async def get_patient(fiscal_code: str, current_user=Depends(require_clinical_or_admin)):
    if not vector_store:
        raise HTTPException(status_code=503, detail="Vector store not initialized")

    patient_data = vector_store.get_patient_by_fiscal_code(fiscal_code)
    if not patient_data:
        raise HTTPException(status_code=404, detail="Patient not found")

    enriched = await enrich_patient_data(fiscal_code, patient_data)
    return enriched


@app.get("/dashboard/nurse")
async def nurse_dashboard(current_user=Depends(require_nurse)):
    if not vector_store:
        raise HTTPException(status_code=503, detail="Vector store not initialized")

    patients = vector_store.get_all_chronic_care_patients()
    roster = []
    for p in patients:
        latest = p.get("latest_vitals") or {}
        adherence_flag = any(
            "missed" in med.get("adherence_notes", "").lower()
            or "inconsistent" in med.get("adherence_notes", "").lower()
            for med in p.get("medications", [])
        )
        roster.append({
            "patient_id": p["patient_id"],
            "full_name": p["full_name"],
            "conditions": p["conditions"],
            "assigned_doctor": p["assigned_doctor"],
            "latest_vitals_summary": latest,
            "vitals_history": p.get("vitals_history", []),
            "unresolved_alert_count": p["unresolved_alert_count"],
            "adherence_flag": adherence_flag,
        })

    roster.sort(key=lambda r: r["unresolved_alert_count"], reverse=True)
    return {"roster": roster}


@app.get("/dashboard/doctor")
async def doctor_dashboard(current_user=Depends(require_doctor)):
    if not vector_store:
        raise HTTPException(status_code=503, detail="Vector store not initialized")

    patients = vector_store.get_all_chronic_care_patients()
    overview = []
    for p in patients:
        high_severity_alerts = [a for a in p.get("alerts", []) if a.get("severity") == "high" and not a.get("resolved")]
        overview.append({
            "patient_id": p["patient_id"],
            "full_name": p["full_name"],
            "conditions": p["conditions"],
            "assigned_nurse": p["assigned_nurse"],
            "latest_vitals_summary": p.get("latest_vitals"),
            "vitals_history": p.get("vitals_history", []),
            "escalations": high_severity_alerts,
        })

    overview.sort(key=lambda o: len(o["escalations"]), reverse=True)
    return {"patients": overview}


async def enrich_patient_data(fiscal_code: str, patient_data: dict) -> dict:
    """Enrich patient data from vector store with external API data.

    Priority:
    1. Consolidated API (AI1 via VPN) - single call returns Registry + BOF + Aurora data
    2. Direct Registry API + BOF API calls (fallback, only when consolidated is disabled)
    """
    enriched = {
        **patient_data['patient'],
        'clinical_events': patient_data['events'],
        'sources': ['rag_vector_store']
    }

    # The chronic-care demo dataset is fully self-contained fictional data —
    # never call out to the real Registry/BOF/Consolidated APIs for it.
    if PATIENT_DATA_SCHEMA == "chronic_care":
        return enriched

    # Option 1: Use consolidated API (preferred - AI1 has internal access to everything)
    if consolidated_client and consolidated_client.enabled:
        consolidated_data = await consolidated_client.get_patient(fiscal_code)
        if consolidated_data:
            patient_info = consolidated_data.get('patient') or {}
            enriched['validated'] = True
            enriched['sources'].append('consolidated_api')

            # Merge demographics from consolidated DB (Registry is source of truth)
            for field in ['first_name', 'last_name', 'birth_date', 'sex',
                          'residence_address', 'domicile_address', 'email',
                          'primary_doctor_name', 'primary_doctor_email',
                          'disability_status', 'disability_details',
                          'cps_active', 'noa_sert_active',
                          'caregiver_name', 'caregiver_relationship', 'caregiver_phone',
                          'exemptions', 'phone_numbers']:
                if patient_info.get(field) is not None:
                    enriched[field] = patient_info[field]

            # Add clinical events from consolidated DB if richer than local data
            clinical_events = consolidated_data.get('clinical_events', [])
            if clinical_events:
                enriched['clinical_events_consolidated'] = clinical_events
                enriched['sources'].append('aurora_consolidated')

            # Add protected discharges from BOF (via consolidated)
            protected = consolidated_data.get('protected_discharges', [])
            if protected:
                enriched['protected_discharges'] = protected
                enriched['sources'].append('bof_consolidated')

        return enriched

    # Option 2: Direct API calls (used when consolidated API is disabled)
    if registry_client:
        registry_patient = await registry_client.get_patient(fiscal_code)
        if registry_patient:
            enriched['validated'] = True
            enriched['sources'].append('registry')
            if registry_patient.luogo_nascita:
                enriched['luogo_nascita'] = {
                    'comune': registry_patient.luogo_nascita.descrizione_comune,
                    'codice_istat': registry_patient.luogo_nascita.codice_istat_comune
                }
            if registry_patient.residenza:
                enriched['residenza'] = {
                    'comune': registry_patient.residenza.descrizione_comune,
                    'indirizzo': registry_patient.residenza.indirizzo
                }

    if bof_client:
        protected_discharges = await bof_client.get_protected_discharges(fiscal_code)
        if protected_discharges:
            enriched['protected_discharges'] = [pd.data for pd in protected_discharges if pd.data]
            enriched['sources'].append('bof')

    return enriched


def calculate_age(birth_date_str) -> Optional[int]:
    """Calculate exact age from birth_date string."""
    if not birth_date_str:
        return None
    try:
        from datetime import date
        if isinstance(birth_date_str, str):
            birth_date_str = birth_date_str[:10]  # take YYYY-MM-DD part
            bd = date.fromisoformat(birth_date_str)
        else:
            bd = birth_date_str
        today = date.today()
        return today.year - bd.year - ((today.month, today.day) < (bd.month, bd.day))
    except Exception:
        return None


def is_fiscal_code(text: str) -> bool:
    text = text.strip().upper()
    return len(text) == 16 and bool(re.match(r'^[A-Z0-9]{16}$', text))


def extract_fiscal_code(text: str) -> Optional[str]:
    match = re.search(r'\b([A-Z]{6}\d{2}[A-Z]\d{2}[A-Z]\d{3}[A-Z])\b', text.upper())
    if match:
        return match.group(1)
    match = re.search(r'\b([A-Z0-9]{16})\b', text.upper())
    if match:
        return match.group(1)
    return None


def detect_language(text: str) -> str:
    italian_keywords = [
        'dimmi', 'dammi', 'mostra', 'mostrami', 'puoi', 'potresti',
        'per favore', 'grazie', 'ciao', 'buongiorno', 'buonasera',
        'paziente', 'pazienti', 'informazioni'
    ]
    if any(kw in text.lower() for kw in italian_keywords):
        return 'it'
    return 'en'


def is_general_query(text: str) -> bool:
    """Detect if the query is about the system, services, or general information."""
    text_lower = text.lower()

    general_keywords = [
        'your service', 'your services', 'you provide', 'you offering', 'what do you do',
        'what can you', 'how can you help', 'help me', 'assist me',
        'i tuoi servizi', 'cosa fai', 'come puoi aiutarmi',
        'what services', 'quali servizi', 'your capabilities', 'le tue capacità',
        'hello', 'hi', 'ciao', 'buongiorno', 'buonasera'
    ]

    return any(kw in text_lower for kw in general_keywords)


def is_patient_query(text: str) -> bool:
    """Detect if the query is about patients (requires RAG search)."""
    text_lower = text.lower()

    if is_general_query(text_lower):
        return False

    # The chronic-care demo dataset has no fiscal codes and covers free-form
    # clinical questions ("is X worsening?", "who needs follow-up?") that don't
    # fit a fixed keyword list — default to a RAG search for anything that
    # isn't clearly a greeting/general-help query.
    if PATIENT_DATA_SCHEMA == "chronic_care":
        return True

    patient_keywords = [
        'patient', 'paziente', 'pazienti', 'patients',
        'tell me about', 'tell me something about', 'show me', 'mostrami', 'dimmi',
        'info about', 'information about', 'details about', 'data about',
        'who is', 'chi è', 'chi e',
        'fiscal code', 'codice fiscale',
        'clinical', 'clinico', 'diagnosis', 'diagnosi',
        'hospital', 'ospedale', 'visit', 'visita',
        'how many', 'quanti', 'list', 'lista', 'all', 'tutti'
    ]

    return any(kw in text_lower for kw in patient_keywords)


@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest, req: Request, current_user=Depends(require_clinical_or_admin), db=Depends(get_db)):
    """
    RAG-based chat endpoint.

    Flow:
    1. Extract fiscal code if present -> exact lookup from vector store
    2. If no fiscal code but patient query -> semantic RAG search
    3. General queries -> respond without patient data
    4. Enrich with external APIs when available
    """
    try:
        if not vector_store:
            raise HTTPException(status_code=503, detail="Vector store not initialized")

        logger.info(f"Received query: {request.message}")
        lang = detect_language(request.message)
        lang_instruction = "\n\n**IMPORTANT: Respond in ENGLISH.**" if lang == 'en' else "\n\n**IMPORTANTE: Rispondi in ITALIANO.**"

        # Extract fiscal code from message (if present)
        fiscal_code = None
        if is_fiscal_code(request.message):
            fiscal_code = request.message.strip().upper()
        else:
            fiscal_code = extract_fiscal_code(request.message)

        # Check if patient context was passed directly or is in conversation history
        active_patient_context = request.patient_context
        if not active_patient_context and request.conversation_history:
            for msg in reversed(request.conversation_history):
                if msg.patient_context:
                    active_patient_context = msg.patient_context
                    break

        # CASE 1: Fiscal code provided - go directly to consolidated API
        if fiscal_code:
            logger.info(f"Fiscal code detected: {fiscal_code} - querying consolidated API")

            enriched = None

            if consolidated_client and consolidated_client.enabled:
                consolidated_data = await consolidated_client.get_patient(fiscal_code)
                if consolidated_data and consolidated_data.get('patient_found'):
                    patient_info = consolidated_data.get('patient') or {}
                    enriched = {
                        **patient_info,
                        'clinical_events': consolidated_data.get('clinical_events', []),
                        'protected_discharges': consolidated_data.get('protected_discharges', []),
                        'prosthetics_items': consolidated_data.get('prosthetics_items', []),
                        'sources': ['consolidated_api']
                    }
                    enriched['age_years'] = calculate_age(patient_info.get('birth_date'))
                    logger.info(f"Patient {fiscal_code} found in consolidated API")
            else:
                # Fallback: try vector store if consolidated API is disabled
                patient_data = vector_store.get_patient_by_fiscal_code(fiscal_code)
                if patient_data:
                    enriched = await enrich_patient_data(fiscal_code, patient_data)

            if not enriched:
                error_msg = "Paziente non trovato nel database. Verifica il codice fiscale e riprova." if lang == 'it' else "Patient not found in the database. Please verify the fiscal code and try again."
                return ChatResponse(response=error_msg, patient_context=None)

            context = f"\n\n**Patient Data:**\n```json\n{json.dumps(enriched, ensure_ascii=False, indent=2)}\n```"

            messages = [{"role": "system", "content": build_system_prompt(vector_store.get_patient_count()) + lang_instruction + context}]
            for msg in request.conversation_history:
                messages.append({"role": msg.role, "content": msg.content})
            messages.append({"role": "user", "content": request.message})

            response = client.chat.completions.create(
                model=MODEL_NAME, messages=messages, temperature=0.3, max_tokens=1000
            )

            await log_action(
                db, current_user["id"], current_user["username"], "chat_query",
                ip=req.client.host if req.client else None,
                fiscal_code=fiscal_code,
                details={"message_preview": request.message[:100]}
            )

            return ChatResponse(response=response.choices[0].message.content, patient_context=enriched)

        # CASE 2: Follow-up question with existing patient context in conversation
        if active_patient_context and not fiscal_code:
            logger.info(f"Follow-up question detected - reusing patient context from conversation history")
            context = f"\n\n**Patient Data (from previous context):**\n```json\n{json.dumps(active_patient_context, ensure_ascii=False, indent=2)}\n```"
            messages = [{"role": "system", "content": build_system_prompt(vector_store.get_patient_count()) + lang_instruction + context}]
            for msg in request.conversation_history:
                messages.append({"role": msg.role, "content": msg.content})
            messages.append({"role": "user", "content": request.message})
            response = client.chat.completions.create(
                model=MODEL_NAME, messages=messages, temperature=0.3, max_tokens=1000
            )
            return ChatResponse(response=response.choices[0].message.content, patient_context=active_patient_context)

        # CASE 3: Patient query without fiscal code - semantic RAG search
        if is_patient_query(request.message):
            logger.info("Patient query detected - performing semantic RAG search")

            # Perform semantic search
            search_results = vector_store.search_patients(request.message, top_k=10)

            if search_results:
                # Get top result and enrich with external APIs
                best = search_results[0]
                confident_match = best['similarity'] >= 0.4
                if not confident_match and PATIENT_DATA_SCHEMA == "chronic_care":
                    # Names are the natural lookup key for this dataset — if the
                    # query explicitly names the top result's patient, trust it
                    # even when the embedding similarity score is borderline.
                    patient_name = (best['patient'].get('full_name') or '').lower()
                    if patient_name and patient_name in request.message.lower():
                        confident_match = True
                top_result = best if confident_match else None
                patient_context = None
                context = ""

                if top_result:
                    # Found a good match - enrich with external APIs
                    found_fiscal_code = top_result['codice_fiscale']
                    logger.info(f"Found patient {found_fiscal_code} via semantic search (similarity: {top_result['similarity']:.2%})")

                    # Enrich with Registry and BOF APIs
                    patient_data = {
                        'patient': top_result['patient'],
                        'events': top_result['events']
                    }
                    enriched = await enrich_patient_data(found_fiscal_code, patient_data)

                    patient_context = {
                        **enriched,
                        'similarity': top_result['similarity']
                    }

                    context = f"\n\n**Patient Data (from RAG + external APIs):**\n```json\n{json.dumps(enriched, ensure_ascii=False, indent=2)}\n```"
                else:
                    # Low confidence - show multiple options
                    context = create_rag_context(search_results, request.message)

                messages = [{"role": "system", "content": build_system_prompt(vector_store.get_patient_count()) + lang_instruction + context}]
                for msg in request.conversation_history:
                    messages.append({"role": msg.role, "content": msg.content})
                messages.append({"role": "user", "content": request.message})

                response = client.chat.completions.create(
                    model=MODEL_NAME, messages=messages, temperature=0.3, max_tokens=1000
                )

                return ChatResponse(response=response.choices[0].message.content, patient_context=patient_context)
            else:
                # No results found
                if PATIENT_DATA_SCHEMA == "chronic_care":
                    no_results_msg = "Non ho trovato pazienti corrispondenti. Prova con il nome completo del paziente." if lang == 'it' else "No matching patients found. Try using the patient's full name."
                else:
                    no_results_msg = "Non ho trovato pazienti corrispondenti. Prova con un codice fiscale specifico." if lang == 'it' else "No matching patients found. Please try with a specific fiscal code."
                return ChatResponse(response=no_results_msg, patient_context=None)

        # CASE 3: General query - respond without patient data
        logger.info("General query detected - responding without patient data")

        messages = [{"role": "system", "content": build_system_prompt(vector_store.get_patient_count()) + lang_instruction}]
        for msg in request.conversation_history:
            messages.append({"role": msg.role, "content": msg.content})
        messages.append({"role": "user", "content": request.message})

        response = client.chat.completions.create(
            model=MODEL_NAME, messages=messages, temperature=0.3, max_tokens=500
        )

        return ChatResponse(response=response.choices[0].message.content, patient_context=None)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in chat endpoint: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/search")
async def search_patients(query: str, top_k: int = 5, current_user=Depends(require_clinical_or_admin)):
    """
    RAG semantic search endpoint for patients.
    """
    if not vector_store:
        raise HTTPException(status_code=503, detail="Vector store not initialized")

    results = vector_store.search_patients(query, top_k=top_k)

    return {
        "query": query,
        "results": [
            {
                "codice_fiscale": r['codice_fiscale'],
                "nome": r['patient'].get('nome', ''),
                "cognome": r['patient'].get('cognome', ''),
                "similarity": r['similarity'],
                "event_count": len(r['events'])
            }
            for r in results
        ]
    }


@app.get("/status")
async def get_status():
    status = {"api": "healthy", "version": "3.0.0", "architecture": "RAG"}
    if vector_store:
        status["vector_store"] = {
            "initialized": True,
            "patient_count": vector_store.get_patient_count()
        }
    if consolidated_client and consolidated_client.enabled:
        status["consolidated_api"] = {
            "enabled": True,
            "url": CONSOLIDATED_API_URL,
            "available": consolidated_client.is_available()
        }
    else:
        if registry_client:
            status["registry_api"] = {"available": registry_client.is_available()}
        if bof_client:
            status["bof_api"] = {"available": bof_client.is_available()}
    return status
