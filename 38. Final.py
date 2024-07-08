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

# Function to display user manual
def display_user_manual():
    st.title("User Manual")
    st.markdown("""
    #### Show Original Document
    - Displays the original PDF document as uploaded by the user.

    #### Show Extracted Document
    - Displays the extracted text from the PDF document, divided into pages.
    - Each page is separated by a horizontal rule.

    #### View Sections
    - Allows the user to select specific sections of the document by checkboxes.
    - Displays the content of the selected sections.
    - Provides an option to look up a word within each section.

    #### Dictionary Lookup
    - Provides a sidebar option to enter a word and fetch its definition using the WordsAPI.
    - Displays the definition of the word if found.
    - Alerts if no definition is found.

    #### Table of Contents
    - Lists all documents stored in the specified folders with their metadata.
    - Provides sorting options for titles.
    - Each row has a select button to navigate directly to the corresponding PDF document and display it.
    - **Title**: The name of the act or document.
    - **Act Number**: The numerical identifier of the act.
    - **Act Year**: The year associated with the act.
    - **Date**: The date when the act was enacted.
    - **PDF**: The filename of the PDF containing the act.
    """)

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



def update_circulars():
    '''
    # Updates: Downloads unique files which means it excludes certain files if they have repeated titles unlike 36. Final.py
    '''
    st.subheader("Updating Circulars")
    base_url = "https://www.mha.gov.in/en/notifications/circular"
    circulars_folder = "Circulars_37"
   
    if not os.path.exists(circulars_folder):
        os.makedirs(circulars_folder)
   
    total_downloads = 0
    total_existing = 0
    
    # Keep track of downloaded files
    downloaded_files = set()
    
    for i in range(6):  # This will check 6 iterations
        url = f"{base_url}?page={i}"
       
        try:
            response = requests.get(url)
            response.raise_for_status()
            soup = BeautifulSoup(response.content, 'html.parser')
           
            table = soup.find('table')
            if table:
                rows = table.find_all('tr')[1:]  # Skip the header row
           
                for row in rows:
                    cells = row.find_all('td')
                    if len(cells) >= 3:
                        title = cells[1].text.strip()
                        download_link = cells[2].find('a', href=True)
                        
                        if download_link:
                            download_url = download_link['href']
                            
                            if not download_url.startswith('http'):
                                download_url = f"https://www.mha.gov.in{download_url}"
                            
                            # Get file size from the download link text
                            file_size = download_link.text.strip().split()[-1].strip('()')
                            
                            # Create a unique identifier using title and file size
                            file_id = hashlib.md5(f"{title}_{file_size}".encode()).hexdigest()
                            
                            if file_id not in downloaded_files:
                                st.write(f"Found new circular: {title}")
                                st.write(f"Download URL: {download_url}")
                                
                                # Create a filename using the title
                                valid_filename = "".join([c for c in title if c.isalpha() or c.isdigit() or c==' ']).rstrip()
                                file_name = os.path.join(circulars_folder, f"{valid_filename[:100]}_{file_size}.pdf")
                                
                                if not os.path.exists(file_name):
                                    st.write(f"Attempting to download: {title}")
                                    try:
                                        file_response = requests.get(download_url)
                                        file_response.raise_for_status()
                                       
                                        with open(file_name, 'wb') as file:
                                            file.write(file_response.content)
                                        st.success(f"Downloaded: {title}")
                                        total_downloads += 1
                                        downloaded_files.add(file_id)
                                    except requests.RequestException as e:
                                        st.error(f"Failed to download {title}: {str(e)}")
                                else:
                                    st.info(f"File already exists: {title}")
                                    total_existing += 1
                                    downloaded_files.add(file_id)
                            else:
                                st.info(f"Duplicate circular found, skipping: {title}")
                    else:
                        st.warning(f"Row doesn't have enough cells: {cells}")
            else:
                st.warning(f"No table found")
       
        except requests.RequestException as e:
            st.error(f"An error occurred while fetching circulars: {str(e)}")
            continue
   
    st.success(f"Circular update completed! Downloaded {total_downloads} new circulars. {total_existing} circulars already existed.")

# Function to read metadata from text files in a folder
def read_metadata_from_folder(folder_path):
    metadata = []

    # Iterate through each file in the folder
    for filename in os.listdir(folder_path):
        if filename.endswith(".txt"):  # Assuming all metadata files have .txt extension
            filepath = os.path.join(folder_path, filename)
            with open(filepath, 'r', encoding='utf-8') as file:
                file_metadata = {}
                for line in file:
                    key, value = line.strip().split(': ', 1)
                    file_metadata[key] = value
                file_metadata['PDF'] = filename[:-4] + '.pdf'  # Assuming PDF names correspond to text file names
                metadata.append(file_metadata)

    return metadata

