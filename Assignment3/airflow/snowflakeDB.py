import snowflake.connector
import os
import logging
from dotenv import load_dotenv

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Load environment variables from .env file
load_dotenv()

def connect_to_db():
    """
    Establish a connection to Snowflake using environment variables.
    """
    try:
        conn = snowflake.connector.connect(
            user=os.getenv('SNOWFLAKE_USER'),
            password=os.getenv('SNOWFLAKE_PASSWORD'),
            account=os.getenv('SNOWFLAKE_ACCOUNT'),
            warehouse=os.getenv('SNOWFLAKE_WAREHOUSE'),
            database=os.getenv('SNOWFLAKE_DATABASE'),
            schema=os.getenv('SNOWFLAKE_SCHEMA'),
            role=os.getenv('SNOWFLAKE_ROLE')
        )
        logger.info("Connected to Snowflake successfully.")
        return conn
    except snowflake.connector.errors.Error as e:
        logger.error("Failed to connect to Snowflake: %s", e)
        return None

def create_storage_integration_and_stage(cursor):
    """
    Create storage integration and stage in Snowflake.
    """
    try:
        # Create storage integration
        cursor.execute("""
        CREATE OR REPLACE STORAGE INTEGRATION my_s3_integration
          TYPE = EXTERNAL_STAGE
          STORAGE_PROVIDER = 'S3'
          ENABLED = TRUE
          STORAGE_AWS_ROLE_ARN = 'arn:aws:iam::339713146727:role/mysnowflakerole'
          STORAGE_ALLOWED_LOCATIONS = ('s3://publications-info/');
        """)
        logger.info("Created storage integration: my_s3_integration")

        # Describe storage integration for verification
        cursor.execute("DESC INTEGRATION my_s3_integration;")
        integration_desc = cursor.fetchall()
        logger.info("Storage Integration Description: %s", integration_desc)

        # Create external stage
        cursor.execute("""
        CREATE OR REPLACE STAGE my_s3_stage
          STORAGE_INTEGRATION = my_s3_integration
          URL = 's3://publications-info/';
        """)
        logger.info("Created stage: my_s3_stage")
    except Exception as e:
        logger.error("Error creating storage integration and stage: %s", e)

def drop_tables(cursor):
    """
    Drops existing tables in Snowflake.
    """
    drop_commands = {
        "drop_metadata_json_table": "DROP TABLE IF EXISTS metadata_json;",
        "drop_publications_info_table": "DROP TABLE IF EXISTS publications_info;",
        "drop_users_table": "DROP TABLE IF EXISTS users;",
        "drop_research_notes_table": "DROP TABLE IF EXISTS research_notes;"
    }
    for table_name, command in drop_commands.items():
        try:
            cursor.execute(command)
            logger.info("Dropped table: %s", table_name)
        except Exception as e:
            logger.error("Error dropping table %s: %s", table_name, e)

def create_tables(cursor):
    """
    Creates required tables in Snowflake and loads data.
    """
    create_commands = [
        """
        CREATE OR REPLACE TABLE metadata_json (
            v VARIANT
        );
        """,
        """
        COPY INTO metadata_json 
        FROM @my_s3_stage 
        FILE_FORMAT = (TYPE = 'JSON') 
        PATTERN = '.*\\.json$';
        """,
        """
        CREATE TABLE IF NOT EXISTS publications_info (
            document_id STRING,
            title STRING,
            overview STRING,
            image_url STRING,
            pdf_url STRING
        );
        """,
        """
        INSERT INTO publications_info (document_id, title, overview, image_url, pdf_url)
        SELECT
            v:document_id::string AS document_id,
            v:title::string AS title,
            v:overview::string AS overview,
            CASE 
                WHEN POSITION('.jpg' IN v:cover_image_url::string) > 0 THEN 
                    's3://publications-info/' || v:document_id::string || '/cover_image.jpg' 
                ELSE NULL 
            END AS image_url,
            CASE 
                WHEN POSITION('.pdf' IN v:pdf_filename::string) > 0 THEN 
                    's3://publications-info/' || v:document_id::string || '/' || v:pdf_filename::string 
                ELSE NULL 
            END AS pdf_url
        FROM metadata_json;
        """,
        """
        CREATE TABLE IF NOT EXISTS users (
            user_id INT AUTOINCREMENT PRIMARY KEY,
            first_name VARCHAR(50) NOT NULL,
            last_name VARCHAR(50) NOT NULL,
            phone VARCHAR(50) NOT NULL,
            email VARCHAR(100) NOT NULL,
            password VARCHAR(255) NOT NULL,
            jwt_token TEXT
        );
        """,
        """
        CREATE TABLE IF NOT EXISTS research_notes (
            document_id VARCHAR(50) NOT NULL,
            user_id VARCHAR(50) NOT NULL,
            prompt VARCHAR(225) NOT NULL,
            response TEXT NOT NULL
        );

        """
    ]
    for command in create_commands:
        try:
            cursor.execute(command)
            logger.info("Executed command: %s", command)
        except Exception as e:
            logger.error("Error creating tables or inserting data: %s", e)

def main():
    conn = connect_to_db()
    if conn is None:
        logger.error("Database connection failed. Exiting.")
        return

    if conn:
        try:
            cursor = conn.cursor()

            # Create storage integration and stage
            create_storage_integration_and_stage(cursor)

            # Drop tables if they exist
            drop_tables(cursor)

            # Create tables and load data
            create_tables(cursor)

            # Check for files in the stage
            cursor.execute("LIST @my_s3_stage;")
            list_results = cursor.fetchall()
            logger.info("Files in @my_s3_stage: %d", len(list_results))
            for file in list_results:
                logger.info("Found file: %s", file)

            # Fetch results from publications_info for verification
            cursor.execute("SELECT * FROM publications_info;")
            results = cursor.fetchall()
            logger.info("Entries in publications_info: %d", len(results))
            for row in results:
                logger.info(row)

        except Exception as e:
            logger.error("Error executing SQL commands: %s", e)
        finally:
            # Close the cursor and connection
            cursor.close()
            conn.close()
            logger.info("Connection closed.")

if __name__ == "__main__":
    main()
