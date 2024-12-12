import os
import io
import re
import jwt
import json
import uuid
import hmac
import boto3
import base64
import PyPDF2
import hashlib
import logging
import tiktoken
import datetime
from PIL import Image
from typing import Any
from openai import OpenAI
from dotenv import load_dotenv
from unidecode import unidecode
from datetime import timezone, timedelta
from fastapi import status, HTTPException, Depends
from fastapi.security import OAuth2PasswordBearer
from fastapi.responses import JSONResponse
from snowflake.connector import DictCursor
from connectDB import create_connection_to_snowflake, close_connection

# RAG Specific Imports
from cleanlab_studio import Studio
from langchain_chroma import Chroma
from langchain_openai import ChatOpenAI
from langchain.storage import InMemoryStore
from langchain_core.documents import Document
from langchain_openai import OpenAIEmbeddings
from langchain_core.messages import HumanMessage
from unstructured.partition.pdf import partition_pdf
from langchain_nvidia_ai_endpoints import ChatNVIDIA
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain.retrievers.multi_vector import MultiVectorRetriever
from langchain_core.runnables import RunnableLambda, RunnablePassthrough
import unstructured_pytesseract as pytesseract

# Load env variables
load_dotenv()


# logging.basicConfig(level = logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
# logger = logging.getLogger(__name__)

# Logger configuration
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")

# Log to console (dev only)
if os.getenv('APP_ENV') == "development":
    handler = logging.StreamHandler()
    handler.setFormatter(formatter)
    logger.addHandler(handler)

# Also log to a file
file_handler = logging.FileHandler(os.getenv('FASTAPI_LOG_FILE', "fastapi_errors.log"))
file_handler.setFormatter(formatter)
logger.addHandler(file_handler) 

# Secret key
SECRET_KEY = os.getenv("SECRET_KEY")

# OAuth2 scheme
oauth2_scheme = OAuth2PasswordBearer(tokenUrl = 'login', auto_error = False)

# Function to hash password
def get_password_hash(password: str) -> str:
    logger.info(f"FASTAPI Services - get_password_hash() - Hashing the given password")
    hash_hex = None

    # Convert secret_key, password to bytes for hashing
     # Create HMAC hash object using secret key and password - Generate hex digest of the hash
    try:
        secret_key = SECRET_KEY.encode()
        hash_object = hmac.new(secret_key, msg=password.encode(), digestmod=hashlib.sha256)
        hash_hex = hash_object.hexdigest()
        return hash_hex
    except Exception as e:
        logger.info(f"FASTAPI Services Error - get_password_hash() - encountered an error: {e}")


# Helper function to create a JWT token with an expiration time
def create_jwt_token(data: dict) -> dict[str, Any]:
    logger.info(f"FASTAPI Services - create_jwt_token() - Create a JWT token with an expiration time")
    
    # Set token expiration time to 'x' minutes from the current time
    expiration = datetime.datetime.now(timezone.utc) + timedelta(minutes=60)
    
    # Create the token payload with expiration and provided data
    token_payload = {
        "expiration": str(expiration), 
        **data
    }
    
   # Encode the payload using the secret key and HS256 algorithm to create the token
    token = jwt.encode(token_payload, SECRET_KEY, algorithm="HS256")
    
    token_dict = {
        'token'         : token,
        'token_type'    : "Bearer"
    }
    logger.info(f"FASTAPI Services - create_jwt_token() - JWT Token created with payload")
    return token_dict


# Function to decode the JWT token and verify its validity
def decode_jwt_token(token: str):
    logger.info(f"FASTAPI Services - decode_jwt_token() - Decode JWT token & Validation")
    try:
        # Decode the JWT token
        decoded_token = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
        logger.info(f"FASTAPI Services - decode_jwt_token() - Decoded JWT token successfully")
        return decoded_token
    
    except Exception as e:
        logger.error(f"FASTAPI Services Error - decode_jwt_token() encountered an error: {e}")  
        raise HTTPException(
            status_code = status.HTTP_401_UNAUTHORIZED,
            detail      = "Token expired",
            headers     = {"WWW-Authenticate": "Bearer"},
        )
    
# Helper function to check if JWT token is expired
def validate_token(token: str) -> bool:
    logger.info(f"FASTAPI Services - validate_token() - Validate if JWT token is valid")
    is_expired = True
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])

        # Check if token has expired
        current_time = str(datetime.datetime.now(timezone.utc))
        if current_time < payload['expiration']:
            is_expired = False
        return is_expired

    except Exception as e:
        logger.error(f"FASTAPI Services Error - validate_token() encountered an error: {e}") 

# Token verification wrapper function
async def verify_token(token: str = Depends(oauth2_scheme)) -> str:
    '''A wrapper to validate the tokens in the request headers'''

    if not token:
        raise HTTPException(
            status_code  = status.HTTP_401_UNAUTHORIZED,
            detail       = {
                'status'    : status.HTTP_204_NO_CONTENT,
                'type'      : "string",
                'message'   : "Missing authentication token"
            },
            headers      = {"WWW-Authenticate": "Bearer"},
        )

    if validate_token(token):
        raise HTTPException(
            status_code  = status.HTTP_401_UNAUTHORIZED,
            detail       = {
                'status'    : status.HTTP_401_UNAUTHORIZED,
                'type'      : "string",
                'message'   : "Invalid or expired token"
            },
            headers      = {"WWW-Authenticate": "Bearer"},
        )
    
    return token 


# Helper function to verify passwords
def verify_password(plain_password: str, hashed_password: str) -> bool:
    logger.info(f"FASTAPI Services - verify_password() - Verifying passwords")
    rehashed_pass= get_password_hash(plain_password)
    return rehashed_pass == hashed_password


