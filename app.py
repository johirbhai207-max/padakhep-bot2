import streamlit as st
import google.generativeai as genai
import os
import time

# ১. পেজ সেটিংস ও UI লুক
st.set_page_config(page_title="পদক্ষেপ মিত্র", page_icon="🤖", layout="wide")

st.markdown("""
    <style>
    .main-title { font-size: 2.8rem; font-weight: 700; text-align: center; color: white; margin-bottom: 0px; }
    .instruction { text-align: center; color: #B0B0B0; font-size: 1.1rem; margin-bottom: 30px; }
    section[data-testid="stSidebar"] { background-color: #1E1E1E; }
    </style>
    <div class="main-title">🤖 পদক্ষেপ মিত্র (Official Assistant)</div>
    <div class="instruction">তথ্য খোঁজার আগে বাম পাশের সেকশন থেকে টপিক সিলেক্ট করে নিন</div>
    """, unsafe_allow_html=True)

# ২. এপিআই কী রোটেশন লজিক
API_KEYS = [
    st.secrets.get("GEMINI_API_KEY_1"),
    st.secrets.get("GEMINI_API_KEY_2"),
    st.secrets.get("GEMINI_API_KEY_3"),
    st.secrets.get("GEMINI_API_KEY_4"),
    st.secrets.get("GEMINI_API_KEY_5")
]
VALID_KEYS = [k for k in API_KEYS if k]

if "key_index" not in st.session_state:
    st.session_state.key_index = 0

def configure_key():
    if VALID_KEYS:
        key = VALID_KEYS[st.session_state.key_index % len(VALID_KEYS)]
        genai.configure(api_key=key)
        return key
    return None

# ৩. ফাইল আপলোড লজিক
def upload_to_gemini(path):
    try:
        configure_key()
        file = genai.upload_file(path)
        while file.state.name == "PROCESSING":
            time.sleep(1)
            file = genai.get_file(file.name)
        return file
    except Exception as e:
        return f"ERROR: {str(e)}"

# ৪. সাইডবার - টপিক সিলেকশন
st.sidebar.title("📚 টপিক সিলেকশন")
knowledge_dir = "knowledge"
subfolders = [f for f in os.listdir(knowledge_dir) if os.path.isdir(os.path.join(knowledge_dir, f))] if os.path.exists(knowledge_dir) else []
selected_folders = st.sidebar.multiselect("টপিক নির্বাচন করুন:", options=subfolders)

if "messages" not in st.session_state:
    st.session_state.messages = []

for m in st.session_state.messages:
    with st.chat_message(m["role"]):
        st.markdown(m["content"])

# ৫. মূল চ্যাট লজিক (৪-৪ এরর ফিক্স করা হয়েছে)
if prompt := st.chat_input("গাইডলাইন সম্পর্কে প্রশ্ন করুন..."):
    if not selected_folders:
        st.warning("আগে টপিক সিলেক্ট করুন।")
    else:
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        with st.chat_message("assistant"):
            with st.spinner("বিশ্লেষণ চলছে..."):
                success = False
                attempts = 0
                diag_logs = []

                while not success and attempts < len(VALID_KEYS):
                    try:
                        configure_key()
                        
                        # ফাইল আপলোড
                        current_files = []
                        for folder in selected_folders:
                            path = os.path.join(knowledge_dir, folder)
                            for f in os.listdir(path):
                                if f.lower().endswith(".pdf"):
                                    res = upload_to_gemini(os.path.join(path, f))
                                    if isinstance(res, str) and "ERROR" in res:
                                        raise Exception(res)
                                    current_files.append(res)

                        # --- ৪-৪ এরর ফিক্সিং পার্ট ---
                        # আমরা সরাসরি হার্ডকোডেড নাম না দিয়ে এভেলেবল মডেল চেক করছি
                        model_to_use = "gemini-1.5-flash"
                        try:
                            for m in genai.list_models():
                                if 'generateContent' in m.supported_generation_methods:
                                    if 'gemini-1.5-flash' in m.name:
                                        model_to_use = m.name # যেমন: 'models/gemini-1.5-flash'
                                        break
                        except:
                            model_to_use = "models/gemini-1.5-flash" # ফলব্যাক
                        
                        model = genai.GenerativeModel(model_to_use)
                        response = model.generate_content(current_files + [prompt])
                        
                        if response.text:
                            st.markdown(response.text)
                            st.session_state.messages.append({"role": "assistant", "content": response.text})
                            success = True
                    
                    except Exception as e:
                        diag_logs.append(f"Key {st.session_state.key_index+1}: {str(e)}")
                        st.session_state.key_index += 1
                        attempts += 1
                
                if not success:
                    st.error("❌ উত্তর তৈরি করা সম্ভব হয়নি।")
                    with st.expander("🛠️ বিস্তারিত এরর দেখুন"):
                        for log in diag_logs:
                            st.write(log)
