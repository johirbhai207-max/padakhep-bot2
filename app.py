import streamlit as st
import google.generativeai as genai
import os
import time

# ১. পেজ সেটিংস
st.set_page_config(page_title="পদক্ষেপ মিত্র", page_icon="🤖", layout="wide")

# ২. টাইটেল ও ইন্সট্রাকশন ফিক্স (যা উধাও হয়ে গিয়েছিল)
st.markdown("""
    <style>
    .main-title { font-size: 2.8rem; font-weight: 700; text-align: center; color: white; margin-bottom: 0px; }
    .instruction { text-align: center; color: #B0B0B0; font-size: 1.1rem; margin-bottom: 30px; }
    </style>
    <div class="main-title">🤖 পদক্ষেপ মিত্র (Official Assistant)</div>
    <div class="instruction">তথ্য খোঁজার আগে বাম পাশের সেকশন থেকে টপিক সিলেক্ট করে নিন</div>
    """, unsafe_allow_html=True)

# ৩. এপিআই কী সেটিংস ও রোটেশন
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

# ৪. ফাইল আপলোড লজিক
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

# ৫. সাইডবার
st.sidebar.title("📚 টপিক সিলেকশন")
knowledge_dir = "knowledge"
subfolders = [f for f in os.listdir(knowledge_dir) if os.path.isdir(os.path.join(knowledge_dir, f))] if os.path.exists(knowledge_dir) else []
selected_folders = st.sidebar.multiselect("টপিক নির্বাচন করুন:", options=subfolders)

if "messages" not in st.session_state:
    st.session_state.messages = []

# চ্যাট হিস্ট্রি দেখানো
for m in st.session_state.messages:
    with st.chat_message(m["role"]):
        st.markdown(m["content"])

# ৬. মূল চ্যাট লজিক
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
                        
                        # ফাইল কালেকশন
                        current_files = []
                        for folder in selected_folders:
                            path = os.path.join(knowledge_dir, folder)
                            if os.path.exists(path):
                                for f in os.listdir(path):
                                    if f.lower().endswith(".pdf"):
                                        res = upload_to_gemini(os.path.join(path, f))
                                        if isinstance(res, str) and "ERROR" in res: raise Exception(res)
                                        current_files.append(res)

                        # ডাইনামিক মডেল সিলেকশন
                        available_models = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
                        model_name = next((m for m in available_models if 'flash' in m), "models/gemini-1.5-flash")
                        
                        model = genai.GenerativeModel(model_name=model_name)
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
                    st.error("❌ সব কয়টি এপিআই কী-এর লিমিট শেষ বা সার্ভার ব্যস্ত। দয়া করে কিছুক্ষণ পর আবার চেষ্টা করুন।")
                    with st.expander("🛠️ বিস্তারিত এরর দেখুন"):
                        for log in diag_logs:
                            st.write(log)