# Helper function to count tokens
def count_tokens(text: str) -> int:
    logger.info(f"FASTAPI Services - count_tokens() - Count token for GPT-4o model")
    encoding = tiktoken.encoding_for_model("gpt-4o")
    return len(encoding.encode(text))

# Helper function to provide rectification strings
def rectification_helper() -> str:
    logger.info(f"FASTAPI Services - rectification_helper() - Adding prompt to generate correct answer")
    return "The answer you provided is incorrect. I have attached the question and the steps to find the correct answer for the question. Please perform them and report the correct answer."


# Helper function to generate response restriction
def generate_restriction(final_answer: str) -> str:
    logger.info(f"FASTAPI Services - generate_restriction() - Generating response restriction")
    words = final_answer.split()
    if len(words) <= 10:
        return f"Restrict your response to {len(words)} words only. No yapping."
    elif final_answer.replace(" ", "").isdigit():
        return "Provide only numerical values in your response. No yapping."
    else:
        return "No yapping."
    
# Helper function to check if object is json serializable
def json_serial(obj):
    logger.info(f"FASTAPI Services - json_serial() - JSON serializer for objects not serializable by default json code")
    if isinstance(obj, datetime.datetime):
        try:
            return obj.isoformat()
        except:
            return str(obj)
    return str(obj)

# Function to store the JWT token in the database
def store_tokens(token: str) -> bool:
    logger.info(f"FASTAPI Services - store_tokens() - Store the newly generated token in the database")
    logger.info("FASTAPI Services - store_tokens() - Request to store JWT token to the database received")
    token_saved = False

    conn = create_connection_to_snowflake()

    if conn is None:
        return JSONResponse({
            'status': status.HTTP_503_SERVICE_UNAVAILABLE,
            'type': 'string',
            'message': 'Database not found'
        })
    
    if conn:
        try:
            # Get the user_id from the token and save it to the users table
            decoded_token = decode_jwt_token(token)
            logger.info("FASTAPI Services - store_tokens() - SQL - Running a UPDATE statement")

            cursor = conn.cursor()
            update_query = "UPDATE users SET jwt_token = %s WHERE user_id = %s"
            cursor.execute(update_query, (str(token), decoded_token['user_id']))
            conn.commit()

            logger.info("FASTAPI Services - store_tokens() - SQL - UPDATE statement complete")
            logger.info("FASTAPI Services - store_tokens() - SQL - Saved JWT token to the database")
            token_saved = True

        except Exception as exception:
            logger.error("FASTAPI Services Error: store_tokens() encountered an error")
            logger.error(exception)

        finally:
            close_connection(conn, cursor)
            return token_saved
    
# Helper function to check if user already exists
def check_if_user_already_exists(email):
    logger.info(f"FASTAPI Services - check_if_user_already_exists() - Checking if the user with email id already exists")
    conn = create_connection_to_snowflake()

    if conn is None:
        return JSONResponse({
            'status': status.HTTP_503_SERVICE_UNAVAILABLE,
            'type': 'string',
            'message': 'Database not found'
        })
    
    if conn:
        logger.info(f"FASTAPI Services - check_if_user_already_exists() - Database connection successful")
        cursor = conn.cursor()
        try:
            logger.info(f"FASTAPI Services - SQL - check_if_user_already_exists() - Executing SELECT statement")
            query = """
            SELECT * FROM users WHERE email = %s;
            """
            cursor.execute(query, (email,))
            logger.info(f"FASTAPI Services - SQL - check_if_user_already_exists() - SELECT statement executed successfully")

            db_user = cursor.fetchone()

            # User does not exist with the given email
            if db_user is None:
                close_connection(conn, cursor)
                logger.info(f"FASTAPI Services - Database - check_if_user_already_exists() - Connection to DB closed")
                return None
            else:
                logger.info(f"FASTAPI Services - Database - check_if_user_already_exists() - User already exists with details {db_user}")
                return db_user
        
        except Exception as e:
            logger.error(f"FASTAPI Services Error - check_if_user_already_exists() encountered an error: {e}")  
    return None

# Helper function to Register New User
def register_user(first_name, last_name, phone, email, password):
    logger.info(f"FASTAPI Services - register_user() - Registering User data into the database")
    conn = create_connection_to_snowflake()

    if conn is None:
        return JSONResponse({
            'status': status.HTTP_503_SERVICE_UNAVAILABLE,
            'type': 'string',
            'message': 'Database not found'
        })
    
    if conn:
        logger.info(f"FASTAPI Services - register_user() - Database connection successful")
        cursor = conn.cursor()
        try:
            hashed_password = get_password_hash(password)
            logger.info(f"FASTAPI Services - SQL - register_user() - Executing INSERT statement")
            query = """
            INSERT INTO users(first_name, last_name, phone, email, password)  
            VALUES (%s, %s, %s, %s, %s)
            """

            cursor.execute(query, (first_name, last_name, phone, email, hashed_password))
            conn.commit()
            logger.info(f"FASTAPI Services - SQL - register_user() - INSERT statement executed")

            # Retrieve the ID of the newly registered user
            cursor.execute("SELECT user_id FROM users WHERE email = %s", (email,))
            new_user_id = cursor.fetchone()[0]
            logger.info(f"FASTAPI Services - register_user() - New user registered with ID: {new_user_id}")

            # Create JWT token for new user
            jwt_token = create_jwt_token({
                'user_id' : new_user_id,
                'email'   : email
            })
            
            token_saved = store_tokens(jwt_token['token'])

            if token_saved:
                logger.info(f"FASTAPI Services - register_user() - JWT token created and stored")
                response = {
                    'status': status.HTTP_200_OK,
                    'type'  : 'string',
                    'message' : jwt_token
                }
            else:
                logger.info(f"FASTAPI Services - register_user() - Failed to save JWT token to database")
                response = {
                    "status"      : status.HTTP_304_NOT_MODIFIED,
                    'type'        : "string",
                    "message"     : "Failed to save token to database"
                }
            
            
        except Exception as e:
            logger.error(f"FASTAPI Services Error - register_user() encountered an error: {e}")  
            response = {
                    "status": status.HTTP_500_INTERNAL_SERVER_ERROR,
                    'type': "string",
                    "message": "New user could not be registered. Something went wrong.",
                }
        finally:
            close_connection(conn, cursor)
            logger.info(f"FASTAPI Services - register_user() - Database - Connection to the database was closed")

        return JSONResponse(content = response)
    
