import streamlit as st
import google.generativeai as genai
import os
import time

# ১. পেজ সেটিংস ও UI
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

# ২. এপিআই কী রোটেশন ও স্মার্ট কনফিগারেশন
API_KEYS = [st.secrets.get(f"GEMINI_API_KEY_{i}") for i in range(1, 6)]
VALID_KEYS = [k for k in API_KEYS if k]

if "key_index" not in st.session_state:
    st.session_state.key_index = 0

def configure_key():
    if VALID_KEYS:
        key = VALID_KEYS[st.session_state.key_index % len(VALID_KEYS)]
        genai.configure(api_key=key, transport='rest')
        return key
    return None

# ৩. ফাইল আপলোড লজিক (উইথ ক্যাশিং যাতে কোটা বাঁচে)
@st.cache_resource
def get_cached_files(selected_folders):
    uploaded_files = []
    knowledge_dir = "knowledge"
    for folder in selected_folders:
        path = os.path.join(knowledge_dir, folder)
        if os.path.exists(path):
            for f in os.listdir(path):
                if f.lower().endswith(".pdf"):
                    try:
                        file_path = os.path.join(path, f)
                        gen_file = genai.upload_file(file_path)
                        while gen_file.state.name == "PROCESSING":
                            time.sleep(2)
                            gen_file = genai.get_file(gen_file.name)
                        uploaded_files.append(gen_file)
                    except:
                        continue
    return uploaded_files

# ৪. সাইডবার
st.sidebar.title("📚 টপিক সিলেকশন")
knowledge_dir = "knowledge"
subfolders = [f for f in os.listdir(knowledge_dir) if os.path.isdir(os.path.join(knowledge_dir, f))] if os.path.exists(knowledge_dir) else []
selected_folders = st.sidebar.multiselect("টপিক নির্বাচন করুন:", options=subfolders)

if "messages" not in st.session_state:
    st.session_state.messages = []

for m in st.session_state.messages:
    with st.chat_message(m["role"]):
        st.markdown(m["content"])

# ৫. মূল চ্যাট লজিক (কোটা এরর ফিক্সড)
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
                        files = get_cached_files(tuple(selected_folders))
                        
                        # মডেল ডিটেকশন
                        model_name = "models/gemini-1.5-flash"
                        try:
                            models = [m.name for m in genai.list_models()]
                            if 'models/gemini-1.5-flash' in models: model_name = 'models/gemini-1.5-flash'
                            elif 'models/gemini-pro' in models: model_name = 'models/gemini-pro'
                        except: pass

                        model = genai.GenerativeModel(model_name)
                        response = model.generate_content(files + [prompt])
                        
                        if response.text:
                            st.markdown(response.text)
                            st.session_state.messages.append({"role": "assistant", "content": response.text})
                            success = True
                    
                    except Exception as e:
                        err_msg = str(e)
                        if "429" in err_msg: # কোটা শেষ হলে পরের কী-তে যাবে
                            diag_logs.append(f"Key {st.session_state.key_index+1}: লিমিট শেষ (Quota Full)")
                        else:
                            diag_logs.append(f"Key {st.session_state.key_index+1}: {err_msg}")
                        
                        st.session_state.key_index += 1
                        attempts += 1
                
                if not success:
                    st.error("❌ সব কয়টি এপিআই কী-এর লিমিট এই মুহূর্তের জন্য শেষ। দয়া করে ৫-১০ মিনিট পর চেষ্টা করুন।")
