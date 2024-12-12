import os
import csv
import json
import time
import shutil
import requests
import logging
import re
import boto3
import snowflake.connector
from bs4 import BeautifulSoup
from uuid import uuid4
from selenium import webdriver
from dotenv import load_dotenv
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
from unidecode import unidecode
from botocore.exceptions import NoCredentialsError, ClientError
from airflow import DAG
from airflow.operators.python import PythonOperator
from datetime import datetime


# Load env variables
load_dotenv()

# Access the variables
user = os.getenv('SNOWFLAKE_USER')
password = os.getenv('SNOWFLAKE_PASSWORD')
account = os.getenv('SNOWFLAKE_ACCOUNT')
warehouse = os.getenv('SNOWFLAKE_WAREHOUSE')
database = os.getenv('SNOWFLAKE_DATABASE')
schema = os.getenv('SNOWFLAKE_SCHEMA')
role = os.getenv('SNOWFLAKE_ROLE')

# ============================= Logger : Begin =============================

# Initialize logger
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")

# Log to console (dev only)
if os.getenv('APP_ENV', 'production') == "development":
    handler = logging.StreamHandler()
    handler.setFormatter(formatter)
    logger.addHandler(handler)

# Also log to a file
file_handler = logging.FileHandler(os.getenv('SCRAPER_LOG_FILE', "scraper_logs.log"))
file_handler.setFormatter(formatter)
logger.addHandler(file_handler) 


# ============================= Logger : End ===============================

def create_client():
    """Create a Selenium client to make requests to websites"""

    logger.info("SCRAPER - create_client() - Request to create a Selenium client received")

    try:    
        # Set WebDriver options (headless mode to run without UI)
        options = Options()
        options.add_argument("--headless") 

        service = Service(ChromeDriverManager().install())

        # Create a Google Chrome WebDriver using the specified service
        driver = webdriver.Chrome(service=service, options=options)
        logger.info("SCRAPER - create_client() - Selenium client created successfully")

    except Exception as exception:
        logger.error("SCRAPER - create_client() - Could not create Selenium client")
        logger.error(exception)
        driver = None
    
    return driver


def download_file(url, filepath):
    """Helper function to download a file from a given URL."""

    logger.info(f"SCRAPER - download_file() - Request to download {filepath} received")
   
    response = requests.get(url, stream = True)
    
    if response.status_code == 200:
        with open(filepath, "wb") as file:
            for chunk in response.iter_content(chunk_size = 8192):
                file.write(chunk)
        
        logger.info(f"SCRAPER - download_file() - Download successfully completed")
    
    else:
        logger.error(f"SCRAPER - download_file() - Download failed")


def stage1_scraper(url, csv_file):
    """Scrape the contents of the results page"""
    
    # Set the scraping status
    stage1_status = False

    # Get the Selenium client
    driver = create_client()

    if driver is None:
        logger.error("SCRAPER - stage1_scraper()- Selenium client not found. Aborting Stage1 scraping.")
        return None
    
    try:

        logger.info(f"SCRAPER - stage1_scraper() - Sending a GET request to URL {url}")

        # Make a GET request
        driver.get(url)

        # Wait for JavaScript to render the content in the browser
        time.sleep(10)

        # Fetch the source code of the webpage so we can parse it
        page_source_code = driver.page_source

        # Call BeautifulSoup to parse the HTML content
        logger.info(f"SCRAPER - stage1_scraper() - Parsing HTML response")
        soup = BeautifulSoup(page_source_code, "html.parser")

        # The content that we are interested in is available in the anchor <a> tag
        # The anchor tags that contain the URL to the PDF file use 'CoveoResultLink' in their CSS class name 
        content = soup.find_all('a', class_="CoveoResultLink")

        if len(content) > 0:

            # Save the title, url, and uuid to a csv file
            with open(csv_file, 'a', newline = '') as file:
               
                writer = csv.writer(file)
                for item in content:
                    
                    document_id = uuid4().hex
                    pdf_name = unidecode(str(item.text).strip().replace("\n", ""))
                    pdf_url = item.get("href")
                    
                    writer.writerow([document_id, pdf_name, pdf_url])
                
                # Force writing the file to the disk
                file.flush()
                logger.info(f"SCRAPER - stage1_scraper() - HTML response parsed and saved to file")
        
        else:
            logger.warning(f"SCRAPER - stage1_scraper() - HTML response was empty! Nothing to parse here...")

        stage1_status = True
    
    except Exception as exception:
        logger.error(f"SCRAPER - stage1_scraper() - Error occured while scraping {url}")
        logger.error(exception)
        stage1_status = False

    finally:
        # Stop the webdriver
        logger.info("SCRAPER - stage1_scraper() - Selenium client closed")
        driver.quit()
    
    return stage1_status