# Helper function to LogIn
def login_user(db_user, email, password):
    logger.info(f"FASTAPI Services - login_user() - Logging In User")
    conn = create_connection_to_snowflake()

    if conn is None:
        return JSONResponse({
            'status': status.HTTP_503_SERVICE_UNAVAILABLE,
            'type': 'string',
            'message': 'Database not found'
        })
    
    if conn:
        logger.info(f"FASTAPI Services - login_user() - Database connection successful")
        cursor = conn.cursor()
        try:

            # Convert tuple into dictionary
            if isinstance(db_user, tuple):
                logger.info(f"FASTAPI Services - login_user() - db_user tuple converted to dictionary")
                db_user = {
                    'user_id': db_user[0],
                    'first_name': db_user[1],
                    'last_name': db_user[2],
                    'phone': db_user[3],
                    'email': db_user[4],
                    'password': db_user[5],
                    'jwt_token': db_user[6]
                }

            if verify_password(password, db_user['password']):
                # Create a JWT token for the user after successful authentication
                logger.info(f"FASTAPI Services - login_user() - Password Verified")
                jwt_token = create_jwt_token({
                    "user_id"   : db_user['user_id'], 
                    "email"     : db_user['email']
                })

                token_saved = store_tokens(jwt_token['token'])

                if token_saved:
                    logger.info(f"FASTAPI Services - login_user() - JWT token created and stored")
                    logger.info(f"User logged in: {db_user['user_id']}")
                    response = {
                        "status"      : status.HTTP_200_OK,
                        'type'        : "string",
                        "message"     : jwt_token
                    }
                
                else:
                    logger.info(f"FASTAPI Services - login_user() - Failed to save JWT token to database")
                    response = {
                    "status"      : status.HTTP_304_NOT_MODIFIED,
                    'type'        : "string",
                    "message"     : "Failed to save token to database"
                }

            else:
                logger.error(f"FASTAPI Services - login_user() - Invalid email or password")
                response = {
                        'status'    : status.HTTP_401_UNAUTHORIZED,
                        'type'      : "string",
                        'message'   : "Invalid email or password"
                    }

        except Exception as e:
            logger.error(f"FASTAPI Services Error - login_user() encountered an error: {e}")  
            response = {
                    "status": status.HTTP_500_INTERNAL_SERVER_ERROR,
                    'type': "string",
                    "message": "User could not be logged in. Something went wrong.",
                }

        finally:
            close_connection(conn, cursor)
            logger.info(f"FASTAPI Services - login_user() - Database - Connection to the database was closed")

        # Return the JSON response containing the JWT token
        return JSONResponse(content=response)

# Helper function to get the list of documents
def explore_documents(prompt_count):
    logger.info(f"FASTAPI Services - explore_documents() - Listing out the documents")
    conn = create_connection_to_snowflake()

    if conn is None:
        return JSONResponse({
            'status': status.HTTP_503_SERVICE_UNAVAILABLE,
            'type': 'string',
            'message': 'Database not found'
        })
    
    if conn:
        logger.info(f"FASTAPI Services - explore_documents() - Database connection successful")
        cursor = conn.cursor(DictCursor)
        try:
            logger.info(f"FASTAPI Services - SQL - explore_documents() - Executing SELECT statement")
            query = """
            SELECT document_id, title, image_url, FROM publications_info LIMIT %s
            """
            cursor.execute(query, (prompt_count,))
            rows = cursor.fetchall()
            logger.info(f"FASTAPI Services - SQL - explore_documents() - Output - {rows}")

            response = {
                    'status'    : status.HTTP_200_OK,
                    'type'      : "json",
                    'message'   : [{"document_id": row["DOCUMENT_ID"], "title": row['TITLE'], "image_url": row['IMAGE_URL']} for row in rows],
                    'length'    : prompt_count
            }

            logger.info(f"FASTAPI Services - SQL - explore_documents() - SELECT statement executed successfully")
            
            return JSONResponse(content = response)

        except Exception as e:
            logger.error(f"FASTAPI Services Error - explore_documents() encountered an error: {e}")  

        finally:
            close_connection(conn, cursor)
            logger.info(f"FASTAPI Services - explore_documents() - Database - Connection to the database was closed")


        return JSONResponse({
            'status'    : status.HTTP_500_INTERNAL_SERVER_ERROR,
            'type'      : "string",
            'message'   : "Could not fetch the list of prompts. Something went wrong."
        })

