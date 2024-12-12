import streamlit as st
from overview import display_overview_page
from documentexplorer import display_document_explorer
from summary import display_summary_page
from qainterface import display_qa_interface

def main():
    # Initialize session state for page navigation
    if 'page' not in st.session_state:
        st.session_state['page'] = 'overview'

    # Sidebar for navigation (only after login)
    if st.session_state.get('logged_in', False):
        st.sidebar.title("Navigation")
        nav_option = st.sidebar.radio(
            "Choose a page:",
            ('Document Explorer', 'Summary', 'Q/A Interface')
        )

        # Update session state based on sidebar selection
        if nav_option == 'Document Explorer' and st.session_state['page'] != 'documentexplorer':
            st.session_state['page'] = 'documentexplorer'
            st.rerun()
        elif nav_option == 'Summary' and st.session_state['page'] != 'summary':
            st.session_state['page'] = 'summary'
            st.rerun()
        elif nav_option == 'Q/A Interface' and st.session_state['page'] != 'Q/A Interface':
            st.session_state['page'] = 'Q/A Interface'
            # st.rerun()    

        # Logout button
        if st.sidebar.button("Logout"):
            st.session_state['logged_in'] = False
            st.session_state['page'] = 'overview'  # Go back to overview page
            st.rerun()

    # Display the appropriate page based on session state
    if st.session_state['page'] == 'overview':
        display_overview_page()
    elif st.session_state['page'] == 'documentexplorer':
        display_document_explorer()
    elif st.session_state['page'] == 'summary':
        display_summary_page()
    elif st.session_state['page'] == 'Q/A Interface':
        display_qa_interface()

if __name__ == '__main__':
    main()
