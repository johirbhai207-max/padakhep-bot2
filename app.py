import streamlit as st
import google.generativeai as genai
from google.generativeai import caching
import os
import time
import datetime

# --- ১. এপিআই কি সেটিংস ---
try:
    if "GEMINI_API_KEY" in st.secrets:
        API_KEY = st.secrets["GEMINI_API_KEY"]
        genai.configure(api_key=API_KEY)
    else:
        st.error("Secrets-এ 'GEMINI_API_KEY' পাওয়া যায়নি।")
        st.stop()
except Exception as e:
    st.error(f"Configuration Error: {e}")
    st.stop()

# --- ২. ফাইল আপলোড ফাংশন ---
def upload_to_gemini(path, mime_type=None):
    try:
        file = genai.upload_file(path, mime_type=mime_type)
        while file.state.name == "PROCESSING":
            time.sleep(2)
            file = genai.get_file(file.name)
        return file
    except Exception as e:
        st.error(f"ফাইল আপলোড এরর: {e}")
        return None

# --- ৩. নলেজ বেস এবং ক্যাশিং (Error Fixed Version) ---
@st.cache_resource
def prepare_knowledge_base():
    files_to_use = []
    knowledge_dir = "knowledge"
    instruction = (
        "তুমি পদক্ষেপ মানবিক উন্নয়ন কেন্দ্রের বিশেষজ্ঞ সহকারী 'পদক্ষেপ মিত্র'। "
        "তোমার কাজ হলো প্রদত্ত পিডিএফ ফাইলগুলো খুব ভালো করে পড়ে বাংলা ভাষায় সঠিক উত্তর দেওয়া। "
        "ফাইলগুলো স্ক্যান করা ইমেজ থেকে নেওয়া, তাই কোনো তথ্য অস্পষ্ট থাকলে সরাসরি বলো যে তথ্যটি অস্পষ্ট।"
    )
    
    if os.path.exists(knowledge_dir) and os.path.isdir(knowledge_dir):
        for f in os.listdir(knowledge_dir):
            if f.lower().endswith(".pdf"):
                file_path = os.path.join(knowledge_dir, f)
                gemini_file = upload_to_gemini(file_path, mime_type="application/pdf")
                if gemini_file:
                    files_to_use.append(gemini_file)
    
    # ক্যাশিং ট্রাই করা (নির্দিষ্ট ভার্সন 001 ব্যবহার করে)
    try:
        if files_to_use:
            cache = caching.CachedContent.create(
                model='models/gemini-1.5-flash-001',
                display_name='padakhep_v3',
                system_instruction=instruction,
                contents=files_to_use,
                ttl=datetime.timedelta(hours=24),
            )
            model = genai.GenerativeModel.from_cached_content(cached_content=cache)
            return model, files_to_use
    except Exception:
        pass # ক্যাশ না হলে নিচে স্ট্যান্ডার্ড মোডে যাবে

    # স্ট্যান্ডার্ড মোড ব্যাকআপ (সঠিক মডেল নেম সহ)
    backup_model = genai.GenerativeModel(
        model_name='models/gemini-1.5-flash-latest', 
        system_instruction=instruction
    )
    return backup_model, files_to_use

# মডেল লোড করা
model, uploaded_files = prepare_knowledge_base()

# --- ৪. ইউজার ইন্টারফেস (UI) ---
st.set_page_config(page_title="পদক্ষেপ মিত্র", page_icon="🤖", layout="wide")
st.title("🤖 পদক্ষেপ মিত্র (Advanced Assistant)")

if "messages" not in st.session_state:
    st.session_state.messages = []

# চ্যাট সেশন চালু রাখা (স্মৃতি ধরে রাখা)
if "chat_session" not in st.session_state and model:
    history_setup = []
    # যদি ক্যাশ সচল না থাকে তবে সেশনের শুরুতে ফাইলগুলো পাঠানো হবে
    if uploaded_files and not hasattr(model, 'cached_content'):
        history_setup = [{"role": "user", "parts": uploaded_files}]
    st.session_state.chat_session = model.start_chat(history=history_setup)

# চ্যাট হিস্ট্রি দেখানো
for m in st.session_state.messages:
    with st.chat_message(m["role"]):
        st.markdown(m["content"])

# --- ৫. চ্যাট প্রসেসিং (Streaming) ---
if prompt := st.chat_input("গাইডলাইন সম্পর্কে প্রশ্ন করুন..."):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        if st.session_state.chat_session:
            try:
                response = st.session_state.chat_session.send_message(prompt, stream=True)
                full_response = ""
                message_placeholder = st.empty()
                for chunk in response:
                    full_response += chunk.text
                    message_placeholder.markdown(full_response + "▌")
                message_placeholder.markdown(full_response)
                st.session_state.messages.append({"role": "assistant", "content": full_response})
            except Exception as e:
                st.error(f"দুঃখিত, উত্তর তৈরি করা যায়নি। এরর: {e}")
