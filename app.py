import streamlit as st
import google.generativeai as genai
import os
import time

# ১. পেজ সেটিংস
st.set_page_config(page_title="পদক্ষেপ মিত্র", page_icon="🤖", layout="wide")

# ২. নাম ও ইন্সট্রাকশন (এটি একদম আলাদা ব্লকে রাখা হয়েছে)
header_container = st.container()
with header_container:
    st.markdown("<h1 style='text-align: center;'>🤖 পদক্ষেপ মিত্র (Official Assistant)</h1>", unsafe_allow_html=True)
    st.markdown("<p style='text-align: center; color: gray;'>তথ্য খোঁজার আগে বাম পাশের সেকশন থেকে টপিক সিলেক্ট করে নিন</p>", unsafe_allow_html=True)
    st.markdown("---")

# ৩. এপিআই কী লজিক (আপনার কাজ করা ভার্সন অনুযায়ী)
API_KEYS = [st.secrets.get(f"GEMINI_API_KEY_{i}") for i in range(1, 6)]
VALID_KEYS = [k for k in API_KEYS if k]

if "key_index" not in st.session_state:
    st.session_state.key_index = 0

def configure_key():
    if VALID_KEYS:
        key = VALID_KEYS[st.session_state.key_index % len(VALID_KEYS)]
        genai.configure(api_key=key, transport='rest')

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

# ৫. সাইডবার ও চ্যাট হিস্ট্রি
st.sidebar.title("📚 টপিক সিলেকশন")
knowledge_dir = "knowledge"
subfolders = [f for f in os.listdir(knowledge_dir) if os.path.isdir(os.path.join(knowledge_dir, f))] if os.path.exists(knowledge_dir) else []
selected_folders = st.sidebar.multiselect("টপিক নির্বাচন করুন:", options=subfolders)

if "messages" not in st.session_state:
    st.session_state.messages = []

for m in st.session_state.messages:
    with st.chat_message(m["role"]):
        st.markdown(m["content"])

# ৬. চ্যাট ইনপুট ও প্রসেসিং
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
                while not success and attempts < len(VALID_KEYS):
                    try:
                        configure_key()
                        current_files = []
                        for folder in selected_folders:
                            path = os.path.join(knowledge_dir, folder)
                            for f in os.listdir(path):
                                if f.lower().endswith(".pdf"):
                                    res = upload_to_gemini(os.path.join(path, f))
                                    if not (isinstance(res, str) and "ERROR" in res):
                                        current_files.append(res)

                        model = genai.GenerativeModel("gemini-1.5-flash")
                        response = model.generate_content(current_files + [prompt])
                        
                        st.markdown(response.text)
                        st.session_state.messages.append({"role": "assistant", "content": response.text})
                        success = True
                    except Exception as e:
                        st.session_state.key_index += 1
                        attempts += 1
                
                if not success:
                    st.error("লিমিট শেষ অথবা টেকনিক্যাল সমস্যা। দয়া করে একটু পর চেষ্টা করুন।")
