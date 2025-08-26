from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import create_engine, text
import google.generativeai as genai
import re

# Set your Gemini API Key
genai.configure(api_key="AIzaSyDaVywEqMGTZPuQTCnk3NRuHVjKyy9bzx8")  # Replace with your actual Gemini API key

app = FastAPI()

# Allow frontend from localhost:5173
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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

# Clean Gemini output (remove ```sql blocks)
def clean_sql_output(text):
    # Remove ```sql ... ``` or ``` ... ``` markdown blocks
    cleaned = re.sub(r"```(?:sql)?\s*(.*?)\s*```", r"\1", text, flags=re.DOTALL)
    return cleaned.strip()

# Helper: Generate text using Gemini
def gemini_generate(system_prompt, user_prompt):
    model = genai.GenerativeModel("gemini-1.5-flash")
    chat = model.start_chat()
    response = chat.send_message(system_prompt + "\n" + user_prompt)
    raw_sql = response.text.strip()
    return clean_sql_output(raw_sql)

@app.post("/query")
async def query_db(request: Request):
    body = await request.json()
    prompt = body.get("prompt", "")
    conn_info = body.get("connection", {})

    if not prompt or not conn_info:
        return {"error": "Prompt or DB connection details missing."}

    try:
        engine = create_dynamic_engine(conn_info)

        # Step 1: Ask Gemini to extract table names
        table_extract_prompt = "Extract table names used in the prompt. Comma-separated, no explanation."
        tables_response = gemini_generate(table_extract_prompt, prompt)
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

        # Step 3: Ask Gemini to generate SQL from prompt and schema
        system_prompt = f"""You are a MySQL expert.
Use the schema below to write a valid SQL query for the user's prompt.

{schema}

Return only the SQL query. Do not return any explanations or markdown.
"""

        sql_query = gemini_generate(system_prompt, prompt)

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