# Helper function to load the document
def load_document(document_id):
    logger.info(f"FASTAPI Services - load_document() - Loading the user selected document")
    conn = create_connection_to_snowflake()

    if conn is None:
        return JSONResponse({
            'status': status.HTTP_503_SERVICE_UNAVAILABLE,
            'type': 'string',
            'message': 'Database not found'
        })
    
    if conn:
        logger.info(f"FASTAPI Services - load_document() - Database connection successful")
        cursor = conn.cursor()
        try:
            logger.info(f"FASTAPI Services - SQL - load_document() - Executing SELECT statement")
            query = """
            SELECT * FROM publications_info WHERE document_id = %s;
            """
            cursor.execute(query, (document_id,))
            record = cursor.fetchone()
            logger.info(f"FASTAPI Services - SQL - load_document() - SELECT statement executed successfully")

            if record is None:
                close_connection(conn, cursor)
                logger.info("FASTAPI Services - Database - load_document() - Connection to the database was closed")
                return JSONResponse(
                    {
                        'status'  : status.HTTP_404_NOT_FOUND,
                        'type'    : 'string',
                        'message' : f"Could not fetch the details for the given document_id {document_id}"
                    }
                )
            close_connection(conn, cursor)
            logger.info(f"FASTAPI Services - load_document() - Database - Connection to the database was closed")

            return JSONResponse({
                'status' : status.HTTP_200_OK,
                'type'   : 'json',
                'message': record
            })                       

        except Exception as e:
            logger.error(f"FASTAPI Services Error - load_document() encountered an error: {e}")  

        finally:
            close_connection(conn, cursor)
            logger.info(f"FASTAPI Services - load_document() - Database - Connection to the database was closed")

        return JSONResponse({
            'status'    : status.HTTP_500_INTERNAL_SERVER_ERROR,
            'type'      : "string",
            'message'   : "Could not fetch the user selected document. Something went wrong."
        })
    
# Helper function to download files from S3 bucket
def download_files_from_s3(document_id):
    logger.info(f"FASTAPI Services - download_files_from_s3() - Downloading files from s3 bucket to local")
    logger.info(f"FASTAPI Services - download_files_from_s3() - Creating S3 Client")

    # Create S3 Client
    s3_client = boto3.client(
        's3',
        aws_access_key_id = os.getenv("AWS_ACCESS_KEY_ID"),
        aws_secret_access_key = os.getenv("AWS_SECRET_ACCESS_KEY")
    )

    logger.info(f"FASTAPI Services - download_files_from_s3() - S3 Client created")

    bucket_name = os.getenv("BUCKET_NAME")
    s3_folder_path = f"{bucket_name}/{document_id}"
    local_dir = os.path.join(os.getcwd(), os.getenv("DOWNLOAD_DIRECTORY"), document_id)
    
    # Checking if the document_id directory already exists
    if os.path.exists(local_dir) and os.listdir(local_dir):
        logger.info(f"FASTAPI Services - download_files_from_s3() - Local directory for {document_id} already exists and contains files. Skipping download.")
        return JSONResponse({
            'status' : status.HTTP_200_OK,
            'type' : 'string',
            'message' : 'Files already exist locally. Now download required'
        })
    
    # Creating directory locally if it does not exist
    if not os.path.exists(local_dir):
        logger.info(f"FASTAPI Services - download_files_from_s3() - Creating local directory to store the files in {document_id}")
        os.makedirs(local_dir)

    try:
        response = s3_client.list_objects_v2(Bucket = bucket_name, Prefix = document_id)
        logger.info(f"FASTAPI Services - download_files_from_s3() - Listed all files in {document_id}")

        if 'Contents' not in response:
            logger.info(f"FASTAPI Services - download_files_from_s3() - No files found in specified folder path: s3://{bucket_name}/{s3_folder_path}")
            return JSONResponse({
                'status' : 404,
                'type'   : 'string',
                'message' : 'No files found in the specified folder path'
            })
         # s3://publications-info/document_id/
        for obj in response['Contents']:
            file_key = obj['Key']
            file_name = os.path.join(local_dir, os.path.basename(file_key))
            logger.info(f"FASTAPI Services - download_files_from_s3() - Downloading files")
            s3_client.download_file(bucket_name, file_key, file_name)
            logger.info(f"FASTAPI Services - download_files_from_s3() - Downloaded {file_name}")
        
        return JSONResponse({
            'status' : status.HTTP_200_OK,
            'type' : 'string',
            'message' : 'Files downloaded successfully'
        })
              
    except Exception as e:
        logger.error(f"FASTAPI Services Error - download_files_from_s3() encountered an error: {e}")
        return JSONResponse({
            'status' : status.HTTP_500_INTERNAL_SERVER_ERROR,
            'type': 'string',
            'message' : 'An error occured while downloading files from S3'
        })
    
# Helper function to extract text from PDF document
def extract_text_from_document(document_id):
    logger.info(f"FASTAPI Services - extract_text_from_document() - Extracting text from document with id = {document_id}")

    pdf_dir = os.path.join(os.getcwd(), os.getenv("DOWNLOAD_DIRECTORY"), document_id)

    if not os.path.exists(pdf_dir):
        logger.error(f"FASTAPI Services Error - extract_text_from_document() - Directory {pdf_dir} does not exist")
        return None
    
    pdf_file = None
    for file in os.listdir(pdf_dir):
        if file.endswith('.pdf'):
            pdf_file = os.path.join(pdf_dir, file)
            break
    
    if pdf_file is None:
        logger.error(f"FASTAPI Services Error - extract_text_from_document() - No PDF file found in directory {pdf_dir} ")
        return None
    
    try:
        logger.info(f"FASTAPI Services - extract_text_from_document() - Extracting text from pdf file = {pdf_file}")
        text = ""
        with open(pdf_file, 'rb') as file:
            reader = PyPDF2.PdfReader(file)
            for page in reader.pages:
                text += page.extract_text()
        print("Text extracted for the entire PDF")
        logger.info(f"FASTAPI Services - extract_text_from_document() - Text extracted for the entire PDF file = {pdf_file}")
        return text.strip()
    
    except Exception as e:
        logger.error(f"FASTAPI Services Error - extract_text_from_document() encountered an error: {e}")

