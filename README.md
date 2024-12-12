# Assignment 3
## Multi-Modal RAG Application
An interactive RAG based application built using FastAPI and Streamlit to explore and analyze publications from the CFA Institute Research Foundation. The application extract contents from the publications including images, graphs, PDF files and stores them in Snowflake database and Chroma DB. Users can interactively explore documents, generate on-the-fly summaries, and retrieve insights using multi-modal Retrieval-Augmented Generation (RAG) approach. This application supports robust Q/A functionality, incremental indexing of research notes, and comprehensive search within documents enhancing document discovery and analysis.


## Live Application Link
- Streamlit application link: http://18.219.124.78:8501/
- FastAPI: http://18.219.124.78:8000/health

## Codelabs Link
Codelabs documentation link: https://codelabs-preview.appspot.com/?file_id=1bqlMWizDFQHl4ucXhfDf2G6EH_YXzS_qWhY8qBONL2w#0
## **Video of Submission**
Demo Link: https://youtu.be/TCs0_5oaGkE



## Attestation and Team Contribution
**WE ATTEST THAT WE HAVEN’T USED ANY OTHER STUDENTS’ WORK IN OUR ASSIGNMENT AND ABIDE BY THE POLICIES LISTED IN THE STUDENT HANDBOOK**

Name | NUID | Contribution% | Work_Contributed
--- | --- | --- | --- |
Sandeep Suresh Kumar | 002841297 | 33% | Scraping, RAG Implementation, Report Generation, Research Notes
Deepthi Nasika       | 002474582 | 33% | FastAPI, Summary Generation, Streamlit, Deployment
Gomathy Selvamuthiah | 002410534 | 33% | Snowflake Database, AirFlow, Streamlit, Documentation
Ramy Solanki         | 002816593 | 33% | JWT, Amazon S3, Dockerization, Documentation

## Problem Statement
With the rapid growth of publications, it has become increasingly challenging to analyze complex documents, interpret images and graphs, and derive meaningful business insights. This project aims to create a robust solution that allows users to interact with documents through Q&A functionality. By leveraging Retrieval-Augmented Generation (RAG), the application provides relevant responses, images, and graphs specific to user questions, simplifying the analysis process and enabling users to obtain accurate insights efficiently. The application primarily focuses on:

1. Content Extraction and Storage: Scrape content from the CFA Institute Research Foundation website, loading files onto S3 and storing textual data, such as titles and summaries, in a Snowflake database.
2. Automated Data Ingestion: Automate the data ingestion process with an Airflow pipeline, ensuring efficient and structured data handling.
3. API Endpoints: Develop multiple API endpoints to support services like document exploration and dropdown selection for document access, RAG interaction with UI.
4. Real-Time Summary Generation: Generate document summaries on the fly using NVIDIA’s advanced services.
5. Multi-Modal RAG with Cleanlabs Integration: Implement multi-modal RAG to enhance response relevance and integrate Cleanlabs for response trustworthiness.
6. Comprehensive Report Generation: Create reports that include responses, images, and graphs relevant to user queries for a richer understanding.
7. Research Notes Validation and Indexing: Validate, store, and incrementally index research notes to facilitate efficient future searches and analysis.


