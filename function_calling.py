import os, toml
from openai import OpenAI
import psycopg2
import json

BASE_DIR = os.path.dirname(__file__)
secrets = toml.load(os.path.join(BASE_DIR, "secrets.toml"))

client = OpenAI(
    api_key=secrets["GROQ_KEY"],
    base_url="https://api.groq.com/openai/v1",
)


# Get Connection
def get_connection():
    try:
        conn = psycopg2.connect(
            database="rio-db1",
            user="rio-query",
            password=secrets["DB_PASS"],
            host=secrets["DB_HOST"],
            port=5432,
        )

        print("> Connection succesful")
        return conn

    except:
        message = "ERROR: Couldn't connect to the database"
        print(message)
        return None


def query_db(SQL_Query, connection):
    # Execute query
    try:
        curr = connection.cursor()
        curr.execute(SQL_Query)
        data = curr.fetchall()

        return data  # List of tuples for rows

    except Exception as e:
        message = f"ERROR: {e}"
        print(message)
        return message


def query_tool(query):
    conn = get_connection()

    if conn:
        get_columns = """
            SELECT column_name
            FROM information_schema.columns
            WHERE table_name = 'sales_revenue'
            ORDER BY ordinal_position; 
        """

        get_firstRow = """
            SELECT * 
            FROM sales_revenue
            LIMIT 1;
            """

        columns = query_db(SQL_Query=get_columns, connection=conn)
        column_line = "Columns: " + " | ".join([i[0] for i in columns])

        first_row = query_db(SQL_Query=get_firstRow, connection=conn)
        firstRow = "First row: " + " | ".join(str(i) for i in first_row[0])

        meta_data = column_line + "\n" + firstRow

        with open(os.path.join(BASE_DIR, "templates", "sql_writer.md")) as file:
            prompt = file.read()

        messages = [
            {
                "role": "system",
                "content": prompt.format(
                    query=query, meta_data=meta_data, table_name="sales_revenue"
                ),
            }
        ]

        response = client.chat.completions.create(
            stream=False, messages=messages, model="llama-3.2-90b-text-preview"
        )

        response = response.choices[0].message.content

        code = response.replace("```sql", "").replace("```", "").strip()
        print("\nExecutable code: \n", code, end="\n\n")

        tool_results = query_db(SQL_Query=code, connection=conn)

        return json.dumps({"result": tool_results, "sql-query": code})

    else:
        return {"error": "connection failed"}


def agent(user_prompt):
    messages = [
        {
            "role": "system",
            "content": "You are a helpful chatbot that can answer natural language questions by querying a database",
        },
        {"role": "user", "content": user_prompt},
    ]

    tools = [
        {
            "type": "function",
            "function": {
                "name": "Query database",
                "description": "Takes a user request as input and query's the database to return relevant information to answer the user question",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "A segment of the user's question that specifies the information to be retrieved from the database.",
                        }
                    },
                    "required": ["query"],
                },
            },
        }
    ]

    response = client.chat.completions.create(
        stream=True, messages=messages, model="llama-3.2-90b-text-preview"
    )

    for chunk in response:
        print(chunk.choices[0].delta.content or "", end="")


# Tool creation


# Run

tool_results = query_tool(query="What is this about?")
print(tool_results)
