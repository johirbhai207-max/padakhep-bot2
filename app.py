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

# --- ৩. নলেজ বেস এবং ক্যাশিং (স্মার্ট ফিক্স) ---
@st.cache_resource
def prepare_knowledge_base():
    files_to_use = []
    knowledge_dir = "knowledge"
    instruction = (
        "তুমি পদক্ষেপ মানবিক উন্নয়ন কেন্দ্রের বিশেষজ্ঞ সহকারী 'পদক্ষেপ মিত্র'। "
        "তোমার কাজ হলো প্রদত্ত পিডিএফ ফাইলগুলো খুব ভালো করে পড়ে বাংলা ভাষায় সঠিক উত্তর দেওয়া। "
        "ফাইলগুলো স্ক্যান করা ইমেজ থেকে নেওয়া, তাই অস্পষ্ট তথ্য থাকলে সরাসরি বলো যে তথ্যটি অস্পষ্ট।"
    )
    
    if os.path.exists(knowledge_dir) and os.path.isdir(knowledge_dir):
        for f in os.listdir(knowledge_dir):
            if f.lower().endswith(".pdf"):
                file_path = os.path.join(knowledge_dir, f)
                gemini_file = upload_to_gemini(file_path, mime_type="application/pdf")
                if gemini_file:
                    files_to_use.append(gemini_file)
    
    if not files_to_use:
        return genai.GenerativeModel(model_name='models/gemini-1.5-flash', system_instruction=instruction), None

    try:
        # সমাধান: সুনির্দিষ্ট মডেল নেম 'models/gemini-1.5-flash-001' ব্যবহার করা হয়েছে
        # এটি v1beta তে createCachedContent সাপোর্ট করে
        cache = caching.CachedContent.create(
            model='models/gemini-1.5-flash-001',
            display_name='padakhep_mitro_v2',
            system_instruction=instruction,
            contents=files_to_use,
            ttl=datetime.timedelta(hours=24),
        )
        model = genai.GenerativeModel.from_cached_content(cached_content=cache)
        return model, files_to_use
    except Exception as e:
        # ক্যাশিং ফেইল করলে অটোমেটিক স্ট্যান্ডার্ড মোডে ব্যাকআপ করবে
        backup_model = genai.GenerativeModel(
            model_name='models/gemini-1.5-flash', 
            system_instruction=instruction
        )
        return backup_model, files_to_use

# মডেল লোড করা
model, uploaded_files = prepare_knowledge_base()

# --- ৪. ইউজার ইন্টারফেস (UI) ---
st.set_page_config(page_title="পদক্ষেপ মিত্র", page_icon="🤖", layout="wide")

st.markdown("""
    <style>
    .stChatMessage { border-radius: 12px; border: 1px solid #444; margin-bottom: 8px; }
    </style>
""", unsafe_allow_html=True)

st.title("🤖 পদক্ষেপ মিত্র (Advanced Assistant)")
st.caption("আপনার ডিজিটাল গাইডলাইন বিশেষজ্ঞ।")

# চ্যাট হিস্ট্রি সেশন
if "messages" not in st.session_state:
    st.session_state.messages = []

# চ্যাট সেশন হ্যান্ডেলার (স্মৃতি ধরে রাখা)
if "chat_session" not in st.session_state and model:
    # যদি ক্যাশ সচল না থাকে তবে সেশনের শুরুতে ফাইলগুলো পাঠানো হবে
    history_setup = []
    if uploaded_files and not hasattr(model, 'cached_content'):
        history_setup = [{"role": "user", "parts": uploaded_files}]
    
    st.session_state.chat_session = model.start_chat(history=history_setup)

# চ্যাট হিস্ট্রি দেখানো
for m in st.session_state.messages:
    with st.chat_message(m["role"]):
        st.markdown(m["content"])

# --- ৫. চ্যাট প্রসেসিং (Streaming + Memory) ---
if prompt := st.chat_input("গাইডলাইন সম্পর্কে প্রশ্ন করুন..."):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        if st.session_state.chat_session:
            try:
                # স্ট্রিমিং রেসপন্স
                response = st.session_state.chat_session.send_message(prompt, stream=True)
                
                full_response = ""
                message_placeholder = st.empty()
                
                for chunk in response:
                    full_response += chunk.text
                    message_placeholder.markdown(full_response + "▌")
                
                message_placeholder.markdown(full_response)
                st.session_state.messages.append({"role": "assistant", "content": full_response})
                
            except Exception as e:
                st.error("দুঃখিত, উত্তর তৈরি করা যায়নি।")
                st.code(str(e))
        else:
            st.error("সিস্টেম লোড হতে সমস্যা হয়েছে। অনুগ্রহ করে পেজটি রিফ্রেশ করুন।")
