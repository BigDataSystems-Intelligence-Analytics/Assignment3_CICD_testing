import streamlit as st
import requests
from http import HTTPStatus
import os
from dotenv import load_dotenv


def login(email, password):
    data = { 
        'email': email, 
        'password': password
    }
    response = requests.post('http://' + os.getenv("HOSTNAME") + ':8000/login', json=data)
    return response.json()

def display_login_page():
    st.title("Login Page")

    email = st.text_input("Email", value="", key="login_email")
    password = st.text_input("Password", type="password", value="", key="login_password")

    if st.button("LogIn"):
        response = login(email, password)
        if response['status'] == HTTPStatus.OK:
            st.success("Logged in successfully!")
            st.session_state['logged_in'] = True  
            st.session_state['token'] = response['message'].get('token')
            st.rerun()
        else:
            st.error("Login failed. Please try again.")