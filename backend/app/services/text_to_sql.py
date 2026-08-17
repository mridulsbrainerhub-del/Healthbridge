from app.config import OPENAI_API_KEY, MODEL_NAME
from openai import OpenAI

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.db.database import Base

from app.utils import (
    get_sql_generation_prompt,
    get_sql_answer_prompt
)


client = OpenAI(api_key=OPENAI_API_KEY)


def get_database_schema() -> str:
    """
    Build a schema description from the existing
    SQLAlchemy models.

    This describes the database structure to the LLM.
    It does NOT load any patient data.
    """

    schema_parts = []

    for table in Base.metadata.sorted_tables:
        schema_parts.append(f"Table: {table.name}")

        schema_parts.append("Columns:")

        for column in table.columns:
            schema_parts.append(
                f"- {column.name} ({column.type})"
            )

        foreign_keys = []

        for column in table.columns:
            for foreign_key in column.foreign_keys:
                foreign_keys.append(
                    f"- {column.name} -> "
                    f"{foreign_key.target_fullname}"
                )

        if foreign_keys:
            schema_parts.append("Relationships:")
            schema_parts.extend(foreign_keys)

        schema_parts.append("")

    return "\n".join(schema_parts)


def generate_sql(user_question: str) -> str:
    schema = get_database_schema()

    system_prompt = get_sql_generation_prompt(schema)

    response = client.chat.completions.create(
        model=MODEL_NAME,
        messages=[
            {
                "role": "system",
                "content": system_prompt,
            },
            {
                "role": "user",
                "content": user_question,
            },
        ],
        temperature=0,
        max_tokens=500,
    )

    sql = response.choices[0].message.content

    if not sql:
        raise ValueError("LLM did not generate SQL.")

    sql = sql.strip()

    # Remove markdown code fences if the LLM adds them
    if sql.startswith("```sql"):
        sql = sql[6:]

    if sql.endswith("```"):
        sql = sql[:-3]

    return sql.strip()


def validate_sql(sql: str) -> bool:
    """
    Allow only a single read-only SELECT statement.
    """

    sql = sql.strip()

    if not sql:
        return False

    sql = sql.rstrip(";").strip()

    if not sql.upper().startswith("SELECT"):
        return False

    if ";" in sql:
        return False

    return True


def execute_sql(db: Session, sql: str):
    """
    Execute a validated read-only SQL query
    and return the result as Python data.
    """

    if not validate_sql(sql):
        raise ValueError(
            "Only read-only SELECT queries are allowed."
        )

    result = db.execute(text(sql))

    return [
        dict(row._mapping)
        for row in result
    ]


def generate_answer(
    user_question: str,
    sql_result: list,
) -> str:

    system_prompt = get_sql_answer_prompt()

    response = client.chat.completions.create(
        model=MODEL_NAME,
        messages=[
            {
                "role": "system",
                "content": system_prompt,
            },
            {
                "role": "user",
                "content": user_question,
            },
            {
                "role": "system",
                "content": f"Database result:\n{sql_result}",
            },
        ],
        temperature=0,
    )

    answer = response.choices[0].message.content

    if not answer:
        raise ValueError("LLM did not generate an answer.")

    return answer.strip()

if __name__ == "__main__":
    question = input("Enter your question: ")

    sql = generate_sql(question)

    print("\nGenerated SQL:")
    print(sql)