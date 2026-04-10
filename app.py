import streamlit as st
import google.generativeai as genai
import os
import time

# ১. এপিআই কি সেটিংস
try:
    if "GEMINI_API_KEY" in st.secrets:
        API_KEY = st.secrets["GEMINI_API_KEY"]
        genai.configure(api_key=API_KEY)
    else:
        st.error("Secrets-এ 'GEMINI_API_KEY' পাওয়া যায়নি।")
        st.stop()
except Exception as e:
    st.error(f"Configuration Error: {e}")
    st.stop()

# ২. ফাইল আপলোড এবং প্রসেসিং (Error Fix)
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

# ৩. স্মার্ট মডেল সিলেকশন (এটি 404 Error সমাধান করবে)
@st.cache_resource
def get_working_model():
    try:
        # আপনার কি দিয়ে কোন মডেলগুলো এভেইলএবল তা দেখা
        available_models = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
        
        # অগ্রাধিকার ভিত্তিতে সঠিক মডেল নাম নির্বাচন
        # অনেক সময় 'models/' প্রিফিক্স ছাড়া কাজ করে না
        target_names = [
            'models/gemini-1.5-flash-latest',
            'models/gemini-1.5-flash',
            'gemini-1.5-flash',
            'models/gemini-pro'
        ]
        
        selected_model = None
        for name in target_names:
            if name in available_models:
                selected_model = name
                break
        
        if not selected_model:
            selected_model = available_models[0]
            
        return genai.GenerativeModel(
            model_name=selected_model,
            system_instruction="তুমি পদক্ষেপ মানবিক উন্নয়ন কেন্দ্রের বিশেষজ্ঞ। তোমার কাছে দেওয়া পিডিএফ ফাইলগুলো খুব ভালো করে পড়ে বাংলা ভাষায় সঠিক উত্তর দাও। হাবিজাবি উত্তর দেবে না।"
        )
    except Exception as e:
        st.error(f"মডেল লোড করতে সমস্যা: {e}")
        return None

# ডাটা এবং মডেল রেডি করা
uploaded_files = prepare_knowledge_base()
model = get_working_model()

# ৪. ইউজার ইন্টারফেস
st.set_page_config(page_title="পদক্ষেপ মিত্র", page_icon="🤖")
st.title("🤖 পদক্ষেপ মিত্র (Official Assistant)")

if "messages" not in st.session_state:
    st.session_state.messages = []

for m in st.session_state.messages:
    with st.chat_message(m["role"]):
        st.markdown(m["content"])

# ৫. চ্যাট প্রসেসিং
if prompt := st.chat_input("গাইডলাইন সম্পর্কে প্রশ্ন করুন..."):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        if model and uploaded_files:
            try:
                # ফাইল এবং টেক্সট একসাথে পাঠানো
                input_data = []
                input_data.extend(uploaded_files)
                input_data.append(prompt)
                
                response = model.generate_content(input_data)
                
                if response.text:
                    st.markdown(response.text)
                    st.session_state.messages.append({"role": "assistant", "content": response.text})
            except Exception as e:
                st.error("দুঃখিত, উত্তর তৈরি করা যায়নি।")
                st.code(str(e))
        else:
            st.warning("ফাইল বা মডেল লোড করা সম্ভব হয়নি। আপনার 'knowledge' ফোল্ডার এবং API Key চেক করুন।")
