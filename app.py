import streamlit as st
import google.generativeai as genai
import os
import time

# ১. পেজ সেটিংস
st.set_page_config(page_title="পদক্ষেপ মিত্র", page_icon="🤖", layout="wide")

# ২. টাইটেল ও ইন্সট্রাকশন (এটি একটি স্ট্যাটিক ব্লকে রাখা হয়েছে যেন এরর না হয়)
st.markdown("<h1 style='text-align: center;'>🤖 পদক্ষেপ মিত্র (Official Assistant)</h1>", unsafe_allow_html=True)
st.markdown("<p style='text-align: center; color: #B0B0B0; font-size: 1.1rem;'>তথ্য খোঁজার আগে বাম পাশের সেকশন থেকে টপিক সিলেক্ট করে নিন</p>", unsafe_allow_html=True)
st.markdown("---")

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

# ৫. সাইডবার ও ইউজার ইন্টারফেস
st.sidebar.title("📚 টপিক সিলেকশন")
knowledge_dir = "knowledge"
subfolders = [f for f in os.listdir(knowledge_dir) if os.path.isdir(os.path.join(knowledge_dir, f))] if os.path.exists(knowledge_dir) else []
selected_folders = st.sidebar.multiselect("টপিক নির্বাচন করুন:", options=subfolders)

if "messages" not in st.session_state:
    st.session_state.messages = []

# চ্যাট হিস্ট্রি রেন্ডার করা
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
                        current_files = []
                        for folder in selected_folders:
                            path = os.path.join(knowledge_dir, folder)
                            if os.path.exists(path):
                                for f in os.listdir(path):
                                    if f.lower().endswith(".pdf"):
                                        res = upload_to_gemini(os.path.join(path, f))
                                        if isinstance(res, str) and "ERROR" in res: raise Exception(res)
                                        current_files.append(res)

                        # মডেল সিলেকশন
                        model = genai.GenerativeModel(model_name="gemini-1.5-flash")
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
                    st.error("❌ লিমিট শেষ অথবা টেকনিক্যাল সমস্যা। দয়া করে ৫-১০ মিনিট পর চেষ্টা করুন।")
                    with st.expander("🛠️ বিস্তারিত এরর দেখুন"):
                        for log in diag_logs:
                            st.write(log)
