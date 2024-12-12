from diagrams import Diagram, Edge, Cluster 
from diagrams.aws.storage import S3 
from diagrams.saas.analytics import Snowflake
from diagrams.onprem.workflow import Airflow 
from diagrams.programming.framework import FastAPI 
from diagrams.custom import Custom 
from diagrams.onprem.client import Users 


with Diagram("Airflow Pipeline", show = False):
    
    # Define nodes   
    cfa_institute   = Custom("Data Source \n Website - CFA Institute", "./images/cfa-institute.png")
    pdf             = Custom("PDF Documents \n and images", "./images/PDF_documents.png")
    scraper         = Airflow("Content Extractor")
    airflow         = Airflow("Airflow \n Snowflake and S3 uploader") 
    s3_1            = S3("AWS S3\n(Images, PDFs)")
    snowflake       = Snowflake("Snowflake DB")

    
    with Cluster("Data Ingestion & Storage", direction = "LR"):
        cfa_institute >> Edge() >> scraper
        scraper >> Edge(label="Download") >> pdf
        pdf >> Edge() >> airflow
        airflow >> Edge(label="upload") >> s3_1
        airflow >> Edge(label="upload") >> snowflake