from dotenv import load_dotenv
from snowflake.connector import Error
import snowflake.connector
import logging
import time
import os

# Load all environment variables
load_dotenv()

# Logger configuration
logging.basicConfig(level = logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def create_connection_to_snowflake(attempts = 3, delay = 2):

    logger.info("FASTAPI - create_connection() - Creating connection to Snowflake database")

    # Create connection with Snowflake Database
    attempt = 1
    while attempt < attempts:
        try:
            conn = snowflake.connector.connect(
                user = os.getenv("DB_USERNAME", None),
                password = os.getenv("DB_PASSWORD", None),
                account = os.getenv("DB_ACCOUNT", None),
                warehouse = os.getenv("DB_WAREHOUSE", None),
                database = os.getenv("DB_NAME", None),
                schema = os.getenv("DB_SCHEMA", None),
                role = os.getenv("DB_USER_ROLE", None)
            )

            logger.info("FASTAPI - create_connection() - Connection to Snowflake database established successfully")
            return conn
        
        except (Error, IOError) as e:
            if attempt == attempts:
                logger.error(f"FASTAPI - create_connection() - Failed to connect to the Snowflake Database: {e}")
                return None
            else:
                logger.warning(f"FASTAPI - create_connection() - Connection Failed: {e} - Retrying {attempt}/{attempts}")
                time.sleep(delay ** attempt)
                attempt += 1
    return None

def close_connection(dbconn, cursor = None):
    logger.info(f"FASTAPI - close_connection() - Closing the database connection")
    try:
        if dbconn is not None:
            cursor.close()
            dbconn.close()
            logger.info(f"FASTAPI - close_connection() - {dbconn} conn closed successfully")
        else:
            logger.warning(f"FASTAPI - create_connection() - {dbconn} connection does not exist")
    except Exception as e:
        logger.error(f"FASTAPI - close_connection() - Error while closing the database connection: {e}")