import streamlit as st
import google.generativeai as genai
import os
import time

# ১. পেজ কনফিগারেশন ও স্টাইল
st.set_page_config(page_title="পদক্ষেপ মিত্র", page_icon="🤖", layout="wide")

st.markdown("""
    <style>
    .main-title { font-size: 2.8rem; font-weight: 700; text-align: center; color: white; margin-bottom: 0px; }
    .instruction { text-align: center; color: #B0B0B0; font-size: 1.1rem; margin-bottom: 30px; }
    </style>
    <div class="main-title">🤖 পদক্ষেপ মিত্র (Official Assistant)</div>
    <div class="instruction">তথ্য খোঁজার আগে বাম পাশের সেকশন থেকে টপিক সিলেক্ট করে নিন</div>
    """, unsafe_allow_html=True)

# ২. এপিআই কী সেটিংস ও রোটেশন
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
        key = VALID_KEYS[st.session_state.key_index % len(VALID_KEYS)]
        genai.configure(api_key=key)
        return key
    return None

# ৩. ফাইল আপলোড লজিক (Lazy Loading)
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

# চ্যাট হিস্ট্রি
if "messages" not in st.session_state:
    st.session_state.messages = []

for m in st.session_state.messages:
    with st.chat_message(m["role"]):
        st.markdown(m["content"])

# ৫. চ্যাট প্রসেসিং ও ডায়াগনস্টিক ট্র্যাকার
if prompt := st.chat_input("গাইডলাইন সম্পর্কে প্রশ্ন করুন..."):
    if not selected_folders:
        st.warning("⚠️ আগে টপিক সিলেক্ট করুন।")
    else:
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        with st.chat_message("assistant"):
            with st.spinner("বিশ্লেষণ চলছে..."):
                
                success = False
                attempts = 0
                diag_logs = [] # এরর লগ জমা রাখার জন্য

                while not success and attempts < len(VALID_KEYS):
                    current_key_name = f"Key_{st.session_state.key_index % len(VALID_KEYS) + 1}"
                    try:
                        configure_next_key()
                        
                        # ফাইল আপলোড করা হচ্ছে (শুধুমাত্র সিলেক্ট করা ফোল্ডারের)
                        current_files = []
                        for folder in selected_folders:
                            path = os.path.join(knowledge_dir, folder)
                            for f in os.listdir(path):
                                if f.lower().endswith(".pdf"):
                                    up_result = upload_to_gemini(os.path.join(path, f))
                                    if isinstance(up_result, str) and "ERROR" in up_result:
                                        raise Exception(up_result)
                                    current_files.append(up_result)

                        # মডেল কল - আমরা এখানে সরাসরি 'gemini-1.5-flash' ব্যবহার করছি আপনার আগের কোড অনুযায়ী
                        model = genai.GenerativeModel('gemini-1.5-flash')
                        
                        input_data = current_files + [prompt]
                        response = model.generate_content(input_data)
                        
                        if response.text:
                            st.markdown(response.text)
                            st.session_state.messages.append({"role": "assistant", "content": response.text})
                            success = True
                    
                    except Exception as e:
                        err_msg = str(e)
                        diag_logs.append(f"**{current_key_name}:** {err_msg}")
                        st.session_state.key_index += 1
                        attempts += 1
                
                if not success:
                    st.error("❌ সবগুলো এপিআই কী ব্যবহার করেও উত্তর পাওয়া যায়নি।")
                    with st.expander("🛠️ ডায়াগনস্টিক ট্র্যাকার (এরর ডিটেইলস দেখুন)"):
                        for log in diag_logs:
                            st.write(log)