def stage1_controller():
    """ Scrape the contents of a website iteratively """

    logger.info("SCRAPER - stage1_scraper() - Request to initiate Stage1 scraping received")
    # logger.info(f"SCRAPER - stage1_scraper() -  {os.getenv("STAGE_1_FILENAME")}")

    # Extract the PDF file name and the download URL from the anchor tags
    # csv_file = os.path.join(os.getcwd(), os.getenv("STAGE_1_FILENAME"))
    csv_file = os.getenv("STAGE_1_FILENAME", None)

    if csv_file is None:
        logger.error("SCRAPER - stage1_controller() - STAGE_1_FILENAME is missing")
        return
        
    try:
        # Delete the file if it already exists
        if os.path.exists(csv_file):
            os.remove(csv_file)

        # There are 10 pages, and each page has 10 results
        for counter in range(0, 100, 10):
                
            # The url for the first 10 results is slightly different from the remaining 90 results
            if counter == 0:
                url = "https://rpc.cfainstitute.org/en/research-foundation/publications#first=1&sort=%40officialz32xdate%20descending&f:SeriesContent=[Research%20Foundation]"
            else:
                url = f"https://rpc.cfainstitute.org/en/research-foundation/publications#first={counter}&sort=%40officialz32xdate%20descending&f:SeriesContent=[Research%20Foundation]"

            stage1_status = stage1_scraper(url, csv_file)

            if not stage1_status:
                # Something went wrong. Stop the download.
                raise 
        
        logger.info("SCRAPER - stage1_scraper() - Stage1 scraping completed")

    except Exception as exception:
        logger.error(f"SCRAPER - stage1_controller() - Something went wrong")
        logger.error(exception)