## Architecture Diagram
### 1. Core Application Pipeline
![Architecture Diagram](https://github.com/BigDataIA-Fall2024-TeamB6/Assignment3/blob/streamlit/UI_FirstDraft/diagram/core_application_pipeline.png)



### 2. Airflow Pipeline
![Architecture Diagram](https://github.com/BigDataIA-Fall2024-TeamB6/Assignment3/blob/streamlit/UI_FirstDraft/diagram/airflow_pipeline.png)



## Project Goals
### Airflow Pipeline
#### 1. Objective
- Streamline the process of extracting contents from publications website which includes textual data, images, pdf files, JSON files and loading files with respect to each docuemnt on Amazon S3 bucket
- Automating data storage process by integrating data ingestion with Snowflake database to load textual publications information like title, brief summary, cover image url and pdf url.
#### 2. Tools
- Extraction of data from publications website - BeautifulSoup
- Database - Snowflake Database
- File storage - Amazon S3 (Simple Storage Service)
- Data Automation - Airflow
- 
#### 3. Output
- Extracted different types of files which are stored in Amazon S3. Document ID is generated with respect to every publication. All the files fetched under that publication will be stored in document_id folder in S3 bucket - publications_info
- Extracted textual data which are the details of the publication like title, brief summary, cover image url, pdf url are stored into table publications_info. Users information is being recorded in users table. All the responses to user queries are recorded in research_notes table. All the tables are stored in Snowflake Database

### Multi-modal RAG
#### 1. Objective
- Process entire PDF documents, including text, images, and graphs, by dividing large text into smaller chunks and converting images from pixel format to base64 for efficient processing
- Each chunk of text and base64-encoded image is transformed into vector embeddings, which are stored in a vector database. The application then uses cosine similarity to match user questions with these embeddings, returning relevant images, text, and graphs as part of the response
- Additionally, Cleanlabs integration provides a trustworthiness score, validating the accuracy of responses generated by the RAG system according to the user prompt
#### 2. Tools
- Document Parsing - 
- Converting to Embeddings - 
- Vector Database - Chroma DB
- Trustworthiness Score - Cleanlabs
#### 3. Output
- The vector embeddings of text chunks and base64 images are stored in Chroma DB, allowing efficient retrieval of relevant content in response to user queries
- Responses to user queries include text, images, and graphs, all aligned with the user prompt, alongside a trustworthiness score provided by Cleanlabs
- Generated responses, research notes, and trust scores are recorded in Snowflake for structured access and future reference


### FastAPI
#### 1. Objective
- Provides end points for connecting Streamlit User Interface with Multi-modal RAG application, Vector Database, Snowflake Database, and Amazon S3 bucket
- Integrating OpenAI, NVIDIA services and Cleanlabs with RAG application using FastAPI for enhanced document analysis, summarization, and validating response trustworthiness
- Implementation of secure authentication and authorization protocols
- Deliver responses in a streamlined JSON format for consistent data handling
#### 2. Tools
- `fastapi[standard]` for building a standard FastAPI application
- `python-multipart` for installing additional dependencies for FastAPI application
- `snowflake-connector-python` for interacting with Snowflake database
- `PyJWT` for authenticating and authorizing users with JSON Web Tokens (JWT)
- `openai` for prompting OpenAI's GPT-4o model to get LLM Response
- `tiktoken` for disintegrating prompts into tokens of known sizes
- `PyPDF2` for extracting text from the pdf files
- `langchain` for RAG implementation
- `unstructured[all-docs]` for text and image extraction from PDFs
- `cleanlab-studio` for generating trustworthy score
#### 3. Output
FastAPI provides a number of endpoints for interacting with the service:
- `GET` - `/health` - To check if the FastAPI application is setup and running
- `POST` - `/register` - To sign up new users to the service
- `POST` - `/login` - To sign in existing users
- `GET` - `/exploredocs` - *Protected* - To fetch 'x' number of documents from the database
- `GET` - `/load_docs/{document_id}` - *Protected* - To load publications information like title, brief summary, cover image url from the database
- `GET` - `/summary/{document_id}` - *Protected* - To generate on the fly summary of the document using NVIDIA services
- `POST` - `/chatbot/{document_id}` - *Protected* - Q/A interface for user to interact with the selected document

FastAPI ensures that every response is returned in a consistent JSON format with HTTP status, type (data type of the response content) message (response content), and additional fields if needed


### Streamlit
#### 1. Objective
- To provide a user-friendly interface that enables users to explore publications, generates on-the-fly summaries for selected document, and provides question answering interface for users to interact with documents
- The responses and reports will be generated by RAG when user prompts with a question specific to docuement. Research notes are the reports with response, images and graphs relevant to the user prompt and are stored in the database

#### 2. Tools
- Streamlit (web application framework), Requests (API calls for data retrieval)

#### 3. Output
- Home Page gives an overview of how to use RAG Application for users like a user-manual,
- Login & Registration Page allows users to authenticate their login securely,
- Document explorer page allows users to select from a list of publications available, and load the publications info like title, brief summary, cover image,
- Summary page generates the summary using NVIDIA model with respect to the selected document
- Question Answering Interface allows users to interact with the document, returns reports with responses to user question prompts along with images and graphs relevant to prompts

### Deployment
- Containerization of FastAPI and Streamlit applications using Docker
- Deployment to a public cloud platform using Docker Compose
- Ensuring public accessibility of the deployed applications - Streamlit and FastAPI
- Providing clear instructions for users to interact with the RAG application and explore its functionalities
- The FastAPI and Streamlit are containerized using Docker, and orchestrated through docker compose and the Docker images are pushed to Docker Hub. For deploying the Docker containers, we use an Amazon Web Services (AWS) EC2 instance within the t3-medium tier


## Data Source
1. CFA Institute Research Foundation Publications: https://rpc.cfainstitute.org/en/research-foundation/publications#sort=%40officialz32xdate%20descending&f:SeriesContent=%5BResearch%20Foundation%5D

## Amazon S3 Link
- s3://publications-info/{document_id}


## Technologies
[![BeautifulSoup](https://img.shields.io/badge/BeautifulSoup-FFD43B?style=for-the-badge&logo=python&logoColor=white)](https://www.crummy.com/software/BeautifulSoup/)
[![Selenium](https://img.shields.io/badge/Selenium-43B02A?style=for-the-badge&logo=selenium&logoColor=white)](https://www.selenium.dev/)
[![Python](https://img.shields.io/badge/Python-FFD43B?style=for-the-badge&logo=python&logoColor=blue)](https://www.python.org/)
[![Amazon S3](https://img.shields.io/badge/Amazon%20S3-569A31?style=for-the-badge&logo=amazonaws&logoColor=white)](https://aws.amazon.com/s3/)
[![Snowflake](https://img.shields.io/badge/Snowflake-29B1E5?style=for-the-badge&logo=snowflake&logoColor=white)](https://www.snowflake.com/)
[![Airflow](https://img.shields.io/badge/Airflow-17B3A8?style=for-the-badge&logo=apacheairflow&logoColor=white)](https://airflow.apache.org/)
[![Docker](https://img.shields.io/badge/Docker-2496ED?style=for-the-badge&logo=docker&logoColor=white)](https://www.docker.com/)
[![Postman](https://img.shields.io/badge/Postman-FF6C37?style=for-the-badge&logo=postman&logoColor=white)](https://www.postman.com/)
[![FastAPI](https://img.shields.io/badge/FastAPI-009688?style=for-the-badge&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![LangChain](https://img.shields.io/badge/LangChain-5A67D8?style=for-the-badge)](https://www.langchain.com/)
[![NVIDIA](https://img.shields.io/badge/NVIDIA-76B900?style=for-the-badge&logo=nvidia&logoColor=white)](https://www.nvidia.com/)
[![Cleanlab](https://img.shields.io/badge/Cleanlab-000000?style=for-the-badge&logo=cleanlab&logoColor=white)](https://cleanlab.ai/)
[![OpenAI](https://img.shields.io/badge/OpenAI-000000?style=for-the-badge&logo=openai&logoColor=white)](https://openai.com/)
[![Chroma DB](https://img.shields.io/badge/Chroma%20DB-FF5A5F?style=for-the-badge&logo=chromadb&logoColor=white)](https://www.trychroma.com/)
[![Streamlit](https://img.shields.io/badge/Streamlit-FF4B4B?style=for-the-badge&logo=streamlit&logoColor=white)](https://streamlit.io/)

## Prerequisites
Software Installations required for the project
1. Python Environment
A Python environment allows you to create isolated spaces for your Python projects, managing dependencies and versions separately

2. Poetry Environment/ Python Virtual Environment
- Poetry is a dependency management tool that helps you manage your Python packages and projects efficiently where a user can install all the dependencies onto pyproject.toml file
- Python Virtual Environment helps you manage your Python packages efficiently where a user can include all the dependencies in requirements.txt file

4. Packages
The project requires multiple packages for loading environment variables: python-dotenv, for loading files from hugging face: huggingface-hub, for connecting to MySQL database: mysql-connector-python, for file storage: google-cloud-storage, for extracting PDF contents from Azure AI Document Intelligence tool: azure-ai-formrecognizer, for extracting PDF contents from Adobe PDF Extract pdfservices-sdk, for extracting PDF contents with open source tool: pymupdf
```bash
pip install -r requirements.txt
```

4. Visual Studio Code
An integrated development environment (IDE) that provides tools and features for coding, debugging, and version control.

5. Docker
 Docker allows you to package applications and their dependencies into containers, ensuring consistent environments across different platforms. All the dependencies will be installed on docker-compose.yaml file with env file

6. Amazon S3 Bucket
Amazon S3 (Simple Storage Service) is a cloud storage solution from AWS used to store files and objects. It provides scalable, secure, and cost-effective storage for all extracted publication files, including images, PDFs, and JSON data, organized under unique document IDs. This bucket serves as the primary cloud storage for file data accessible by the application.

8. Streamlit
Streamlit is an open-source app framework that allows you to create interactive web applications easily.

9. Snowflake Database
Snowflake is a cloud-based data warehousing and analytics service that supports structured data storage. This project uses Snowflake to store extracted textual data, such as titles, summaries, cover image URLs, and PDF URLs from CFA publications. Snowflake also hosts user data and stores responses to user queries, enabling efficient querying and data retrieval.

10. ChromaDB Vector Database
ChromaDB is a specialized vector database used for storing vector embeddings of processed document contents, such as text chunks and image embeddings in base64 format. It enables efficient retrieval by calculating cosine similarity between user query embeddings and stored content embeddings, ensuring relevant document content is retrieved quickly and accurately for user queries.


## Project Structure
```
Assignment3/
├── airflow
│   ├── Dockerfile
│   ├── POC
│   │   ├── MultiModalRAG.ipynb
│   │   ├── Stage1.ipynb
│   │   ├── Stage2.ipynb
│   │   ├── Stage3.py
│   │   └── stage1.csv
│   ├── chromedriver
│   │   ├── LICENSE.chromedriver
│   │   ├── THIRD_PARTY_NOTICES.chromedriver
│   │   └── chromedriver.exe
│   ├── dags
│   │   └── airflow_pipeline.py
│   ├── docker-compose.yaml
│   ├── rag_pipeline.py
│   ├── requirements.txt
│   ├── scraper.py
│   ├── snowflakeDB.py
│   ├── upload_to_S3.py
│   └── webscrape.py
├── diagram
│   ├── AirflowPipeline.py
│   ├── airflow_pipeline.png
│   ├── core_app_architecture.py
│   ├── core_application_pipeline.png
│   └── images
│       ├── Chroma.png
│       ├── Download.png
│       ├── InMemoryStore.png
│       ├── Langchain.png
│       ├── MultiVectorRetriever.png
│       ├── Nvidia-Logo.png
│       ├── Nvidia.png
│       ├── OpenAI.png
│       ├── PDF_documents.png
│       ├── PNG.png
│       ├── Question.png
│       ├── Snowflake.png
│       ├── Streamlit.png
│       ├── Text.png
│       ├── Unstructured.png
│       ├── cfa-institute.png
│       └── cleanlabs.png
├── docker-compose.yml
├── fastapi
│   ├── Dockerfile
│   ├── connectDB.py
│   ├── main.py
│   ├── models.py
│   ├── requirements.txt
│   ├── routers.py
│   └── services.py
└── streamlit
    ├── Dockerfile
    ├── app.py
    ├── documentexplorer.py
    ├── homepage.py
    ├── loginpage.py
    ├── overview.py
    ├── qainterface.py
    ├── registerpage.py
    ├── requirements.txt
    └── summary.py

```

## How to run the application locally
1. **Clone the Repository**: Clone the repository onto your local machine and navigate to the directory within your terminal.

   ```bash
   git clone https://github.com/BigDataIA-Fall2024-TeamB6/Assignment3
   ```

2. **Install Docker**: Install docker and `docker compose` to run the application:

   - For Windows, Mac OS, simply download and install Docker Desktop from the official website to install docker and `docker compose` 
   [Download Docker Desktop](https://www.docker.com/products/docker-desktop/)

   - For Linux (Ubuntu based distributions), 
   ```bash
   # Add Docker's official GPG key:
   sudo apt-get update
   sudo apt-get install ca-certificates curl
   sudo install -m 0755 -d /etc/apt/keyrings
   sudo curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
   sudo chmod a+r /etc/apt/keyrings/docker.asc

   # Add the repository to Apt sources:
   echo \
   "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu \
   $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | \
   sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
   sudo apt-get update 

   # Install packages for Docker
   sudo apt-get install docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

   # Check to see if docker is running 
   sudo docker run hello-world

3. **Run the application:** In the terminal within the directory, run 
   ```bash
   docker-compose up

   # To run with logging disabled, 
   docker-compose up -d

4. In the browser, 
   - visit `localhost:8501` to view the Streamlit application
   - visit `localhost:8000/docs` to view the FastAPI endpoint docs
