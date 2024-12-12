import streamlit as st
import requests
from http import HTTPStatus
import os
import re
import boto3

# Function to download file from S3
def download_s3_file(bucket_name, s3_key, local_path):
    s3 = boto3.client('s3')
    s3.download_file(bucket_name, s3_key, local_path)

# Function to display the Document Explorer page
def display_document_explorer():
    st.title("Explore Publications")
    
    st.session_state['page'] = 'documentexplorer'

    auth_token = st.session_state.get('token', None)

    headers = {
        "Authorization": f"Bearer {auth_token}",
        "Content-Type": "application/json"
    }

    # Fetch all the publications available count = 10 default
    response = requests.get(f"http://{os.getenv('HOSTNAME')}:8000/exploredocs?count=50", headers=headers)
    response_data = response.json()

    if response_data['status'] == HTTPStatus.OK and isinstance(response_data.get('message'), list):
        documents_list = response_data['message']
        documents_dict = {item['title']: item['document_id'] for item in documents_list}
        documents = list(documents_dict.keys())

        st.session_state['documents'] = documents
        st.session_state['documents_dict'] = documents_dict

    else:
        st.error("Failed to fetch documents from the database.")

    # Check if documents are available in session_state
    if 'documents' in st.session_state:
        documents = st.session_state['documents']
        documents_dict = st.session_state['documents_dict']

        # Display the fetched publications in a selectbox
        selected_doc = st.selectbox("Select a publication:", documents)

        # Store the selected publication in session_state
        if selected_doc:
            st.session_state['selected_doc'] = selected_doc
            st.session_state['selected_doc_id'] = documents_dict[selected_doc]
    else:
        st.error("Documents not in sessions state")
    

    # Check if a prompt has been selected
    if 'selected_doc' in st.session_state:
        document_id = st.session_state['selected_doc_id']

        # Load Data button after prompt selection
        if st.button("Load Data"):
            headers = {
                "Authorization": f"Bearer {auth_token}",
                "Content-Type": "application/json"
            }
            # Fetch the data for the selected prompt using the task ID
            response = requests.get(f"http://{os.getenv('HOSTNAME')}:8000/load_docs/{document_id}", headers=headers)
            load_data = response.json()

            if load_data['status'] == HTTPStatus.OK:
                doc_id = load_data['message'][0]
                title = load_data['message'][1]
                overview = re.sub(r'\s+', ' ', load_data['message'][2].strip())
                image_url = load_data['message'][3]
                pdf_url = load_data['message'][4]

                # Check for S3 URL and display image
                if image_url and image_url.startswith("s3://"):
                    # Extract bucket and key from the S3 URL
                    bucket_name, s3_key = image_url[5:].split("/", 1)
                    local_image_path = "/tmp/temp_image.png"  # Fixed local path

                    # Download and display the image
                    download_s3_file(bucket_name, s3_key, local_image_path)
                    st.write("Document Image")
                    st.image(local_image_path, width=300)
                else:
                    st.warning("No image available for this document.")

                st.text_area("Title", value=title, key="document_title", disabled=True, height=100)
                st.text_area("Overview", value=overview, key="document_overview", disabled=True, height=100)
                
            else:
                st.error("Failed to load document data.")
