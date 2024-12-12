from diagrams import Diagram, Edge, Cluster 
from diagrams.aws.storage import S3 
from diagrams.programming.framework import FastAPI 
from diagrams.custom import Custom 
from diagrams.onprem.client import Users 


with Diagram("Core Application Pipeline", show = False):
    
    # Define nodes
    users           = Users("End Users")
    document_request= Custom("Request to\nDownload\nChosen PDF", "./images/Download.png")
    question        = Custom("Question", "./images/Question.png")
    streamlit_app   = Custom("Streamlit", "./images/Streamlit.png") 
    s3_2            = S3("AWS S3\n(Images, PDFs)")
    cleanlabs       = Custom("CleanLabs\nTrusted Language Model", "./images/cleanlabs.png")
    
    fastapi         = FastAPI("FastAPI")
    pdf2            = Custom("PDF Document", "./images/PDF_documents.png")
    nvidia          = Custom("Llama 3.1 405b\non\nNvidia NIM", "./images/Nvidia.png")
    unstructured    = Custom("Unstructured\nParsing PDFs \nwith\nMachine Learning", "./images/Unstructured.png")
    extracted_text  = Custom("Text", "./images/Text.png")
    extracted_image = Custom("Images, Tables", "./images/PNG.png")
    openai_embed_1  = Custom("OpenAI\nEmbeddings", "./images/OpenAI.png")
    openai_embed_2  = Custom("OpenAI\nEmbeddings", "./images/OpenAI.png")
    chromadb        = Custom("ChromaDB\nVector Store", "./images/Chroma.png")
    openai_llm1     = Custom("Image Summary\nwith\nGPT-4o", "./images/OpenAI.png")
    openai_llm2     = Custom("GPT-4o", "./images/OpenAI.png")
    memory          = Custom("In-Memory\nDocument Store", "./images/InMemoryStore.png")
    mmr             = Custom("MultiVector\nRetriever", "./images/MultiVectorRetriever.png")


    with Cluster("RAG Application", direction = "RL"):
        streamlit_app << Edge() << users
        fastapi << Edge() << streamlit_app
        question << Edge(label="User asks question") << fastapi
        document_request << Edge(label="Forward request\nto FastAPI") << streamlit_app
        fastapi << Edge() << document_request
        fastapi << Edge() << s3_2
        nvidia << Edge(label="Get Document Summary") >> fastapi
        pdf2 << Edge(label="Save PDF locally for text, image extraction") << fastapi
        unstructured << Edge() << pdf2
        extracted_text << Edge(label="Document Chunks") << unstructured
        extracted_image << Edge() << unstructured
        openai_llm1 << Edge(label="Images in Base64 format") << extracted_image
        openai_embed_1 << Edge(label="Document Chunks") << extracted_text
        chromadb << Edge(label="Save and Index\nembedded content") << openai_embed_1
        openai_embed_1 << Edge(label="Image summary") << openai_llm1
        memory << Edge(label="Store in RAM\nfaster access") << extracted_image
        openai_embed_2 << Edge() << question
        mmr << Edge() << openai_embed_2
        mmr << Edge(label="Relevant Document Chunks") << chromadb
        mmr << Edge(label="Relevant Images") << memory
        openai_llm2 << Edge(label="Question with relevant context") << mmr 
        fastapi << Edge(label="Answer") << openai_llm2
        cleanlabs << Edge(label="Get Trust Score\nfor LLM response") >> fastapi
        fastapi << Edge(label="Relevant Images") << memory
        streamlit_app << Edge(label="Answer or Report\n(with images)") << fastapi
        users << Edge() << streamlit_app