# Function to display table of contents for circular metadata
def display_circular_metadata(folder_path, sort_option):
    metadata = read_metadata_from_folder(folder_path)

    if sort_option == 'Alphabetical Order':
        sorted_metadata = sorted(metadata, key=lambda x: x.get('Issuer', '').lower())
    elif sort_option == 'Reverse Alphabetical Order':
        sorted_metadata = sorted(metadata, key=lambda x: x.get('Issuer', '').lower(), reverse=True)
    elif sort_option == 'Date':
        sorted_metadata = sorted(metadata, key=lambda x: x.get('Date', ''), reverse=True)

    st.subheader("Table of Contents - All Circulars")
    st.write("Total Circulars:", len(sorted_metadata))
    
    if sorted_metadata:
        # Create a DataFrame to hold the table of contents data
        data = []
        for meta_info in sorted_metadata:
            data.append({
                'Issuer': meta_info.get('Issuer', ''),
                'Date': meta_info.get('Date', ''),
                'Signatory': meta_info.get('Signatory', ''),
                'PDF': meta_info.get('PDF', '')
            })

        df = pd.DataFrame(data)

        st.write("### Table Columns:")
        st.write("- **Issuer**: The organization issuing the circular.")
        st.write("- **Date**: The date when the circular was issued.")
        st.write("- **Signatory**: The person who signed the circular.")
        st.write("- **PDF**: The filename of the PDF containing the circular.")

        for index, row in df.iterrows():
            col1, col2, col3, col4, col5 = st.columns([3, 2, 2, 2, 1])
            col1.write(row['Issuer'])
            col2.write(row['Date'])
            col3.write(row['Signatory'])
            col4.write(row['PDF'])
            if col5.button("✓", key=f"select_{index}"):
                st.session_state.selected_pdf = row['PDF']
                st.session_state.current_option = 'Show Original Document'
                st.experimental_rerun()

    else:
        st.write("No circulars found.")

# Main function to run the Streamlit app
def main():    
    st.title('Lex Res Data Science & Analytics Pvt. Ltd.: BASE ACTS Chatbot Application')

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
            if password == "!@#$1234" and username == "Admin":
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
            logout_message_placeholder.info('Logged out successfully.')  # Display logout confirmation message

            # Delay and clear the message after 5 seconds
            time.sleep(5)
            logout_message_placeholder.empty()

            # Rerun the script to reset the session and show login screen
            st.experimental_rerun()  # Rerun the app to show the login screen again

        # Sidebar for navigation and search
        st.sidebar.title("Navigation")
        option = st.sidebar.radio("Choose an option:", ('Show Original Document', 'Show Extracted Document', 'View Sections', 'Dictionary Lookup', 'User Manual', 'Table of Contents', 'Update Circulars'))

        # Handle the selected PDF from the Table of Contents
        if st.session_state.selected_pdf and st.session_state.current_option == 'Show Original Document':
            pdf_folder = 'All Documents'  # Update this with your PDF folder path
            pdf_path = os.path.join(pdf_folder, st.session_state.selected_pdf)
            if os.path.exists(pdf_path):
                with open(pdf_path, "rb") as pdf_file:
                    st.markdown("### Original Document")
                    display_pdf(pdf_file)
                    if st.button("Suggest BARE ACTS' Keywords"):
                        full_document_text, _ = extract_text_from_pdf(pdf_file)
                        suggest_bare_acts(full_document_text)
                # Clear the selected_pdf from session state to avoid redisplaying on refresh
                st.session_state.selected_pdf = None
            else:
                st.error(f"File {st.session_state.selected_pdf} not found in {pdf_folder}")

        # File uploader widget
        uploaded_file = st.file_uploader("Choose a PDF file", type="pdf")

        if option == 'Table of Contents':
            # List all documents in specified folders and provide sorting options
            pdf_folder = 'All Documents'  # Update this with your PDF folder path
            txt_folder = 'Cleaned Metadata'  # Update this with your TXT folder path
            titles = extract_txt_titles(pdf_folder, txt_folder)

            if titles:
                sort_option = st.sidebar.selectbox("Sort by:", ('Alphabetical Order', 'Reverse Alphabetical Order', 'Act Number', 'Date'))
                display_table_of_contents(titles, sort_option)
            else:
                st.write("No documents found.")

        elif option == 'Update Circulars':
            update_circulars()

        elif uploaded_file is not None:
            # Process the uploaded PDF file
            full_document_text, document_sections = extract_text_from_pdf(uploaded_file)
            
            if option == 'Show Original Document':
                st.markdown("### Original Document")
                display_pdf(uploaded_file)
                if st.button("Suggest BARE ACTS"):
                    suggest_bare_acts(full_document_text)
            
            elif option == 'Show Extracted Document':
                # Display full document text with line breaks between pages
                pages = full_document_text.split('\n\n')
                for i, page in enumerate(pages):
                    st.write(page)
                    if i < len(pages) - 1:
                        st.markdown('<hr>', unsafe_allow_html=True)  # Add horizontal rule between pages
            
            elif option == 'View Sections':
                # Display checkboxes for each section
                selected_sections = []
                for section in document_sections:
                    if st.sidebar.checkbox(section):
                        selected_sections.append(section)
                
                # Display content for selected sections
                for section in selected_sections:
                    st.subheader(section)
                    display_section_content(full_document_text, section)
            
            elif option == 'Dictionary Lookup':
                # Dictionary lookup functionality
                word_to_lookup = st.sidebar.text_input("Enter a word to lookup:")
                if word_to_lookup:
                    # Fetch definition from WordsAPI
                    definition = fetch_definition(word_to_lookup)
                    if definition:
                        st.sidebar.write(f"**Definition of '{word_to_lookup}':** {definition}")
                    else:
                        st.sidebar.write(f"No definition found for '{word_to_lookup}'")
            
            elif option == 'User Manual':
                # Display user manual
                display_user_manual()
        
        elif option == 'Table of Contents - Circulars':
            # Assuming 'Circulars' is a folder containing circular metadata text files
            circulars_folder = 'Circulars'
            sort_option = st.sidebar.selectbox("Sort by:", ('Alphabetical Order', 'Reverse Alphabetical Order', 'Date'))
            display_circular_metadata(circulars_folder, sort_option)

if __name__ == '__main__':
    main()