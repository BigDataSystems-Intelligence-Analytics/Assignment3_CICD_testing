import streamlit as st
import requests
from http import HTTPStatus
import os
from dotenv import load_dotenv

load_dotenv()

def register(first_name, last_name, email, phone, password):
    data = { 
        'first_name': first_name,
        'last_name': last_name, 
        'phone': phone,
        'email': email, 
        'password': password
    }
    response = requests.post('http://' + os.getenv("HOSTNAME") + ':8000/register', json=data)
    return response.json()

def display_register_page():
    st.title("Register Page")

    first_name = st.text_input("First Name", key="register_first_name")
    last_name = st.text_input("Last Name", key="register_last_name")
    email = st.text_input("Email", key="register_email")
    phone = st.text_input("Phone", key="register_phone")
    password = st.text_input("Password", type="password", key="register_password")
    
    if st.button("SignUp"):
        response = register(first_name, last_name, email, phone, password)
        print(response)  # For debugging purposes
        if response['status'] == HTTPStatus.OK:
            st.success("Registered successfully!")
            st.session_state["logged_in"] = True 
            st.session_state['token'] = response['message'].get('token')
            st.session_state['page'] = 'documentexplorer'  # Navigate to the search engine
            st.rerun()
        else:
            st.error("Registration failed/ User Already Exists. Please try again")
