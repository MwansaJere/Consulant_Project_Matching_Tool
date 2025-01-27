import os
import re
import pdfplumber
from docx import Document
import pandas as pd
import streamlit as st
import plotly.express as px
from st_aggrid import AgGrid
from st_aggrid.grid_options_builder import GridOptionsBuilder

# Paths for input CVs and metadata
CV_DIR = "/Users/Mwansa/Desktop/Projects/Consultant Matching/cv"
OUTPUT_CSV = os.path.join(CV_DIR, "consultant_metadata.csv")

# Function to extract text from PDF
def extract_text_from_pdf(file_path):
    text = ""
    with pdfplumber.open(file_path) as pdf:
        for page in pdf.pages:
            text += page.extract_text() + "\n"
    return text

# Function to extract text from DOCX
def extract_text_from_docx(file_path):
    doc = Document(file_path)
    return "\n".join([p.text for p in doc.paragraphs])

# Unified text extraction
def extract_text(file_path):
    if file_path.endswith(".pdf"):
        return extract_text_from_pdf(file_path)
    elif file_path.endswith(".docx"):
        return extract_text_from_docx(file_path)
    else:
        raise ValueError(f"Unsupported file format: {file_path}")

# Function to calculate years of experience
def calculate_years_of_experience(experience_section):
    years = 0
    date_pattern = r"(\d{4})-(\d{4})|(\d{4})-Present|(\d{4})"
    matches = re.findall(date_pattern, experience_section)
    for match in matches:
        if match[1]:
            start_year = int(match[0])
            end_year = int(match[1])
        elif match[2]:
            start_year = int(match[2])
            end_year = datetime.now().year
        elif match[3]:
            start_year = end_year = int(match[3])
        else:
            continue
        years += end_year - start_year
    return years

# Improved function to parse metadata
def parse_metadata(raw_text, file_name):
    name_pattern = re.search(r"(Name[:\-]?\s*(.+))", raw_text, re.IGNORECASE)
    email_pattern = re.search(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}", raw_text)
    phone_pattern = re.search(r"(\+?\d[\d\s\-()]{7,})", raw_text)
    education_matches = re.findall(r"(?i)(.*?degree.*?)\s*(\d{4})", raw_text)
    experience_matches = re.findall(r"(?i)(.*?\s\d{4} - \d{4}|.*?\s\d{4} - Present)", raw_text)

    # Metadata structure
    metadata = {
        "Name": name_pattern.group(2).strip() if name_pattern and name_pattern.group(2) else file_name.split('.')[0],
        "Email": email_pattern.group(0).strip() if email_pattern else "Not Provided",
        "Phone": phone_pattern.group(0).strip() if phone_pattern else "Not Provided",
        "Education": "; ".join([f"{edu[0]} ({edu[1]})" for edu in education_matches]),
        "Skills": "; ".join(re.findall(r"(?i)skills[:\-]?\s*(.+)", raw_text)),
        "Experience": "; ".join(experience_matches),
        "Years of Experience": calculate_years_of_experience(raw_text),
    }
    return metadata

# Function to process all CVs and save metadata
def process_cvs(directory):
    data = []
    for file_name in os.listdir(directory):
        file_path = os.path.join(directory, file_name)
        if not file_name.startswith('.') and os.path.isfile(file_path):
            try:
                raw_text = extract_text(file_path)
                metadata = parse_metadata(raw_text, file_name)
                metadata["File"] = file_name
                data.append(metadata)
            except Exception as e:
                print(f"Error processing {file_name}: {e}")
    if not data:
        print("No metadata extracted. Check the CVs and extraction logic.")
        return pd.DataFrame()
    df = pd.DataFrame(data)
    df.to_csv(OUTPUT_CSV, index=False)
    return df

# Streamlit App
def display_streamlit_dashboard():
    st.set_page_config(page_title="Consultant Matching System", layout="wide")
    st.image("/Users/Mwansa/Downloads/consultant_profiles/dpclogo.png", width=200)
    st.title("Consultant Matching System")
    st.markdown("### Find the best consultants for your project with AI-driven insights.")

    # Sidebar Inputs
    st.sidebar.header("Project Requirements")
    required_skills = st.sidebar.text_input("Required Skills (comma-separated):").split(",")
    num_results = st.sidebar.selectbox("Number of Results to Display:", [3, 5, 10], index=0)
    min_experience = st.sidebar.number_input("Minimum Experience (years):", min_value=0, step=1)

    weight_skills = st.sidebar.slider("Weight for Skills Match:", 0.0, 1.0, 0.7)
    weight_experience = st.sidebar.slider("Weight for Years of Experience:", 0.0, 1.0, 0.3)

    # Load Metadata
    st.header("Consultant Profiles")
    try:
        if not os.path.exists(OUTPUT_CSV):
            print("Generating metadata from CVs...")
            consultant_df = process_cvs(CV_DIR)
        else:
            consultant_df = pd.read_csv(OUTPUT_CSV)
        
        if st.sidebar.button("Find Consultants"):
            if consultant_df.empty:
                st.warning("No consultant data available.")
            else:
                consultant_df["Rank"] = (
                    consultant_df["Years of Experience"].astype(float) * weight_experience +
                    consultant_df["Skills"].apply(lambda x: len(set(x.split("; ")).intersection(set(required_skills)))) * weight_skills
                )
                consultant_df = consultant_df.sort_values(by="Rank", ascending=False).head(num_results)

                st.subheader(f"Top {num_results} Consultants for Your Project")
                st.dataframe(consultant_df[["Name", "Email", "Phone", "Rank"]])

                st.subheader("Bar Chart: Top Consultants Comparison")
                fig = px.bar(
                    consultant_df, 
                    x="Name", 
                    y=["Rank", "Years of Experience"],
                    barmode="group", 
                    title="Comparison of Top Consultants"
                )
                st.plotly_chart(fig)

                st.subheader("Interactive Consultant Details")
                grid_builder = GridOptionsBuilder.from_dataframe(consultant_df)
                grid_builder.configure_pagination()
                grid_options = grid_builder.build()
                AgGrid(consultant_df, gridOptions=grid_options, height=300)
    except Exception as e:
        st.error(f"An error occurred: {e}")

# Run the app
if __name__ == "__main__":
    display_streamlit_dashboard()
