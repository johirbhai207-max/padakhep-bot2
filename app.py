import streamlit as st
import google.generativeai as genai
import os
import time

# ১. পেজ কনফিগারেশন
st.set_page_config(page_title="পদক্ষেপ মিত্র", page_icon="🤖", layout="wide")

# ২. টাইটেল ও ইন্সট্রাকশন (এটি সবার ওপরে থাকবে, কোনো কন্ডিশনের ভেতরে নয়)
st.markdown("<h1 style='text-align: center;'>🤖 পদক্ষেপ মিত্র (Official Assistant)</h1>", unsafe_allow_html=True)
st.markdown("<p style='text-align: center; color: #B0B0B0; font-size: 1.1rem;'>তথ্য খোঁজার আগে বাম পাশের সেকশন থেকে টপিক সিলেক্ট করে নিন</p>", unsafe_allow_html=True)
st.markdown("---") # একটি দাগ দিয়ে চ্যাট এরিয়া আলাদা করা হলো

# ৩. এপিআই কী সেটিংস ও রোটেশন লজিক
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
        genai.configure(api_key=key, transport='rest')
        return key
    return None

# ৪. ফাইল আপলোড লজিক (আপনার কাজ করা ভার্সন)
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
subfolders = []
if os.path.exists(knowledge_dir):
    subfolders = [f for f in os.listdir(knowledge_dir) if os.path.isdir(os.path.join(knowledge_dir, f))]

selected_folders = st.sidebar.multiselect("টপিক নির্বাচন করুন:", options=subfolders)

if "messages" not in st.session_state:
    st.session_state.messages = []

for m in st.session_state.messages:
    with st.chat_message(m["role"]):
        st.markdown(m["content"])

# ৬. মূল চ্যাট লজিক (আপনার সেই সফল লজিক)
if prompt := st.chat_input("গাইডলাইন সম্পর্কে প্রশ্ন করুন..."):
    if not selected_folders:
        st.warning("⚠️ আগে বাম পাশের সেকশন থেকে টপিক সিলেক্ট করুন।")
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
                    try:
                        configure_key()
                        current_files = []
                        for folder in selected_folders:
                            path = os.path.join(knowledge_dir, folder)
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
                    st.error("❌ উত্তর তৈরি করা সম্ভব হয়নি। লিমিট শেষ হতে পারে।")
