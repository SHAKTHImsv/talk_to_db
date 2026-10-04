from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import create_engine, text
from groq import Groq
from dotenv import load_dotenv
from pathlib import Path
import os
import re

# Load secrets from the .env file at the project root (values in .env take precedence)
load_dotenv(Path(__file__).resolve().parent.parent / ".env", override=True)

GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")
GROQ_MODEL = os.environ.get("GROQ_MODEL", "meta-llama/llama-prompt-guard-2-22m")

app = FastAPI()

# Allow frontend from localhost:5173
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
async def root():
    return {
        "status": "ok",
        "message": "AI SQL Assistant API is running"
    }

# Create engine from user's connection details
def create_dynamic_engine(conn):
    try:
        db_url = (
            f"mysql+pymysql://{conn['user']}:{conn['password']}"
            f"@{conn['host']}:{conn['port']}/{conn['database']}"
        )
        return create_engine(db_url)
    except Exception as e:
        raise ValueError(f"Invalid connection: {e}")

# Clean Groq output (remove ```sql blocks)
def clean_sql_output(text):
    # Remove ```sql ... ``` or ``` ... ``` markdown blocks
    cleaned = re.sub(r"```(?:sql)?\s*(.*?)\s*```", r"\1", text, flags=re.DOTALL)
    return cleaned.strip()

# Helper: Generate text using Groq
def groq_generate(system_prompt, user_prompt):
    if not GROQ_API_KEY:
        raise ValueError("GROQ_API_KEY environment variable is not set.")
    client = Groq(api_key=GROQ_API_KEY)
    response = client.chat.completions.create(
        model=GROQ_MODEL,
        messages=[
            # Prompt Guard only accepts a single user message (400 otherwise),
            # so system + user are combined like the original Gemini call
            {"role": "user", "content": f"{system_prompt}\n{user_prompt}"},
        ],
    )
    raw_sql = response.choices[0].message.content.strip()
    return clean_sql_output(raw_sql)

# Prompt Guard outputs a malicious-score (0.0-1.0) instead of text;
# returns the score if the model output is one, else None
def parse_score(text):
    match = re.fullmatch(r"(0\.\d+|1\.0+)", text.strip())
    return float(match.group(1)) if match else None

@app.post("/query")
async def query_db(request: Request):
    body = await request.json()
    prompt = body.get("prompt", "")
    conn_info = body.get("connection", {})

    if not prompt or not conn_info:
        return {"error": "Prompt or DB connection details missing."}

    try:
        engine = create_dynamic_engine(conn_info)

        # Step 1: Ask Groq to extract table names
        table_extract_prompt = "Extract table names used in the prompt. Comma-separated, no explanation."
        tables_response = groq_generate(table_extract_prompt, prompt)

        # If the model is a classifier (Prompt Guard), it returns a score, not tables
        score = parse_score(tables_response)
        if score is not None:
            if score >= 0.5:
                return {"error": f"Prompt blocked: prompt injection suspected (score {score:.4f})."}
            return {
                "error": (
                    f"Prompt screened as safe (score {score:.4f}), but {GROQ_MODEL} is a "
                    "classifier and cannot generate SQL. Set GROQ_MODEL=llama-3.1-8b-instant "
                    "in .env to enable SQL generation."
                )
            }

        tables = [t.strip() for t in tables_response.split(",") if t.strip()]

        # Step 2: Fetch schema from MySQL
        schema_parts = []
        with engine.begin() as conn:
            for table in tables:
                try:
                    rows = conn.execute(text(f"DESCRIBE {table}")).fetchall()
                    columns = [f"{row[0]} {row[1]}" for row in rows]
                    schema_parts.append(f"{table}({', '.join(columns)})")
                except Exception as e:
                    return {"error": f"Schema error for '{table}': {e}"}

        schema = "\n".join(schema_parts)

        # Step 3: Ask Groq to generate SQL from prompt and schema
        system_prompt = f"""You are a MySQL expert.
Use the schema below to write a valid SQL query for the user's prompt.

{schema}

Return only the SQL query. Do not return any explanations or markdown.
"""

        sql_query = groq_generate(system_prompt, prompt)

        # Step 4: Execute the SQL query
        with engine.begin() as conn:
            result = conn.execute(text(sql_query))
            if sql_query.strip().lower().startswith("select"):
                rows = [dict(row._mapping) for row in result]
                return {"sql": sql_query, "data": rows}
            else:
                return {"sql": sql_query, "message": f"{result.rowcount} rows affected."}

    except Exception as e:
        return {"error": f"Server error: {e}"}



