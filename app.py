import streamlit as st
import google.generativeai as genai
import os
import time

# ১. পেজ কনফিগারেশন ও কাস্টম UI
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

# ২. এপিআই কী সেটিংস ও রোটেশন লজিক
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

def configure_next_key():
    if VALID_KEYS:
        current_key = VALID_KEYS[st.session_state.key_index % len(VALID_KEYS)]
        genai.configure(api_key=current_key)
        return current_key
    return None

# ৩. ফাইল আপলোড ফাংশন
def upload_to_gemini(path):
    try:
        configure_next_key()
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

# ৫. মূল চ্যাট এবং স্মার্ট মডেল কলিং (Fix for 404 Error)
if prompt := st.chat_input("গাইডলাইন সম্পর্কে প্রশ্ন করুন..."):
    if not selected_folders:
        st.warning("⚠️ তথ্য খোঁজার আগে বাম পাশের সেকশন থেকে অন্তত একটি টপিক সিলেক্ট করে নিন।")
    else:
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        with st.chat_message("assistant"):
            with st.spinner("গাইডলাইন বিশ্লেষণ করছি..."):
                
                success = False
                attempts = 0
                diag_logs = []

                while not success and attempts < len(VALID_KEYS):
                    current_key_num = (st.session_state.key_index % len(VALID_KEYS)) + 1
                    try:
                        configure_next_key()
                        
                        current_files = []
                        for folder in selected_folders:
                            folder_path = os.path.join(knowledge_dir, folder)
                            for f in os.listdir(folder_path):
                                if f.lower().endswith(".pdf"):
                                    res = upload_to_gemini(os.path.join(folder_path, f))
                                    if isinstance(res, str) and "ERROR" in res: raise Exception(res)
                                    current_files.append(res)

                        # ৪-৪ এরর ফিক্সের জন্য আমরা লিস্ট থেকে নাম চেক করবো
                        # অনেক সময় ভার্সন সমস্যার কারণে 'models/' যোগ করতে হয়
                        model_name = 'gemini-1.5-flash'
                        try:
                            # আপনার এপিআই ভার্সনে কোন নাম কাজ করবে তা চেক করা
                            available = [m.name for m in genai.list_models()]
                            if 'models/gemini-1.5-flash' in available:
                                model_name = 'models/gemini-1.5-flash'
                        except:
                            pass

                        model = genai.GenerativeModel(model_name)
                        response = model.generate_content(current_files + [prompt])
                        
                        if response.text:
                            st.markdown(response.text)
                            st.session_state.messages.append({"role": "assistant", "content": response.text})
                            success = True
                    
                    except Exception as e:
                        diag_logs.append(f"**Key {current_key_num}:** {str(e)}")
                        st.session_state.key_index += 1
                        attempts += 1
                
                if not success:
                    st.error("❌ উত্তর তৈরি করা সম্ভব হয়নি।")
                    with st.expander("🛠️ ডায়াগনস্টিক ট্র্যাকার (এরর ডিটেইলস)"):
                        for log in diag_logs:
                            st.write(log)