def stage2_scraper(document_id, title, url):
    """ Scrape the contents of each result page """
    
    # Set the scraping status
    stage2_status = False

    # Domain prefix for URLs
    url_prefix = os.getenv("URL_PREFIX", None)
    
    if not url_prefix:
        logger.error("SCRAPER - stage2_scraper() - URL_PREFIX is missing. Aborting Stage 2 scraping.")
        return
    
    # Directory to save downloads to
    download_dir = os.getenv("DOWNLOAD_DIRECTORY", "downloads")

    # Get the Selenium client
    driver = create_client()
    if driver is None:
        logger.error("SCRAPER - stage2_scraper() - Selenium client not found. Aborting Stage 2 scraping.")
        return stage2_status

    try:
        
        logger.info(f"SCRAPER - stage2_scraper() - Sending a GET request to URL: {url}")
        driver.get(url)

        # Wait for JavaScript rendering
        time.sleep(10)

        # Parse HTML content using BeautifulSoup
        page_source_code = driver.page_source
        logger.info("SCRAPER - stage2_scraper() - Parsing HTML response.")
        soup = BeautifulSoup(page_source_code, "html.parser")

        download_url = ""
        cover_image_url = ""
        overview = ""

        try:
            # Extract the PDF download URL
            download_content = soup.find('a', class_="content-asset content-asset--primary")
            
            if download_content and download_content.get("href", None):
                if download_content.get("href").endswith(".pdf"):
                    download_url = url_prefix + download_content.get("href")
                
                else:
                    
                    # There is one case where the link of the PDF is not available directly
                    section_content = soup.find('section', class_="article-meta__container items grid__item--article-element")
                    
                    if section_content:
                        url_content = soup.find('a', class_="items__item")

                        if url_content and url_content.get("href", None):
                            download_url = url_prefix + url_content.get("href")
                
            else:
                logger.error("SCRAPER - stage2_scraper() - PDF download link not found.")

        except Exception as exception:
            logger.error("SCRAPER - stage2_scraper() - Error extracting PDF URL")
            logger.error(exception)

        try:
            # Extract the book cover image URL
            cover_image_content = soup.find('img', class_="article-cover")
            
            if cover_image_content and cover_image_content.get("src", None):
                cover_image_url = url_prefix + cover_image_content.get("src").split('?')[0]
            else:
                logger.warning("SCRAPER - stage2_scraper() - Cover image not found.")

        except Exception as exception:
            logger.error("SCRAPER - stage2_scraper() - Error extracting cover image URL")
            logger.error(exception)

        try:
            # Extract the overview text
            
            # Look for <div class="article__paragraph"> and scrape its content
            overview_content = soup.find_all('div', class_='article__paragraph')
            if overview_content:
                for div in overview_content:
                    
                    # Extract text from <p>, <ol>, and <ul> tags
                    for tag in div.find_all(['p', 'ol', 'ul']):
                        overview = overview + " " + unidecode(tag.get_text().strip().replace("\n", ""))

            # Fallback if <div class="article__paragraph"> is missing (Aggressive scraping)
            if not overview:
                logger.warning("SCRAPER - stage2_scraper() - Overview content seems to be missing. Performing brute force search...")

                article_body = soup.find('article', class_='grid__item--article-body')
                if article_body:
                    
                    # Extract from <span class="overview__content">
                    span_content = article_body.find('span', class_='overview__content')
                    if span_content:
                        for para in span_content.find_all('p'):
                            overview = overview + " " + unidecode(para.get_text().strip().replace("\n", ""))

                    # Extract from <div> tags without any class
                    div_without_class = article_body.find_all('div', class_=None)
                    for div in div_without_class:
                        
                        for tag in div.find_all(['p', 'ol', 'ul'], class_=None):
                            overview = overview + " " + unidecode(tag.get_text().strip().replace("\n", ""))
                            overview = re.sub(r'\t+', ' ', overview)


                    logger.info("SCRAPER - stage2_scraper() - Overview content generated")

        except Exception as exception:
            logger.error("SCRAPER - stage2_scraper() - Error extracting overview")
            logger.error(exception)

        try:
            directory = os.path.join(download_dir, document_id)
            
            os.makedirs(directory, exist_ok=False)
            logger.info(f"SCRAPER - stage2_scraper() - Directory created: {directory}")

        except Exception as exception:
            stage2_status = False
            logger.error("SCRAPER - stage2_scraper() - Error creating directories")
            logger.error(exception)
            raise

        try:
            # Download the PDF file
            pdf_filename = os.path.join(directory, os.path.basename(download_url))
            
            if download_url:
                download_file(download_url, pdf_filename)
            else:
                logger.error("SCRAPER - stage2_scraper() - No PDF URL to download.")

        except Exception as exception:
            logger.error("SCRAPER - stage2_scraper() - Error downloading PDF")
            logger.error(exception)

        try:
            # Download the cover image
            cover_image_filename = os.path.join(directory, "cover_image.jpg")
            if cover_image_url:
                download_file(cover_image_url, cover_image_filename)
            else:
                logger.warning("SCRAPER - stage2_scraper() - No cover image URL to download")

        except Exception as exception:
            logger.error("SCRAPER - stage2_scraper() - Error downloading cover image")
            logger.error(exception)

        # Create metadata.json
        try:
            
            metadata = {
                "title"             : title,
                "url"               : url,
                "pdf_filename"      : os.path.basename(pdf_filename) if download_url else "",
                "cover_image_url"   : cover_image_url,
                "pdf_download_url"  : download_url,
                "overview"          : overview,
                "document_id"       : document_id
            }
            
            metadata_file = os.path.join(directory, "metadata.json")
            with open(metadata_file, "w") as file:
                json.dump(metadata, file, indent=4)
            
            logger.info(f"SCRAPER - stage2_scraper() - Metadata saved: {metadata_file}")

        except Exception as exception:
            logger.error("SCRAPER - stage2_scraper() - Error creating metadata.json")
            logger.error(exception)

        stage2_status = True

    except Exception as exception:
        logger.error(f"SCRAPER - Error occurred while scraping {url}")
        logger.error(exception)

    finally:
        logger.info("SCRAPER - stage2_scraper() - Selenium client closed")
        driver.quit()

    return stage2_status


