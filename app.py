import streamlit as st
import google.generativeai as genai
import os
import PyPDF2
import re

# --- ১. এপিআই সেটিংস ---
if "GEMINI_API_KEY" in st.secrets:
    # এখানে সরাসরি v1beta ভার্সন কনফিগার করার চেষ্টা করা হচ্ছে
    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
else:
    st.error("Secrets-এ 'GEMINI_API_KEY' পাওয়া যায়নি।")
    st.stop()

# --- ২. পিডিএফ ডেটা প্রসেসিং ---
@st.cache_data(show_spinner=False)
def get_guideline_paragraphs():
    paragraphs = []
    knowledge_dir = "knowledge"
    if os.path.exists(knowledge_dir):
        for file in os.listdir(knowledge_dir):
            if file.lower().endswith(".pdf"):
                try:
                    path = os.path.join(knowledge_dir, file)
                    with open(path, "rb") as f:
                        pdf_reader = PyPDF2.PdfReader(f)
                        full_text = ""
                        for page in pdf_reader.pages:
                            text = page.extract_text()
                            if text:
                                full_text += text + "\n"
                        # প্যারাগ্রাফে ভাগ করা
                        raw_parts = full_text.split('\n\n')
                        for p in raw_parts:
                            clean_p = p.strip()
                            if len(clean_p) > 25:
                                paragraphs.append(clean_p)
                except Exception:
                    continue
    return paragraphs

# --- ৩. ইন্টারফেস ডিজাইন ---
st.set_page_config(page_title="পদক্ষেপ মিত্র", page_icon="🤖")

with st.sidebar:
    st.title("কট্রোল প্যানেল")
    if st.button("মেমোরি পরিষ্কার করুন"):
        st.session_state.messages = []
        st.rerun()

st.title("🤖 পদক্ষেপ মিত্র (Official Assistant)")
st.caption("পদক্ষেপ মানবিক উন্নয়ন কেন্দ্রের নীতিমালা বিষয়ক এআই সহকারী")

with st.spinner("গাইডলাইন ডাটাবেস চেক করা হচ্ছে..."):
    all_paragraphs = get_guideline_paragraphs()

if "messages" not in st.session_state:
    st.session_state.messages = []

# --- ৪. মাল্টি-লেভেল ফলব্যাক চ্যাট ফাংশন ---
def generate_ai_response(prompt_text):
    # এই মডেলের নামগুলো v1beta এবং v1 উভয় ভার্সনেই সবচেয়ে বেশি কাজ করে
    test_models = ['gemini-1.5-flash', 'gemini-1.5-pro', 'gemini-pro']
    
    for model_name in test_models:
        try:
            model = genai.GenerativeModel(model_name)
            response = model.generate_content(
                prompt_text,
                safety_settings={
                    'HATE': 'BLOCK_NONE', 'HARASSMENT': 'BLOCK_NONE',
                    'SEXUAL' : 'BLOCK_NONE', 'DANGEROUS' : 'BLOCK_NONE'
                }
            )
            return response.text
        except Exception as e:
            # যদি 404 আসে, তবে পরের মডেলে যাবে
            if "404" in str(e):
                continue
            else:
                return f"এপিআই ত্রুটি: {str(e)}"
    
    return "দুঃখিত, কোনো সক্রিয় মডেল খুঁজে পাওয়া যায়নি। আপনার এপিআই কী-এর পারমিশন চেক করুন।"

# আগের মেসেজ দেখানো
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# --- ৫. চ্যাট ইনপুট ও প্রসেসিং ---
if prompt := st.chat_input("গাইডলাইন
