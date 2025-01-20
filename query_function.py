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


# Get Connection to neon postgres
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

        return json.dumps({"result": str(tool_results), "sql-query": code})

    else:
        return {"error": "connection failed"}


def run_agent():
    with open(os.path.join(BASE_DIR, "templates", "agent_prompt.md")) as file:
        agent_prompt = file.read()

    messages = [
        {
            "role": "system",
            "content": agent_prompt.format(table_name="sales_revenue", user_query=""),
        },
    ]

    tools = [
        {
            "type": "function",
            "function": {
                "name": "query_tool",
                "description": "Query a database for finding specific information about the user's company products or financial metrics",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "The user question to find answer to",
                        }
                    },
                    "required": ["query"],
                },
            },
        }
    ]

    while True:
        user_query = input("\n> ")
        messages.append(
            {
                "role": "user",
                "content": agent_prompt.format(
                    table_name="sales_revenue", user_query=user_query
                ),
            }
        )

        response = client.chat.completions.create(
            stream=True,
            messages=messages,
            model="llama-3.2-90b-text-preview",
            tools=tools,
            tool_choice="auto",
        )

        chunked = ""
        tool_calls = []
        for chunk in response:
            print(chunk.choices[0].delta.content or "", end="")
            if chunk.choices[0].delta.content:
                chunked += chunk.choices[0].delta.content
            if chunk.choices[0].delta.tool_calls:
                tool_calls += chunk.choices[0].delta.tool_calls

        print("Tools info: ", tools)
        messages.append({"role": "assistant", "content": chunked})

        # messages.append(response_msg)
        if tool_calls:
            available_tools = {"query_tool": query_tool}

            for call in tool_calls:
                function_name = call.function.name
                funtion_to_call = available_tools[function_name]
                function_args = json.loads(call.function.arguments)

                function_response = funtion_to_call(function_args.get("query"))

                messages.append(
                    {
                        "role": "tool",
                        "name": function_name,
                        "content": function_response,
                        "tool_call_id": call.id,
                    }
                )

            followUp_response = client.chat.completions

            response = client.chat.completions.create(
                stream=True,
                messages=messages,
                model="llama-3.2-90b-text-preview",
            )

            chunked_again = ""
            for chunk in response:
                print(chunk.choices[0].delta.content or "", end="")
                if chunk.choices[0].delta.content:
                    chunked += chunk.choices[0].delta.content

            messages.append({"role": "assistant", "content": chunked_again})


# Run agent
# run_agent()
