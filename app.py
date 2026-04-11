import streamlit as st
import google.generativeai as genai
import os
import PyPDF2

# --- এপিআই সেটিংস ---
if "GEMINI_API_KEY" in st.secrets:
    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
else:
    st.error("Secrets-এ এপিআই কী পাওয়া যায়নি।")
    st.stop()

# --- পিডিএফ প্রসেসিং ---
@st.cache_data(show_spinner=False)
def get_pdf_text():
    text = ""
    if os.path.exists("knowledge"):
        for file in os.listdir("knowledge"):
            if file.endswith(".pdf"):
                try:
                    with open(f"knowledge/{file}", "rb") as f:
                        pdf = PyPDF2.PdfReader(f)
                        for page in pdf.pages:
                            text += page.extract_text() + "\n"
                except: continue
    return text

# --- ইন্টারফেস ---
st.set_page_config(page_title="পদক্ষেপ মিত্র", page_icon="🤖")
st.title("🤖 পদক্ষেপ মিত্র")

knowledge_base = get_pdf_text()

if "messages" not in st.session_state:
    st.session_state.messages = []

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# --- চ্যাট লজিক ---
if prompt := st.chat_input("প্রশ্ন করুন..."):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        try:
            # সবচেয়ে নিরাপদ মডেল নাম ব্যবহার করা হয়েছে
            model = genai.GenerativeModel('gemini-1.5-flash')
            response = model.generate_content(
                f"তথ্যসমূহ: {knowledge_base[:5000]}\n\nপ্রশ্ন: {prompt}"
            )
            st.markdown(response.text)
            st.session_state.messages.append({"role": "assistant", "content": response.text})
        except Exception as e:
            st.error(f"যান্ত্রিক সমস্যা: {str(e)}")
