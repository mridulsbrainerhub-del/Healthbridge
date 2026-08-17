import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..schemas.ai.chats import ChatRequest, ChatResponse
from ..auth.dependencies import require_clinical_or_admin
from ..db.database import get_db

from ..services.text_to_sql import (
    generate_sql,
    validate_sql,
    execute_sql,
    generate_answer,
)


logger = logging.getLogger(__name__)


router = APIRouter(
    prefix="/chat",
    tags=["Chat"],
)


@router.post(
    "",
    response_model=ChatResponse,
)
async def chat(
    request: ChatRequest,
    current_user=Depends(require_clinical_or_admin),
    db: Session = Depends(get_db),
):
    try:
        logger.info(
            "Received chat query: %s",
            request.message,
        )

        # -------------------------------------------------
        # 1. Generate SQL using the LLM
        # -------------------------------------------------

        sql = generate_sql(request.message)

        logger.info(
            "Generated SQL: %s",
            sql,
        )

        # -------------------------------------------------
        # 2. Validate generated SQL
        # -------------------------------------------------

        if not validate_sql(sql):
            return ChatResponse(
                response=(
                    "I could not safely process that database query."
                )
            )

        # -------------------------------------------------
        # 3. Execute SQL against PostgreSQL
        # -------------------------------------------------

        sql_result = execute_sql(
            db,
            sql,
        )

        logger.info(
            "Database result: %s",
            sql_result,
        )

        # -------------------------------------------------
        # 4. Generate natural-language answer
        # -------------------------------------------------

        answer = generate_answer(
            request.message,
            sql_result,
        )

        # -------------------------------------------------
        # 5. Return response
        # -------------------------------------------------

        return ChatResponse(
            response=answer,
        )

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