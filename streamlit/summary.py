import streamlit as st
import requests
from http import HTTPStatus
import os 

def display_summary_page():
    st.title("Document Summary")

    document_id = st.session_state.get('selected_doc_id')
    auth_token = st.session_state.get('token', None)
    headers = {
        "Authorization": f"Bearer {auth_token}",
        "Content-Type": "application/json"
    }

    # Fetch the summary data for the selected document
    if document_id:
        summary_response = requests.get(f"http://{os.getenv('HOSTNAME')}:8000/summary/{document_id}", headers=headers)
        summary_data = summary_response.json()
        
        if summary_data['status'] == HTTPStatus.OK:
            summary_text = summary_data['message']

            st.text_area("Summary", value=summary_text, key="document_summary", disabled=True, height=300)
        else:
            st.error("Failed to load document summary.")
    else:
        st.error("No document selected to display the summary.")