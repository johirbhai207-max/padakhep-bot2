import streamlit as st
import google.generativeai as genai
import os
import time

# ১. পেজ সেটিংস ও লুক
st.set_page_config(page_title="পদক্ষেপ মিত্র", page_icon="🤖", layout="wide")

st.markdown("""
    <style>
    .main-title { font-size: 2.8rem; font-weight: 700; text-align: center; color: white; margin-bottom: 0px; }
    .instruction { text-align: center; color: #B0B0B0; margin-bottom: 30px; }
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
API_KEYS = [k for k in API_KEYS if k] # শুধু ভ্যালিড কী গুলো রাখা

if "key_index" not in st.session_state:
    st.session_state.key_index = 0

def get_current_key():
    return API_KEYS[st.session_state.key_index % len(API_KEYS)]

# ৩. ফাইল আপলোড লজিক (একবার আপলোড হলে বারবার করবে না)
@st.cache_resource
def upload_file_cached(file_path):
    try:
        genai.configure(api_key=get_current_key())
        file = genai.upload_file(file_path)
        while file.state.name == "PROCESSING":
            time.sleep(2)
            file = genai.get_file(file.name)
        return file
    except Exception:
        # কী লিমিট শেষ হলে পরবর্তী কী দিয়ে ট্রাই করা
        st.session_state.key_index += 1
        return None

# ৪. সাইডবার - টপিক সিলেকশন
st.sidebar.title("📚 টপিক সিলেকশন")
knowledge_dir = "knowledge"
subfolders = [f for f in os.listdir(knowledge_dir) if os.path.isdir(os.path.join(knowledge_dir, f))]

selected_folders = st.sidebar.multiselect(
    "কোন টপিকগুলো থেকে উত্তর খুঁজবেন?",
    options=subfolders
)

# ৫. চ্যাট সিস্টেম
if "messages" not in st.session_state:
    st.session_state.messages = []

for m in st.session_state.messages:
    with st.chat_message(m["role"]):
        st.markdown(m["content"])

if prompt := st.chat_input("আপনার প্রশ্নটি এখানে লিখুন..."):
    if not selected_folders:
        st.warning("আগে টপিক সিলেক্ট করুন!")
    else:
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        with st.chat_message("assistant"):
            with st.spinner("উত্তরের জন্য ফাইলগুলো বিশ্লেষণ করছি..."):
                files_to_send = []
                for folder in selected_folders:
                    folder_path = os.path.join(knowledge_dir, folder)
                    for f in os.listdir(folder_path):
                        if f.endswith(".pdf"):
                            uploaded = upload_file_cached(os.path.join(folder_path, f))
                            if uploaded: files_to_send.append(uploaded)

                # রেসপন্স জেনারেট করা
                success = False
                attempts = 0
                while not success and attempts < len(API_KEYS):
                    try:
                        genai.configure(api_key=get_current_key())
                        model = genai.GenerativeModel('gemini-1.5-flash')
                        response = model.generate_content(files_to_send + [prompt])
                        st.markdown(response.text)
                        st.session_state.messages.append({"role": "assistant", "content": response.text})
                        success = True
                    except Exception as e:
                        st.session_state.key_index += 1
                        attempts += 1
                
                if not success:
                    st.error("সবগুলো এপিআই কী-এর লিমিট শেষ। কিছুক্ষণ পর চেষ্টা করুন।")
