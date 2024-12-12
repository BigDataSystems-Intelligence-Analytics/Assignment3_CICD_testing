import streamlit as st

def display_home_page():

    # Set the title of the application
    st.title("Multi-modal RAG Application!")

    # Introduction
    st.markdown("""
    This interactive platform is designed to help you explore and analyze publications from the CFA Institute Research Foundation using advanced Retrieval-Augmented Generation (RAG) techniques. Here’s how to navigate through the application seamlessly:
    """)

    # Getting Started Section
    st.subheader("Getting Started")

    # Login/Register
    st.markdown("""
    1. **Login/Register**
    - **Access Your Account**: Click on the **Login/Register** link at the top of the page. Enter your credentials to access the application. If you don’t have an account, simply register for one by providing your personal details.
    - **Troubleshooting**: If you encounter issues logging in, ensure your credentials are correct. If you’re a new user, check your email for confirmation after registration.
    """)

    # Explore Publications
    st.markdown("""
    2. **Explore Publications**
    - **Access the Publications Page**: After logging in, you will be directed to the **Explore Publications Page**. Here, you can browse through the available publications.
    - **Select a Publication**: Use the dropdown menu labeled **"Select a publication:"** to choose a document of interest.
    - **Load Document Details**: Click the **"Load Data"** button to view more information about the selected publication, including its image, title, and overview.
    """)

    # View Document Summaries
    st.markdown("""
    3. **View Document Summaries**
    - **Navigate to the Summary Page**: From the sidebar, click on **"Documents Summary"** to generate a concise summary of the selected document.
    - **Understanding Summaries**: Summaries are fetched from our advanced services and displayed in a read-only format. If no document is selected, you'll be prompted to choose one first.
    """)

    # Engage with the Q/A Interface
    st.markdown("""
    4. **Engage with the Q/A Interface**
    - **Context-Sensitive Chat**: Ensure you have a document selected; otherwise, you’ll be prompted to choose one. The Q/A interface allows you to ask specific questions about the publication.
    - **Select Settings**: Choose your **Prompt Type** (report or text) and **Source** (Document or Research notes) to tailor the responses you receive.
    - **Submit Your Questions**: Type your question in the **"Ask something:"** input box and press enter. Your questions will appear in the chat log, and responses will include a trust score for credibility.
    """)

    # Explore Research Notes
    st.markdown("""
    5. **Explore Research Notes**
    - **Access Saved Notes**: Your interactions will generate research notes, which can be revisited for quick access to previously obtained insights. Use the search functionality to find specific information within your notes or across documents.
    """)

    # Need Help?
    st.markdown("""
    6. **Need Help?**
    - **Support Section**: If you have questions or encounter issues, visit the **Help** section for FAQs and troubleshooting tips. You can also contact support through the application for further assistance.
    """)

    # Tips for an Enhanced Experience
    st.subheader("Tips for an Enhanced Experience")
    st.markdown("""
    - **Stay Logged In**: For seamless access, remain logged in while exploring documents and summaries.
    - **Utilize Search**: Use the search feature to quickly find documents or specific information within your research notes.
    - **Provide Feedback**: Your insights help us improve! Share any feedback or suggestions through the designated channels in the app.
    """)

    # Call to Action
    st.markdown("""
    ### **Get Started Now!**
    Explore the wealth of knowledge contained in CFA Institute publications and unlock insights that matter to you. Click the **Login/Register** button to begin your journey!
    """)

    # Getting Started Section
    st.subheader("Getting Started")

    # Login/Register
    st.markdown("""
    1. **Login/Register**
    - **Access Your Account**: Click on the **Login/Register** link at the top of the page. Enter your credentials to access the application. If you don’t have an account, simply register for one by providing your personal details.
    - **Troubleshooting**: If you encounter issues logging in, ensure your credentials are correct. If you’re a new user, check your email for confirmation after registration.
    """)

    # Explore Publications
    st.markdown("""
    2. **Explore Publications**
    - **Access the Publications Page**: After logging in, you will be directed to the **Explore Publications Page**. Here, you can browse through the available publications.
    - **Select a Publication**: Use the dropdown menu labeled **"Select a publication:"** to choose a document of interest.
    - **Load Document Details**: Click the **"Load Data"** button to view more information about the selected publication, including its image, title, and overview.
    """)

    # View Document Summaries
    st.markdown("""
    3. **View Document Summaries**
    - **Navigate to the Summary Page**: From the sidebar, click on **"Documents Summary"** to generate a concise summary of the selected document.
    - **Understanding Summaries**: Summaries are fetched from our advanced services and displayed in a read-only format. If no document is selected, you'll be prompted to choose one first.
    """)

    # Engage with the Q/A Interface
    st.markdown("""
    4. **Engage with the Q/A Interface**
    - **Context-Sensitive Chat**: Ensure you have a document selected; otherwise, you’ll be prompted to choose one. The Q/A interface allows you to ask specific questions about the publication.
    - **Select Settings**: Choose your **Prompt Type** (report or text) and **Source** (Document or Research notes) to tailor the responses you receive.
    - **Submit Your Questions**: Type your question in the **"Ask something:"** input box and press enter. Your questions will appear in the chat log, and responses will include a trust score for credibility.
    """)

    # Explore Research Notes
    st.markdown("""
    5. **Explore Research Notes**
    - **Access Saved Notes**: Your interactions will generate research notes, which can be revisited for quick access to previously obtained insights. Use the search functionality to find specific information within your notes or across documents.
    """)

    # Need Help?
    st.markdown("""
    6. **Need Help?**
    - **Support Section**: If you have questions or encounter issues, visit the **Help** section for FAQs and troubleshooting tips. You can also contact support through the application for further assistance.
    """)

    # Tips for an Enhanced Experience
    st.subheader("Tips for an Enhanced Experience")
    st.markdown("""
    - **Stay Logged In**: For seamless access, remain logged in while exploring documents and summaries.
    - **Utilize Search**: Use the search feature to quickly find documents or specific information within your research notes.
    - **Provide Feedback**: Your insights help us improve! Share any feedback or suggestions through the designated channels in the app.
    """)

    # Call to Action
    st.markdown("""
    ### **Get Started Now!**
    Explore the wealth of knowledge contained in CFA Institute publications and unlock insights that matter to you. Click the **Login/Register** button to begin your journey!
    """)