# Helper function to generate summary of PDF document
def generate_summary(document_id):
    logger.info(f"FASTAPI Services - generate_summary() - Generating summary for document {document_id}")

    # Extracting text from the document pdf file
    text = extract_text_from_document(document_id)
    logger.info(f"FASTAPI Services - generate_summary() - {document_id} - Text extracted and ready for summarization")

    try:
        # Creating OpenAI client
        client = OpenAI(
            base_url = os.getenv("NVIDIA_URL_SUMMARY"),
            api_key = os.getenv("NVIDIA_API_KEY_SUMMARY")
        )
        logger.info(f"FASTAPI Services - generate_summary() - OpenAI Client created successfully")

        message = [{'role': 'user', 'content' : f"Conclude the summary in 3-5 sensible complete sentences for text, no extra context needed: \n {text}"}]
        logger.info(f"FASTAPI Services - generate_summary() - Message/Prompt created successfully")

        completion = client.chat.completions.create(
            model = "meta/llama-3.1-405b-instruct",
            messages = message,
            temperature = 0.2, 
            top_p = 0.7,
            max_tokens = 150,
            stream = True
        )
        logger.info(f"FASTAPI Services - generate_summary() - NVIDIA model defined successfully")

        summary = ""
        for chunk in completion:
            if chunk.choices[0].delta.content is not None:
                logger.info(f"FASTAPI Services - generate_summary() - Collecting generated summary")
                summary += chunk.choices[0].delta.content
        logger.info(f"FASTAPI Services - generate_summary() - {document_id} - Summary generated successfully")
        return JSONResponse({
            'status' : status.HTTP_200_OK,
            'type' : 'text',
            'message' : summary
        })

    except Exception as e:
        logger.error(f"FASTAPI Services Error - generate_summary() encountered an error: {e}")
        return JSONResponse({
            'status' : status.HTTP_500_INTERNAL_SERVER_ERROR,
            'type' : 'string',
            'message' : 'Error while generating summary for the pdf document'
        })


# Helper function to store the responses into the database
def save_response_to_db(document_id, question, response, token):
    logger.info(f"FASTAPI Services - save_response_to_db() - Saving Research Notes to SnowFlake database")
    token_payload = decode_jwt_token(token)
    user_id = token_payload['user_id']
    logger.info(f"FASTAPI Services - save_response_to_db() - User id = {user_id}")
    conn = create_connection_to_snowflake()

    if conn is None:
        return JSONResponse({
            'status': status.HTTP_503_SERVICE_UNAVAILABLE,
            'type': 'string',
            'message': 'Database not found'
        })
    
    if conn:
        logger.info(f"FASTAPI Services - save_response_to_db() - Database connection successful")
        cursor = conn.cursor()
        try:
            logger.info(f"FASTAPI Services - SQL - save_response_to_db() - Executing INSERT statement")
            query = f"""INSERT INTO research_notes(document_id, user_id, prompt, response) VALUES('{document_id}', '{user_id}', '{str(question).replace("'", "")}', '{str(response).replace("'", "")}')"""

            cursor.execute(query)
            conn.commit()
            logger.info(f"FASTAPI Services - SQL - save_response_to_db() - INSERT statement executed successfully")
            return JSONResponse({
                'status': status.HTTP_200_OK,
                'type'  : 'string',
                'message' : 'Response stored to database successfully'
            })
        except Exception as e:
            logger.error(f"FASTAPI Services Error - save_response_to_db() encountered an error: {e}")  
            response = {
                    "status": status.HTTP_500_INTERNAL_SERVER_ERROR,
                    'type': "string",
                    "message": "Error while saving responses to Database",
                }
        finally:
            close_connection(conn, cursor)
            logger.info(f"FASTAPI Services - save_response_to_db() - Database - Connection to the database was closed")


# # Provide path to Tesseract OCR (Windows only)
# pytesseract.pytesseract.tesseract_cmd = "C:\\Program Files\\Tesseract-OCR\\tesseract.exe"

# Tesseract OCR - Homebrew
# pytesseract.pytesseract.tesseract_cmd = "/opt/homebrew/bin/tesseract"


# ============================== Handling Text based content ==============================

def extract_pdf_elements(fpath, fname):
    """ Extract images, tables, and chunk text from a PDF file """
    
    return partition_pdf(
        filename                        = os.path.join(fpath, fname),
        starting_page_number            = 5,
        extract_images_in_pdf           = True,
        extract_image_block_types       = ["Image", "Table"],
        infer_table_structure           = True,
        chunking_strategy               = "by_title",
        max_characters                  = 4000,
        new_after_n_chars               = 3800,
        combine_text_under_n_chars      = 2000,
        extract_image_block_output_dir  = os.path.join(fpath, os.getenv("EXTRACTED_IMAGE_DIRECTORY")),
    )

def categorize_elements(raw_pdf_elements):
    """ Categorize extracted elements from a PDF into tables and texts """
    
    tables = []
    texts = []
    
    for element in raw_pdf_elements:
        if "unstructured.documents.elements.Table" in str(type(element)):
            tables.append(str(element))
        
        elif "unstructured.documents.elements.CompositeElement" in str(type(element)):
            texts.append(str(element))
    
    return texts, tables

def preprocess_text(raw_text):
    """ Strip unnecessary characters from the provided text """

    processed_text = []

    for text in raw_text:
        new_text = text.replace('\n', ' ').replace('- ', '').replace('  ', '')
        processed_text.append(unidecode(new_text))
    
    return processed_text


def chunk_pdf(fpath, fname):
    
    # Get elements
    raw_pdf_elements = extract_pdf_elements(fpath, fname)

    # Get text, tables
    texts, tables = categorize_elements(raw_pdf_elements)

    # Remove irrelevant characters to avoid tokenizing issues
    # texts = preprocess_text(texts)

    # Enforce a specific token size for texts
    # Use tiktoken for tokenizing
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size      = 4000, 
        chunk_overlap   = 500,
        add_start_index = True
    )
    
    # Merge all the texts in the texts[]
    joined_texts = " ".join(texts)
    
    texts_4k_token = text_splitter.split_text(joined_texts)
    texts_4k_token = preprocess_text(texts_4k_token)

    return texts, tables, texts_4k_token

