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

# --- ৩. নলেজ বেস তৈরি (Stable Mode) ---
@st.cache_resource
def prepare_knowledge_base():
    files_to_use = []
    knowledge_dir = "knowledge"
    
    if os.path.exists(knowledge_dir) and os.path.isdir(knowledge_dir):
        for f in os.listdir(knowledge_dir):
            if f.lower().endswith(".pdf"):
                file_path = os.path.join(knowledge_dir, f)
                gemini_file = upload_to_gemini(file_path, mime_type="application/pdf")
                if gemini_file:
                    files_to_use.append(gemini_file)
    return files_to_use

# ফাইলগুলো লোড করা
uploaded_files = prepare_knowledge_base()

# মডেল ডিক্লেয়ার করা (সরাসরি স্ট্যাবল মডেল ব্যবহার)
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

# চ্যাট সেশন হ্যান্ডেলার (স্মৃতি ধরে রাখা)
if "chat_session" not in st.session_state:
    # সেশনের শুরুতে সব ফাইল কনটেক্সট হিসেবে দেওয়া
    history_setup = []
    if uploaded_files:
        history_setup = [{"role": "user", "parts": uploaded_files}]
    st.session_state.chat_session = model.start_chat(history=history_setup)

# চ্যাট হিস্ট্রি দেখানো
for m in st.session_state.messages:
    with st.chat_message(m["role"]):
        st.markdown(m["content"])

# --- ৫. চ্যাট প্রসেসিং (Error-Proof) ---
if prompt := st.chat_input("গাইডলাইন সম্পর্কে প্রশ্ন করুন..."):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        try:
            # স্ট্রিমিং রেসপন্স
            response = st.session_state.chat_session.send_message(prompt, stream=True)
            
            full_response = ""
            message_placeholder = st.empty()
            
            for chunk in response:
                if chunk.text:
                    full_response += chunk.text
                    message_placeholder.markdown(full_response + "▌")
            
            message_placeholder.markdown(full_response)
            st.session_state.messages.append({"role": "assistant", "content": full_response})
            
        except Exception as e:
            st.error("দুঃখিত, উত্তর তৈরি করা যায়নি।")
            st.info("অ্যাপটি একবার রিফ্রেশ করুন বা ইন্টারনেট কানেকশন চেক করুন।")
            # টেকনিক্যাল এরর চেক করার জন্য কোডটি হাইড রাখা হলো
            # st.code(str(e))