def stage2_controller():
    """ Scrape the contents of a result page iteratively """

    logger.info("SCRAPER - stage2_scraper() - Request to initiate Stage2 scraping received")

    # Extract the PDF file name and the download URL from the anchor tags
    csv_file = os.getenv("STAGE_1_FILENAME", None)

    if csv_file is None:
        logger.error("SCRAPER - stage2_controller() - STAGE_1_FILENAME is missing")
        return
    
    # Directory to save downloads to
    download_dir = os.getenv("DOWNLOAD_DIRECTORY", "downloads")
    
    try:
        # Remove the download directory if already available
        dir_path = os.path.join(os.getcwd(), download_dir)
        
        if os.path.exists(dir_path) and os.path.isdir(dir_path):
            shutil.rmtree(dir_path)

        # Create download directory
        os.makedirs(download_dir, exist_ok=False)
        dir_created = True
    
    except Exception as exception:
        dir_created = False
        logger.error(f"SCRAPER - stage2_controller() - Something went wrong while removing or creating {download_dir}")
        logger.error(exception)
        
    if dir_created:
        try:
            with open(csv_file, 'r') as file:
                reader = csv.reader(file)

                for row in reader:
                    if len(row) != 3:
                        logger.warning(f"SCRAPER - stage2_controller() - Skipping invalid row: {row}")
                        continue 

                    document_id, title, url = row
                    logger.info(f"SCRAPER - stage2_controller() - Downloading: {title}")
                    
                    # Call download for each title and URL
                    success = stage2_scraper(document_id, title, url)
                    
                    if success:
                        logger.info(f"SCRAPER - stage2_controller() - Downloaded: {title}")
                    else:
                        logger.error(f"SCRAPER - stage2_controller() - Failed to download: {title}")
            
            logger.info("SCRAPER - stage1_scraper() - Stage2 scraping completed")

        except Exception as exception:
            logger.error(f"SCRAPER - stage2_controller() - Something went wrong")
            logger.error(exception)


def scrapepublication():
    stage1_controller()
    stage2_controller()

def upload_folder_to_s3(folder_path, bucket):
    # Initialize an S3 client using boto3
    s3 = boto3.client('s3')
    
    # Walk through the directory and its subdirectories
    for root, dirs, files in os.walk(folder_path):
        for file in files:
            # Create the full file path by joining the root with the file name
            local_file_path = os.path.join(root, file)
            
            # Remove the folder_path from the local file path to get the S3 object key
            s3_file_path = os.path.relpath(local_file_path, folder_path)
            
            try:
                # Upload each file to S3, preserving the folder structure
                s3.upload_file(local_file_path, bucket, s3_file_path)
                print(f"Upload Successful: {local_file_path} to s3://{bucket}/{s3_file_path}")
            except FileNotFoundError:
                print(f"The file was not found: {local_file_path}")
            except NoCredentialsError:
                print("Credentials not available")
            except ClientError as e:
                print(f"Client error: {e}")

# Example usage:
folder_path = os.path.join(os.getcwd(), os.getenv('DOWNLOAD_DIRECTORY', 'downloads'))  # Specify the path to the folder you want to upload
bucket = os.getenv('AWS_BUCKET_NAME')  # Specify the S3 bucket name

# Call the function to upload the folder
upload_folder_to_s3(folder_path, bucket)

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


def snowflakeupload():
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

# Define the default arguments
default_args = {
    'owner': 'airflow',
    'depends_on_past': False,
    'retries': 1,
}

# Define the DAG
with DAG(
    'publication_scraper_dag',
    default_args=default_args,
    description='A DAG to scrape publications, upload to S3, and then load data into Snowflake',
    schedule_interval='@daily',
    start_date=datetime(2023, 10, 26),
    catchup=False,
) as dag:

    # Define tasks
    scrape_task = PythonOperator(
        task_id='scrape_publication',
        python_callable=scrapepublication,
    )

    upload_to_s3_task = PythonOperator(
        task_id='upload_to_s3',
        python_callable=upload_folder_to_s3,
        op_args=[folder_path, bucket],
    )

    snowflake_upload_task = PythonOperator(
        task_id='upload_to_snowflake',
        python_callable=snowflakeupload,
    )

    # Set task dependencies
    scrape_task >> upload_to_s3_task >> snowflake_upload_task
