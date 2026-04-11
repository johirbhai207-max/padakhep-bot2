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

# --- ৩. নলেজ বেস এবং ক্যাশিং (বটের জ্ঞানভাণ্ডার তৈরি) ---
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
    
    if not files_to_use:
        return None, None

    try:
        # সিস্টেম ইন্সট্রাকশন: যা বটের পারসোনালিটি ঠিক করবে
        instruction = (
            "তুমি পদক্ষেপ মানবিক উন্নয়ন কেন্দ্রের বিশেষজ্ঞ সহকারী 'পদক্ষেপ মিত্র'। "
            "তোমার কাজ হলো প্রদত্ত পিডিএফ ফাইলগুলো খুব ভালো করে পড়ে বাংলা ভাষায় সঠিক উত্তর দেওয়া। "
            "যদি কোনো তথ্য অস্পষ্ট থাকে তবে ভুল উত্তর না দিয়ে সরাসরি বলো যে তথ্যটি অস্পষ্ট।"
        )
        
        # Context Caching: ফাইলগুলোকে বটের স্মৃতিতে ২৪ ঘণ্টার জন্য জমা রাখা
        cache = caching.CachedContent.create(
            model='models/gemini-1.5-flash-001',
            display_name='padakhep_mitro_v2',
            system_instruction=instruction,
            contents=files_to_use,
            ttl=datetime.timedelta(hours=24), # ২৪ ঘণ্টা মেমোরিতে থাকবে
        )
        
        # ক্যাশ ব্যবহার করে প্রফেশনাল মডেল তৈরি
        model = genai.GenerativeModel.from_cached_content(cached_content=cache)
        return model, files_to_use
    except Exception as e:
        # ক্যাশিং এ কোনো এরর হলে সাধারণ মডেলে ব্যাকআপ করবে
        st.warning(f"Caching not available, using standard mode. Error: {e}")
        return genai.GenerativeModel(model_name='gemini-1.5-flash', system_instruction=instruction), files_to_use

# মডেল লোড করা
model, uploaded_files = prepare_knowledge_base()

# --- ৪. ইউজার ইন্টারফেস (UI) ---
st.set_page_config(page_title="পদক্ষেপ মিত্র", page_icon="🤖", layout="wide")
st.title("🤖 পদক্ষেপ মিত্র (Advanced AI)")
st.caption("পদক্ষেপ মানবিক উন্নয়ন কেন্দ্রের ডিজিটাল তথ্যভাণ্ডার।")

# চ্যাট হিস্ট্রি সেশন স্টেট
if "messages" not in st.session_state:
    st.session_state.messages = []

# চ্যাট সেশন হ্যান্ডেলার (এটিই আগের কথা মনে রাখে)
if "chat_session" not in st.session_state and model:
    # শুরুতে ফাইলগুলো দিয়ে সেশন শুরু করা
    st.session_state.chat_session = model.start_chat(history=[])

# আগের মেসেজগুলো স্ক্রিনে দেখানো
for m in st.session_state.messages:
    with st.chat_message(m["role"]):
        st.markdown(m["content"])

# --- ৫. চ্যাট প্রসেসিং (Streaming + Context Recall) ---
if prompt := st.chat_input("গাইডলাইন সম্পর্কে প্রশ্ন করুন..."):
    # ইউজারের প্রশ্ন দেখানো
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    # বটের রেসপন্স তৈরি
    with st.chat_message("assistant"):
        if st.session_state.chat_session:
            try:
                # স্ট্রিমিং এফেক্ট (উত্তর টাইপ হতে দেখা যাবে)
                response = st.session_state.chat_session.send_message(prompt, stream=True)
                
                full_response = ""
                message_placeholder = st.empty()
                
                for chunk in response:
                    full_response += chunk.text
                    message_placeholder.markdown(full_response + "▌")
                
                message_placeholder.markdown(full_response)
                
                # হিস্ট্রিতে সেভ করা
                st.session_state.messages.append({"role": "assistant", "content": full_response})
                
            except Exception as e:
                st.error("দুঃখিত, উত্তর তৈরি করা যায়নি।")
                st.code(str(e))
        else:
            st.error("মডেল বা সেশন লোড হয়নি।")
