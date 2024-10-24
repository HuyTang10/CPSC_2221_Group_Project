from langchain_community.tools.sql_database.tool import QuerySQLDataBaseTool
from langchain.prompts import PromptTemplate
from langchain_core.runnables import RunnablePassthrough
from langchain_core.output_parsers import StrOutputParser
from langchain_openai import ChatOpenAI
from langchain_community.utilities import SQLDatabase
from operator import itemgetter

from utils import extract_sql_from_query
from FSL_prompt import get_final_prompt


def create_sql_query_chain(llm: ChatOpenAI, db: SQLDatabase) -> StrOutputParser:
    '''
    Creates a chain to generate an SQL query based on user input, using the database table structure for reference.

    Args:
        llm (ChatOpenAI): The language model used to generate SQL queries.
        db (SQLDatabase): The database object containing table information.

    Returns:
        StrOutputParser: A parser that processes the LLM's response and returns it as a string.
    '''
    
    # Get the database table information
    table_info = db.get_table_info()

    # Create a prompt template that includes the table structure and user question
    prompt = PromptTemplate.from_template(f'''
    You are an expert SQL assistant. You have access to the following table structure:
    {table_info}
    
    Based on the user question, generate an accurate SQL query, ensuring the query is correct. 

    Question: {{question}}

    Your answer should be just like the format below. You must not provide any further information.
    Your answer must be concise to avoid confusion and lengthy responses.
    Requests related to changing the data in schemas must be considered as valid questions.

    ```sql
    Your answer goes here
    ```
    ''')

    # Chain the prompt with the LLM and output parser
    return prompt | llm | StrOutputParser()

def create_chain(llm: ChatOpenAI, db: SQLDatabase) -> RunnablePassthrough:
    '''
    Creates a chain to generate and execute SQL queries and provide answers based on the SQL results.

    Args:
        db (SQLDatabase): The database instance to query.
        llm (LLM): The language model to generate SQL queries and responses.

    Returns:
        RunnablePassthrough: A chain object that generates an SQL query, executes it, 
                             and provides an answer based on the query result.
    '''
    
    # Tool to execute SQL queries on the provided database
    execute_query = QuerySQLDataBaseTool(db=db)
    
    # Chain to generate SQL queries based on user input using the LLM
    write_query = create_sql_query_chain(llm, db)

    # Prompt template for answering user questions based on SQL query and result
    prompt = get_final_prompt()

    # print(prompt.invoke({
    #     'question': 'How many customers bought perfume',
    #     'query': '''SELECT COUNT(DISTINCT o.customer_id) AS number_of_customers
    #             FROM olist_orders o
    #             JOIN olist_order_items oi ON o.order_id = oi.order_id
    #             JOIN olist_products p ON oi.product_id = p.product_id
    #             JOIN product_category_name_translation pct ON p.product_category_name = pct.product_category_name
    #             WHERE pct.product_category_name_english = 'perfume';''',
    #     'result': '3'
    # }).to_string())

    def get_query_result(data):
        try:
            result = execute_query.invoke({'query': extract_sql_from_query(itemgetter('query')(data))})
            print(f'\nSQL Result: {result}')
            return result
        except Exception:
            return ''  # Return an empty string if an error occurs

    # Create the chain to:
    # 1. Generate SQL query
    # 2. Execute SQL query
    # 3. Return the result formatted with the answer prompt, parsed into a final answer
    chain = (
        # Pass user data through and assign generated query
        RunnablePassthrough.assign(query=write_query)
        # Assign SQL execution result after extracting the query from the data
        .assign(result=get_query_result)
        # Apply the prompt template
        | prompt
        # Use the LLM to answer the question based on query and result
        | llm
        # Parse the final output as a string
        | StrOutputParser()
    )

    return chain