def generate_text_summaries(texts, tables, summarize_texts=False):
    """ Summarize text elements if needed """

    # Define the prompt message for summarizing the text
    prompt_text = """You are an assistant tasked with summarizing tables and text for retrieval via RAGs. \
    These summaries will be embedded and used to retrieve the raw text or table elements. \
    Give a concise summary of the table or text that is well optimized for retrieval via RAGs. Table or text: {element} """
    
    prompt = ChatPromptTemplate.from_template(prompt_text)

    # Text summary chain
    model = ChatOpenAI(
        temperature     = 0, 
        model           = "gpt-4o",
        api_key         = os.getenv("OPEN_AI_API")
    )
    summarize_chain = {"element": lambda x: x} | prompt | model | StrOutputParser()

    text_summaries = []
    table_summaries = []

    # Apply to text if texts are provided and summarization is requested
    if texts and summarize_texts:
        text_summaries = summarize_chain.batch(texts, {"max_concurrency": 5})
    
    elif texts:
        text_summaries = texts

    # Apply to tables if tables are provided
    if tables:
        table_summaries = summarize_chain.batch(tables, {"max_concurrency": 5})

    return text_summaries, table_summaries


# ============================== Handling Image based content ==============================

def encode_image(image_path):
    """ Return the image in base64 format """
   
    with open(image_path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode("utf-8")


def image_summarize(img_base64, prompt):
    """ Ask the LLM to generate a summary of the image """
    
    chat = ChatOpenAI(
        model       = "gpt-4o", 
        max_tokens  = 1024,
        api_key     = os.getenv("OPEN_AI_API")
    )

    msg = chat.invoke(
        [
            HumanMessage(
                content=[
                    {
                        "type": "text", 
                        "text": prompt
                    },
                    {
                        "type"      : "image_url",
                        "image_url" : {"url": f"data:image/jpeg;base64,{img_base64}"},
                    },
                ]
            )
        ]
    )
    return msg.content


def generate_img_summaries(path):
    """ Generate summaries and base64 encoded strings for images """

    # Store base64 encoded images
    img_base64_list = []

    # Store image summaries
    image_summaries = []

    # Define the prompt message for summarizing the images
    prompt = """You are an assistant tasked with summarizing images for retrieval via RAGs. \
    These summaries will be embedded and used to retrieve the raw image via RAGs. \
    If you encounter an image that seems to be a logo or a cover image or a barcode, simply respond by saying IRRELEVANT IMAGE. \
    Give a concise summary of the image that is well optimized for retrieval via RAGs."""

    # Apply to images
    for img_file in sorted(os.listdir(path)):
        if img_file.endswith(".jpg"):
            
            img_path = os.path.join(path, img_file)
            base64_image = encode_image(img_path)
            
            img_base64_list.append(base64_image)
            image_summaries.append(image_summarize(base64_image, prompt))

    return img_base64_list, image_summaries

def save_preprocessed_context(fpath, json_file, texts, text_summaries, tables, table_summaries, img_base64_list, image_summaries):

    texts_uuid_list  = [str(uuid.uuid4()) for _ in texts]
    tables_uuid_list = [str(uuid.uuid4()) for _ in tables]
    images_uuid_list = [str(uuid.uuid4()) for _ in img_base64_list]

    data = {
        "texts"             : texts,
        "text_summaries"    : text_summaries,
        "texts_uuid_list"   : texts_uuid_list,
        "tables"            : tables,
        "table_summaries"   : table_summaries,
        "tables_uuid_list"  : tables_uuid_list,
        "img_base64_list"   : img_base64_list,
        "image_summaries"   : image_summaries,
        "images_uuid_list"  : images_uuid_list
    }

    output_path = os.path.join(fpath, json_file)
    
    with open(output_path, "w") as file:
        json.dump(data, file, indent = 4)

def create_multi_vector_retriever(
    vectorstore, 
    text_summaries, 
    texts, 
    texts_uuid_list, 
    table_summaries, 
    tables, 
    tables_uuid_list, 
    image_summaries, 
    images, 
    images_uuid_list
):
    """ Create retriever that indexes summaries, but returns raw images or texts """

    # Initialize the storage layer
    store = InMemoryStore()
    id_key = "doc_id"

    # Create the multi-vector retriever to fetch 'k' similar documents
    retriever = MultiVectorRetriever(
        vectorstore     = vectorstore,
        docstore        = store,
        id_key          = id_key,
        search_type     = "similarity",
        search_kwargs   = {"k": 6}
    )

    # Helper function to add documents to the vectorstore and docstore
    def add_documents(retriever, doc_summaries, doc_contents, doc_uuids):
        
        doc_ids = doc_uuids
        summary_docs = [
            Document(
                page_content    = s, 
                metadata        = {
                    "doc_id"    : doc_ids[i],
                    # Store the original content in metadata
                    "content"   : doc_contents[i]
                }
            )
            for i, s in enumerate(doc_summaries)
        ]
        
        retriever.vectorstore.add_documents(summary_docs)
        retriever.docstore.mset(list(zip(doc_ids, doc_contents)))

    # Add texts, tables, and images
    
    # Check that text_summaries is not empty before adding
    if text_summaries:
        add_documents(retriever, text_summaries, texts, texts_uuid_list)
    
    # Check that table_summaries is not empty before adding
    if table_summaries:
        add_documents(retriever, table_summaries, tables, tables_uuid_list)
    
    # Check that image_summaries is not empty before adding
    if image_summaries:
        add_documents(retriever, image_summaries, images, images_uuid_list)

    return retriever

def save_report_vectorstore(report_vectorstore, response):
    """ Add the report response to vectorstore if prompt_type is 'report' """
    
    report_doc = Document(
        page_content = response,
        metadata = {
            "doc_id"    : str(uuid.uuid4()),
            "doc_type"  : "report"
        }
    )
    
    report_vectorstore.add_documents([report_doc])

def create_report_retriever(report_vectorstore):
    """ Create a retriever for the vectorstore """

    return report_vectorstore.as_retriever(
        search_type     = "similarity",
        search_kwargs   = {'k':3}
    )

def looks_like_base64(sb):
    """Check if the string looks like base64"""
    
    return re.match("^[A-Za-z0-9+/]+[=]{0,2}$", sb) is not None


def is_image_data(b64data):
    """ Check if the base64 data is an image by looking at the start of the data """
    
    image_signatures = {
        b"\xff\xd8\xff"                     : "jpg",
        b"\x89\x50\x4e\x47\x0d\x0a\x1a\x0a" : "png",
        b"\x47\x49\x46\x38"                 : "gif",
        b"\x52\x49\x46\x46"                 : "webp",
    }
    
    try:
        # Decode and get the first 8 bytes
        header = base64.b64decode(b64data)[:8]  
        
        for sig, format in image_signatures.items():
            if header.startswith(sig):
                return True
        
        return False
    
    except Exception as exception:
        print(exception)
        return False


def resize_base64_image(base64_string, size=(128, 128)):
    """ Resize an image encoded as a Base64 string """
    
    # Decode the Base64 string
    img_data = base64.b64decode(base64_string)
    img = Image.open(io.BytesIO(img_data))

    # Resize the image
    resized_img = img.resize(size, Image.LANCZOS)

    # Save the resized image to a bytes buffer
    buffered = io.BytesIO()
    resized_img.save(buffered, format=img.format)

    # Encode the resized image to Base64
    return base64.b64encode(buffered.getvalue()).decode("utf-8")


def split_image_text_types(docs):
    """ Split base64-encoded images and texts """
    
    b64_images = []
    texts = []
    
    for doc in docs:
        
        # Check if the document is of type Document and extract page_content if so
        if isinstance(doc, Document):
            doc = doc.page_content
        
        if looks_like_base64(doc) and is_image_data(doc):
            doc = resize_base64_image(doc, size=(1300, 600))
            b64_images.append(doc)
        
        else:
            texts.append(doc)
    
    return {
        "images": b64_images, 
        "texts" : texts
    }


def img_prompt_func(data_dict, prompt_type = "default"):
    """ Join the context into a single string with configurable prompt type """
    
    formatted_texts = "\n".join(data_dict["context"]["texts"])
    messages = []

    # Adding image(s) to the messages if present
    if data_dict["context"]["images"]:
        for image in data_dict["context"]["images"]:
            
            image_message = {
                "type"      : "image_url",
                "image_url" : {"url": f"data:image/jpeg;base64,{image}"},
            }
            messages.append(image_message)

    # Define different prompt templates
    prompts = {
        "default": (
            "You are a helpful assistant that does exactly as instructed.\n"
            "You will be given a mixed of text, tables, and image(s) usually of charts or graphs.\n"
            "Use this information to provide answer related to the user question. \n"
            f"User-provided question: {data_dict['question']}\n\n"
            "Text and / or tables:\n"
            f"{formatted_texts}"
        ),
        "report": (
            "You are a professional report writer and analyst. "
            "Generate a detailed report based on the provided information and images. "
            "Your report should:\n"
            "1. Have a clear title related to the query\n"
            "2. Include multiple sections with appropriate headings\n"
            "3. Reference and analyze any charts or graphs provided\n"
            "4. Provide insights and conclusions\n\n"
            f"Topic for the report: {data_dict['question']}\n\n"
            "Available information:\n"
            f"{formatted_texts}\n\n"
            "Please structure your response in a report format with clear sections and analysis of any visualizations provided."
        )
    }

    # Set prompt based on prompt_type
    prompt_text = prompts.get(prompt_type, prompts["default"])
    
    text_message = {
        "type": "text",
        "text": prompt_text
    }
    messages.append(text_message)
    
    return [HumanMessage(content = messages)]

def multi_modal_rag_chain(retriever, prompt_type = "default", max_tokens = 1024):
    """ Multi-modal RAG chain with configurable prompt type """
    
    # Use GPT-4o as the LLM
    model = ChatOpenAI(
        temperature = 0, 
        model       = "gpt-4o", 
        max_tokens  = max_tokens,
        api_key     = os.getenv("OPEN_AI_API")
    )

    # model = ChatNVIDIA(
    #     model       = "meta/llama-3.2-90b-vision-instruct",
    #     api_key     = os.getenv("NVIDIA_API"),
    #     temperature = 0,
    #     max_tokens  = max_tokens
    # )

    # Lambda function that includes both data_dict and prompt_type
    prompt_func = lambda data_dict: img_prompt_func(data_dict, prompt_type = prompt_type)

    # RAG pipeline
    chain = (
        {
            "context"   : retriever | RunnableLambda(split_image_text_types),
            "question"  : RunnablePassthrough(),
        }
        | RunnableLambda(prompt_func)
        | model
        | StrOutputParser()
    )

    return chain


def invoke_pipeline(document_id, question, prompt_type, source, token):

    # Find the PDF document in the directory of document_id
    fpath = os.path.join(os.getcwd(), os.getenv("DOWNLOAD_DIRECTORY", "downloads") , document_id)
    dir_contents = os.listdir(fpath)
    
    for file in dir_contents:
        if file.endswith(".pdf"):
            fname = file
            break

    # Define full_text vector database details
    full_text_database_name = document_id + "_full_text_database"
    full_text_collection_name = document_id + "_full_text_collection"
    full_text_persistent_directory = os.path.join(fpath, full_text_database_name)

    # Define report vector database details
    report_database_name = document_id + "_report_database"
    report_collection_name = document_id + "_report_collection"
    report_persistent_directory = os.path.join(fpath, report_database_name)

    # Save preprocessed contents to a json file
    preprocessed_json = os.getenv("PREPROCESSED_JSON_FILE")

    # Check if the vector store and the json file already exist to avoid rebuilding
    # the vector index
    json_exists = database_exists = False

    json_exists = preprocessed_json in dir_contents and os.path.isfile(os.path.join(fpath, preprocessed_json))
    database_exists = full_text_database_name in dir_contents and os.path.isdir(os.path.join(fpath, full_text_database_name))

    if not json_exists and not database_exists:

        # Partition and chunk the PDF
        texts, tables, texts_4k_token = chunk_pdf(fpath, fname)

        # (OPTIONAL) Summarize the text content
        text_summaries, table_summaries = generate_text_summaries(
            texts_4k_token, 
            tables, 
            summarize_texts = False
        )

        # Generate summaries for the images
        img_base64_list, image_summaries = generate_img_summaries(os.path.join(fpath, os.getenv("EXTRACTED_IMAGE_DIRECTORY")))

        # Save all preprocessed data
        save_preprocessed_context(fpath, preprocessed_json, texts, text_summaries, tables, table_summaries, img_base64_list, image_summaries)

    file_path = os.path.join(fpath, preprocessed_json)

    text_summaries = texts = texts_uuid_list = []
    table_summaries = tables = tables_uuid_list = [] 
    image_summaries = img_base64_list = images_uuid_list = []

    with open(file_path, "r") as file:
        data = json.load(file)
        
        texts = data["texts"]
        text_summaries = data["text_summaries"]
        texts_uuid_list = data["texts_uuid_list"]
        
        tables = data["tables"]
        table_summaries = data["table_summaries"]
        tables_uuid_list = data["tables_uuid_list"]
        
        img_base64_list = data["img_base64_list"]
        image_summaries = data["image_summaries"]
        images_uuid_list = data["images_uuid_list"]

    
    # The full text vectorstore to use to index the summaries
    full_text_vectorstore = Chroma(
        collection_name     = full_text_collection_name, 
        embedding_function  = OpenAIEmbeddings(
            model   = "text-embedding-3-large",
            api_key = os.getenv("OPEN_AI_API")
        ),
        persist_directory   = full_text_persistent_directory
    )

    # The report vectorstore to index reports
    report_vectorstore = Chroma(
        collection_name     = report_collection_name, 
        embedding_function  = OpenAIEmbeddings(
            model   = "text-embedding-3-large",
            api_key = os.getenv("OPEN_AI_API")
        ),
        persist_directory   = report_persistent_directory
    )

    # Create full_text_retriever
    retriever_multi_vector_img = create_multi_vector_retriever(
        full_text_vectorstore,
        text_summaries,
        texts,
        texts_uuid_list,
        table_summaries,
        tables,
        tables_uuid_list,
        image_summaries,
        img_base64_list,
        images_uuid_list
    )

    # Create report_retriever
    retriever_report = create_report_retriever(report_vectorstore)

    try:

        # Check retrieval
        query = question

        if prompt_type == "report":
            if source == "report":
                # RAG chain for Q&A, with report_vectorstore as source
                chain_multimodal_rag = multi_modal_rag_chain(retriever_report, prompt_type="report", max_tokens=2048)
                docs = retriever_report.invoke(query)
            
            else:
                # RAG chain for generating reports, with full_text_vectorstore as source
                chain_multimodal_rag = multi_modal_rag_chain(retriever_multi_vector_img, prompt_type="report", max_tokens=2048)
                docs = retriever_multi_vector_img.invoke(query)

        if prompt_type == "default":
            if source == "report":
                # Default Q&A RAG chain, with report_vectorstore as source
                chain_multimodal_rag = multi_modal_rag_chain(retriever_report, prompt_type="default")
                docs = retriever_report.invoke(query)
            
            else:
                # Default Q&A RAG chain, with full_text_vectorstore as source
                chain_multimodal_rag = multi_modal_rag_chain(retriever_multi_vector_img, prompt_type="default")
                docs = retriever_multi_vector_img.invoke(query)
        
        # Bundle the images
        doc_limit = len(docs) if len(docs) < 3 else 3
        images_retrieved = {
            "length": 0,
            "content": []
        }
        
        if source != "report":
            for i in range(doc_limit):
                if looks_like_base64(docs[i]):
                    images_retrieved['length'] += 1
                    images_retrieved['content'].append(docs[i])

        # Run the default RAG chain
        llm_response = chain_multimodal_rag.invoke(query)

        # Get trust score from CleanLabs TLM
        studio = Studio(os.getenv("TLM_API_KEY"))
        tlm = studio.TLM(
            options = {
                "model" : "gpt-4o"
            }
        )
        trust_score = tlm.get_trustworthiness_score(prompt=query, response=llm_response)

        # Save and index reports in report_vectorstore only if trust_score exceeds threshold
        if prompt_type == "report" and trust_score['trustworthiness_score'] > 0.6:
            save_report_vectorstore(report_vectorstore, llm_response)
            save_response_to_db(document_id, question, llm_response, token)

        # Prepare the JSON content to return to frontend
        response = {
            "token"         : token,
            "document_id"   : document_id,
            "question"      : question,
            "llm_response"  : llm_response,
            "image_length"  : images_retrieved['length'],
            "image_content" : images_retrieved['content'],
            "trust_score"   : f"{trust_score['trustworthiness_score']:.3f}"
        }

        return JSONResponse({
            'status'    : status.HTTP_200_OK,
            'type'      : 'json',
            'message'   : response
        })
    
    except Exception as e:
        logger.error(f"FASTAPI Services Erorr - invoke_pipeline() encountered an error: {e}")
        return JSONResponse({
            'status'    : status.HTTP_500_INTERNAL_SERVER_ERROR,
            'type'      : 'string',
            'message'   : 'Error while implementing RAG pipeline'
        })