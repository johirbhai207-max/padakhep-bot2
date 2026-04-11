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
        # সরাসরি v1beta ভার্সন এবং API Key সেট করা
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

# --- ৩. নলেজ বেস এবং মডেল সিলেকশন (Error-Proof) ---
@st.cache_resource
def prepare_knowledge_base():
    files_to_use = []
    knowledge_dir = "knowledge"
    instruction = (
        "তুমি পদক্ষেপ মানবিক উন্নয়ন কেন্দ্রের বিশেষজ্ঞ সহকারী 'পদক্ষেপ মিত্র'। "
        "তোমার কাজ হলো প্রদত্ত পিডিএফ ফাইলগুলো খুব ভালো করে পড়ে বাংলা ভাষায় সঠিক উত্তর দেওয়া। "
        "ফাইলগুলো স্ক্যান করা ইমেজ থেকে নেওয়া, তাই অস্পষ্ট তথ্য থাকলে সরাসরি বলো যে তথ্যটি অস্পষ্ট।"
    )
    
    # নলেজ ফোল্ডার থেকে ফাইল আপলোড
    if os.path.exists(knowledge_dir) and os.path.isdir(knowledge_dir):
        for f in os.listdir(knowledge_dir):
            if f.lower().endswith(".pdf"):
                file_path = os.path.join(knowledge_dir, f)
                gemini_file = upload_to_gemini(file_path, mime_type="application/pdf")
                if gemini_file:
                    files_to_use.append(gemini_file)

    # মডেল আইডিগুলো ট্রাই করা (একটির পর একটি)
    # v1beta-তে 'gemini-1.5-flash-001' সবচেয়ে স্ট্যাবল
    model_names = ['gemini-1.5-flash-001', 'gemini-1.5-flash', 'gemini-1.5-pro']
    
    selected_model = None
    for m_name in model_names:
        try:
            # ক্যাশিং ট্রাই করা (যদি ফাইল থাকে)
            if files_to_use:
                cache = caching.CachedContent.create(
                    model=f'models/{m_name}',
                    display_name='padakhep_cache',
                    system_instruction=instruction,
                    contents=files_to_use,
                    ttl=datetime.timedelta(hours=24),
                )
                selected_model = genai.GenerativeModel.from_cached_content(cached_content=cache)
                return selected_model, files_to_use
            else:
                # ফাইল না থাকলে সাধারণ মডেল
                selected_model = genai.GenerativeModel(model_name=m_name, system_instruction=instruction)
                return selected_model, None
        except Exception:
            continue # এরর হলে পরের মডেল ট্রাই করবে

    # যদি ক্যাশিং কাজ না করে, তবে সরাসরি মডেল লোড করা (সবচেয়ে নিরাপদ পদ্ধতি)
    return genai.GenerativeModel(model_name='gemini-1.5-flash', system_instruction=instruction), files_to_use

# মডেল লোড করা
model, uploaded_files = prepare_knowledge_base()

# --- ৪. ইউজার ইন্টারফেস ---
st.set_page_config(page_title="পদক্ষেপ মিত্র", page_icon="🤖", layout="wide")
st.title("🤖 পদক্ষেপ মিত্র (Official Assistant)")

if "messages" not in st.session_state:
    st.session_state.messages = []

# চ্যাট সেশন চালু রাখা (স্মৃতিশক্তি ধরে রাখা)
if "chat_session" not in st.session_state and model:
    history_setup = []
    # ক্যাশ না থাকলে সেশনের শুরুতে ফাইলগুলো পাঠানো
    if uploaded_files and not hasattr(model, 'cached_content'):
        history_setup = [{"role": "user", "parts": uploaded_files}]
    st.session_state.chat_session = model.start_chat(history=history_setup)

# চ্যাট হিস্ট্রি দেখানো
for m in st.session_state.messages:
    with st.chat_message(m["role"]):
        st.markdown(m["content"])

# --- ৫. চ্যাট প্রসেসিং ---
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
                # এরর মেসেজটি সুন্দরভাবে দেখানো
                st.error(f"দুঃখিত, উত্তর তৈরি করা যায়নি। মডেলের সাথে কানেক্ট করতে সমস্যা হচ্ছে।")
                st.info("আপনার ইন্টারনেট বা API Key চেক করে আবার চেষ্টা করুন।")
