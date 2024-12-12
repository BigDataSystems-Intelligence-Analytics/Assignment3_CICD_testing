import io
import os
import re
import json
import uuid
import base64
from PIL import Image
from unidecode import unidecode
from dotenv import load_dotenv
from cleanlab_studio import Studio
from langchain_chroma import Chroma
from langchain_openai import ChatOpenAI
from langchain.storage import InMemoryStore
from langchain_core.documents import Document
from langchain_openai import OpenAIEmbeddings
import unstructured_pytesseract as pytesseract
from langchain_core.messages import HumanMessage
from unstructured.partition.pdf import partition_pdf
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain.retrievers.multi_vector import MultiVectorRetriever
from langchain_core.runnables import RunnableLambda, RunnablePassthrough
from langchain_nvidia_ai_endpoints import ChatNVIDIA

# Load environment variables
load_dotenv()

# Provide path to Tesseract OCR (Windows only)
pytesseract.pytesseract.tesseract_cmd = "C:\\Program Files\\Tesseract-OCR\\tesseract.exe"



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


def invoke_pipeline(document_id, prompt_type = "full_text", report_as_source = False):

    # Find the PDF document in the directory of document_id
    fpath = os.path.join(os.getcwd(), os.getenv("DOWNLOAD_DIRECTORY", "downloads") , document_id)
    dir_contents = os.listdir(fpath)
    
    for file in dir_contents:
        if file.endswith(".pdf"):
            fname = file

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

    # Check retrieval
    query = input("Ask a question: ")

    if prompt_type == "report":
        if report_as_source:
            # RAG chain for Q&A, with report_vectorstore as source
            chain_multimodal_rag = multi_modal_rag_chain(retriever_report, prompt_type="report", max_tokens=2048)
            docs = retriever_report.invoke(query)
        
        else:
            # RAG chain for generating reports, with full_text_vectorstore as source
            chain_multimodal_rag = multi_modal_rag_chain(retriever_multi_vector_img, prompt_type="report", max_tokens=2048)
            docs = retriever_multi_vector_img.invoke(query)

    if prompt_type == "full_text":
        if report_as_source:
            # Default Q&A RAG chain, with report_vectorstore as source
            chain_multimodal_rag = multi_modal_rag_chain(retriever_report, prompt_type="default")
            docs = retriever_report.invoke(query)
        
        else:
            # Default Q&A RAG chain, with full_text_vectorstore as source
            chain_multimodal_rag = multi_modal_rag_chain(retriever_multi_vector_img, prompt_type="default")
            docs = retriever_multi_vector_img.invoke(query)
    

    # Check what docs were retrieved
    print("Documents retrieved: ", len(docs))
    for i in range(len(docs)):
        print(f"Document: {i}")
        print(docs[i])

    print("Image Documents fetched:")
    doc_limit = len(docs) if len(docs) < 3 else 3
    
    images_retrieved = {
        "length": 0,
        "content": []
    }
    for i in range(doc_limit):
        if looks_like_base64(docs[i]):
            images_retrieved['length'] += 1
            images_retrieved['content'].append(docs[i])

    print(images_retrieved)

    # Run the default RAG chain
    response = chain_multimodal_rag.invoke(query)
    print("LLM's response:")
    print(response)

    # Get trust score
    studio = Studio(os.getenv("TLM_API_KEY"))
    tlm = studio.TLM(
        options = {
            "model"     : "gpt-4o"
        }
    )
    score = tlm.get_trustworthiness_score(prompt=query, response=response)

    print("Trust score:")
    print(score)

    # Save and index reports in report_vectorstore
    if prompt_type == "report":
        save_report_vectorstore(report_vectorstore, response)

if __name__ == "__main__":
    invoke_pipeline(
        document_id         = "3dfc65a6f4dd48d1ae58c254a9c0b418",
        prompt_type         = "report",
        report_as_source    = False
    )
    