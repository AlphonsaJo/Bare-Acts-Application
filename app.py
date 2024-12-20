import streamlit as st
import fitz  # PyMuPDF for PDF handling
import os
import re  # Regular expression library
import base64
from datetime import datetime
from bs4 import BeautifulSoup  # HTML parsing library
import requests  # HTTP library for making requests
import time
import pandas as pd
import string
import streamlit as st
import hashlib
from urllib.parse import urlparse, unquote

# Function to extract title information from text files in a folder
def extract_txt_titles(pdf_folder, txt_folder):
    pdf_files = os.listdir(pdf_folder)
    txt_files = os.listdir(txt_folder)
    titles = []

    for pdf_file in pdf_files:
        pdf_name, _ = os.path.splitext(pdf_file)
        txt_file = f"{pdf_name}.txt"
        
        if txt_file in txt_files:
            txt_path = os.path.join(txt_folder, txt_file)
            try:
                with open(txt_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                    # Extract metadata from the txt file
                    title_match = re.search(r'Title:\s*(.*)', content)
                    act_number_match = re.search(r'Act:\s*(\d+)', content)
                    act_year_match = re.search(r'Year:\s*(\d{4})', content)
                    date_match = re.search(r'Date:\s*(\[.*?\])', content)

                    if title_match and act_number_match and act_year_match and date_match:
                        title_info = {
                            'title': title_match.group(1).strip(),
                            'act_number': int(act_number_match.group(1)),
                            'act_year': int(act_year_match.group(1)),
                            'date': date_match.group(1).strip(),
                            'pdf': pdf_file  # Include PDF filename
                        }
                        titles.append(title_info)
                    else:
                        st.warning(f"Failed to extract metadata from {txt_file}")

            except Exception as e:
                st.warning(f"Error processing {txt_file}: {str(e)}")

    return titles

# Function to parse dates with various suffixes
def parse_date(date_str):
    suffixes = ['st', 'nd', 'rd', 'th']
    for suffix in suffixes:
        date_str = date_str.replace(suffix, '')
    try:
        return datetime.strptime(date_str, '%d %B, %Y').date()
    except ValueError:
        return None

# Function to display table of contents
def display_table_of_contents(titles, sort_option):
    if sort_option == 'Alphabetical Order':
        sorted_titles = sorted(titles, key=lambda x: x['title'])
    elif sort_option == 'Reverse Alphabetical Order':
        sorted_titles = sorted(titles, key=lambda x: x['title'], reverse=True)
    elif sort_option == 'Act Number':
        sorted_titles = sorted(titles, key=lambda x: x['act_number'])
    elif sort_option == 'Date':
        sorted_titles = sorted(titles, key=lambda x: x['date'] if x['date'] else datetime.min)

    st.subheader("Table of Contents - All Documents")
    st.write("Total Documents:", len(sorted_titles))
    
    if sorted_titles:
        # Create a DataFrame to hold the table of contents data
        data = []
        for title_info in sorted_titles:
            data.append({
                'Title': title_info['title'],
                'Act Number': title_info['act_number'],
                'Act Year': title_info['act_year'],
                'Date': title_info['date'],
                'PDF': title_info['pdf']
            })

        df = pd.DataFrame(data)

        st.write("### Table Columns:")
        st.write("- **Title**: The name of the act or document.")
        st.write("- **Act Number**: The numerical identifier of the act.")
        st.write("- **Act Year**: The year associated with the act.")
        st.write("- **Date**: The date when the act was enacted.")
        st.write("- **PDF**: The filename of the PDF containing the act.")

        for index, row in df.iterrows():
            col1, col2, col3, col4, col5, col6 = st.columns([3, 2, 2, 2, 2, 1])
            col1.write(row['Title'])
            col2.write(row['Act Number'])
            col3.write(row['Act Year'])
            col4.write(row['Date'])
            col5.write(row['PDF'])
            if col6.button("✓", key=f"select_{index}"):
                st.session_state.selected_pdf = row['PDF']
                st.session_state.current_option = 'Show Original Document'
                st.experimental_rerun()

    else:
        st.write("No documents found.")

# Function to extract text from the selected PDF
def extract_text_from_pdf(pdf_file):
    pdf_document = fitz.open(stream=pdf_file.getvalue())
    full_text = ""
    sections = []

    # Iterate through each page
    for page_num in range(min(pdf_document.page_count, 2)):  # Limiting to first 2 pages
        page = pdf_document[page_num]
        text = page.get_text()
        full_text += text + "\n\n"  # Add line breaks between pages

        # Extract section titles using regex
        pattern = re.compile(r'(\d+\.\s+[^\n]+)')
        matches = pattern.findall(text)
        sections.extend(matches)

    # Continue to extract full text beyond the first two pages
    for page_num in range(2, pdf_document.page_count):
        page = pdf_document[page_num]
        text = page.get_text()
        full_text += text + "\n\n"  # Add line breaks between pages

    return full_text, sections

# Function to display section content
def display_section_content(full_text, section_title):
    exact_section_title = f"{section_title.rstrip()}—"
    section_pattern = re.compile(r'(\b\d+\.\s+[^\d]+\s*—|\bShort title\.\s+[^\n]+\.\—)', re.DOTALL)
    sections = list(section_pattern.finditer(full_text))

    current_section_index = None
    for i, match in enumerate(sections):
        if exact_section_title in match.group():
            current_section_index = i
            break

    if current_section_index is not None:
        start_pos = sections[current_section_index].end()
        next_section_pattern = re.compile(r'\b(\d{1,2})\.')  # Only stop at "n." where n is less than 100

        next_section_match = next_section_pattern.search(full_text, pos=start_pos)
        if next_section_match:
            end_pos = next_section_match.start()
            section_content = full_text[start_pos:end_pos].strip()
        else:
            section_content = full_text[start_pos:].strip()

        # Clean up HTML tags/entities in the text
        soup = BeautifulSoup(section_content, "html.parser")
        cleaned_content = soup.get_text(separator="\n")
        st.write(cleaned_content)

        # Dictionary lookup for highlighted word
        highlighted_word_key = f"{section_title}_word_lookup"
        highlighted_word = st.sidebar.text_input(f"Enter a word to lookup ({section_title}):", key=highlighted_word_key)
        
        if highlighted_word:
            # Fetch definition from WordsAPI
            definition = fetch_definition(highlighted_word)
            if definition:
                st.sidebar.write(f"**Definition of '{highlighted_word}':** {definition}")
            else:
                st.sidebar.write(f"No definition found for '{highlighted_word}'")

    else:
        st.write(f"Content for section '{section_title}' not found.")

# Function to fetch word definition from WordsAPI
def fetch_definition(word):
    url = f'https://api.dictionaryapi.dev/api/v2/entries/en/{word}'
    
    try:
        response = requests.get(url)
        if (response.status_code == 200):
            data = response.json()
            definition = data[0]['meanings'][0]['definitions'][0]['definition']
            return definition
        else:
            st.write(f"Failed to fetch definition. Error: {response.status_code}")
            return None
    except requests.exceptions.RequestException as e:
        st.write(f"Error fetching definition: {str(e)}")
        return None

# Function to highlight search keywords in the text
def highlight_search_keywords(text, keyword):
    highlighted_text = re.sub(rf'({re.escape(keyword)})', r'<mark style="background-color: orange">\1</mark>', text, flags=re.IGNORECASE)
    return highlighted_text

# Updated function to display PDF
def display_pdf(file):
    base64_pdf = base64.b64encode(file.read()).decode('utf-8')
    pdf_display = f'<embed src="data:application/pdf;base64,{base64_pdf}" width="700" height="1000" type="application/pdf">'
    st.markdown(pdf_display, unsafe_allow_html=True)



# Function to extract keywords from a text
def extract_keywords(text):
    stopwords = set([
        "a", "an", "and", "are", "as", "at", "be", "but", "by", "for", "if", 
        "in", "into", "is", "it", "no", "not", "of", "on", "or", "such", 
        "that", "the", "their", "then", "there", "these", "they", "this", 
        "to", "was", "will", "with"
    ])
    words = re.findall(r'\b\w+\b', text.lower())
    keywords = [word for word in words if word not in stopwords and not word.isdigit()]
    return keywords

# Function to suggest BARE ACTS based on keywords comparison
def suggest_bare_acts(uploaded_pdf_text):
    bare_acts_pdf_path = 'Chronological Order_BARE ACTS.pdf'
    if not os.path.exists(bare_acts_pdf_path):
        st.error("Bare Acts PDF not found.")
        return

    try:
        with fitz.open(bare_acts_pdf_path) as bare_acts_pdf:
            bare_acts_text = ""
            for page_num in range(bare_acts_pdf.page_count):
                page = bare_acts_pdf[page_num]
                bare_acts_text += page.get_text()

        uploaded_pdf_keywords = extract_keywords(uploaded_pdf_text)
        bare_acts_keywords = extract_keywords(bare_acts_text)

        common_keywords = set(uploaded_pdf_keywords) & set(bare_acts_keywords)

        # Display common keywords in a tabular format
        if common_keywords:
            df_keywords = pd.DataFrame(list(common_keywords), columns=["Common Keywords"])
            st.write("### Common Keywords with BARE ACTS")
            st.table(df_keywords)
        else:
            st.write("No common keywords found with BARE ACTS.")

    except Exception as e:
        st.error(f"Error reading Bare Acts PDF: {str(e)}")

# Modify the main function to include the new option
def main():    
    st.title('BARE ACTS Application')

    # Initialize session state
    if 'authenticated' not in st.session_state:
        st.session_state.authenticated = False
    if 'current_option' not in st.session_state:
        st.session_state.current_option = None
    if 'selected_pdf' not in st.session_state:
        st.session_state.selected_pdf = None

    # Placeholder for logout confirmation message
    logout_message_placeholder = st.empty()

    # Display login screen if not authenticated
    if not st.session_state.authenticated:
        username = st.text_input('Username')
        password = st.text_input('Password', type='password')

        if st.button('Login'):
            if username == st.secrets["USERNAME"] and password == st.secrets["PASSWORD"]:
                st.session_state.authenticated = True
                st.success('Logged in as Admin.')
            else:
                st.error('Invalid credentials. Please try again.')

    # Main application if authenticated
    if st.session_state.authenticated:
        st.write("Welcome to the main application.")

        # Logout button
        if st.button('Logout'):
            st.session_state.authenticated = False
            logout_message_placeholder.info('Logged out successfully.')
            time.sleep(5)
            logout_message_placeholder.empty()
            st.experimental_rerun()

        # Sidebar for navigation and search
        st.sidebar.title("Navigation")
        option = st.sidebar.radio("Choose an option:", ('Show Original Document', 'Show Extracted Document', 'View Sections', 'Dictionary Lookup', 'Bare Acts - Table of Contents'))

        # Handle the selected PDF from the Table of Contents or Circulars
        if st.session_state.selected_pdf and st.session_state.current_option == 'Show Original Document':
            pdf_folder = 'All_Documents'
            pdf_path = os.path.join(pdf_folder, st.session_state.selected_pdf)
            if os.path.exists(pdf_path):
                with open(pdf_path, "rb") as pdf_file:
                    st.markdown("### Original Document")
                    display_pdf(pdf_file)
                    if st.button("Suggest BARE ACTS' Keywords"):
                        full_document_text, _ = extract_text_from_pdf(pdf_file)
                        suggest_bare_acts(full_document_text)
                st.session_state.selected_pdf = None
            else:
                st.error(f"File {st.session_state.selected_pdf} not found in {pdf_folder}")

        # File uploader widget
        uploaded_file = st.file_uploader("Choose a PDF file", type="pdf")

        if option == 'Bare Acts - Table of Contents':
            pdf_folder = 'All_Documents'
            txt_folder = 'Cleaned_Metadata'
            titles = extract_txt_titles(pdf_folder, txt_folder)

            if titles:
                sort_option = st.sidebar.selectbox("Sort by:", ('Alphabetical Order', 'Reverse Alphabetical Order', 'Act Number', 'Date'))
                display_table_of_contents(titles, sort_option)
            else:
                st.write("No documents found.")

        elif uploaded_file is not None:
            # Process the uploaded PDF file
            full_document_text, document_sections = extract_text_from_pdf(uploaded_file)
            
            if option == 'Show Original Document':
                st.markdown("### Original Document")
                display_pdf(uploaded_file)
                if st.button("Suggest BARE ACTS"):
                    suggest_bare_acts(full_document_text)
            
            elif option == 'Show Extracted Document':
                pages = full_document_text.split('\n\n')
                for i, page in enumerate(pages):
                    st.write(page)
                    if i < len(pages) - 1:
                        st.markdown('<hr>', unsafe_allow_html=True)
            
            elif option == 'View Sections':
                selected_sections = []
                for section in document_sections:
                    if st.sidebar.checkbox(section):
                        selected_sections.append(section)
                
                for section in selected_sections:
                    st.subheader(section)
                    display_section_content(full_document_text, section)
            
            elif option == 'Dictionary Lookup':
                word_to_lookup = st.sidebar.text_input("Enter a word to lookup:")
                if word_to_lookup:
                    definition = fetch_definition(word_to_lookup)
                    if definition:
                        st.sidebar.write(f"**Definition of '{word_to_lookup}':** {definition}")
                    else:
                        st.sidebar.write(f"No definition found for '{word_to_lookup}'")
            

if __name__ == '__main__':
    main()


