import streamlit as st
import google.generativeai as genai
import os
import time

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
def upload_to_gemini(path):
    try:
        # সরাসরি ফাইল আপলোড (বিনা কোনো এক্সট্রা প্যারামিটারে)
        file = genai.upload_file(path)
        while file.state.name == "PROCESSING":
            time.sleep(2)
            file = genai.get_file(file.name)
        return file
    except Exception as e:
        return None

# --- ৩. নলেজ বেস তৈরি (Stable Mode) ---
@st.cache_resource
def prepare_knowledge_base():
    files_to_use = []
    knowledge_dir = "knowledge"
    
    if os.path.exists(knowledge_dir) and os.path.isdir(knowledge_dir):
        for f in os.listdir(knowledge_dir):
            if f.lower().endswith(".pdf"):
                file_path = os.path.join(knowledge_dir, f)
                gemini_file = upload_to_gemini(file_path)
                if gemini_file:
                    files_to_use.append(gemini_file)
    return files_to_use

# ফাইলগুলো লোড করা
uploaded_files = prepare_knowledge_base()

# মডেল সেটআপ (সরাসরি স্ট্যাবল মডেল আইডি)
instruction = (
    "তুমি পদক্ষেপ মানবিক উন্নয়ন কেন্দ্রের বিশেষজ্ঞ সহকারী 'পদক্ষেপ মিত্র'। "
    "তোমার কাজ হলো প্রদত্ত পিডিএফ ফাইলগুলো খুব ভালো করে পড়ে বাংলা ভাষায় সঠিক উত্তর দেওয়া। "
    "ফাইলগুলো স্ক্যান করা ইমেজ থেকে নেওয়া, তাই অস্পষ্ট তথ্য থাকলে সরাসরি বলো যে তথ্যটি অস্পষ্ট।"
)
model = genai.GenerativeModel(model_name='gemini-1.5-flash', system_instruction=instruction)

# --- ৪. ইউজার ইন্টারফেস (UI) ---
st.set_page_config(page_title="পদক্ষেপ মিত্র", page_icon="🤖", layout="wide")
st.title("🤖 পদক্ষেপ মিত্র (Official Assistant)")

if "messages" not in st.session_state:
    st.session_state.messages = []

# চ্যাট সেশন চালু রাখা
if "chat_session" not in st.session_state:
    history_setup = []
    if uploaded_files:
        # শুরুতে ফাইলগুলো কনটেক্সট হিসেবে পাঠিয়ে দেওয়া
        history_setup = [{"role": "user", "parts": uploaded_files}]
    st.session_state.chat_session = model.start_chat(history=history_setup)

# আগের চ্যাটগুলো দেখানো
for m in st.session_state.messages:
    with st.chat_message(m["role"]):
        st.markdown(m["content"])

# --- ৫. চ্যাট প্রসেসিং ---
if prompt := st.chat_input("গাইডলাইন সম্পর্কে প্রশ্ন করুন..."):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        try:
            # সরাসরি রেসপন্স (স্ট্রিমিং ছাড়া ট্রাই করা যাতে কানেকশন ড্রপ না করে)
            response = st.session_state.chat_session.send_message(prompt)
            
            if response.text:
                st.markdown(response.text)
                st.session_state.messages.append({"role": "assistant", "content": response.text})
            
        except Exception as e:
            st.error("দুঃখিত, উত্তর তৈরি করা যায়নি। মডেলের সাথে কানেক্ট করতে সমস্যা হচ্ছে।")
            st.info("দয়া করে অ্যাপটি একবার Reboot করুন।")
