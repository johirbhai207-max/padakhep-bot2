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
    /* চ্যাট কন্টেইনার এবং ইনপুট সেটিংস */
    .stChatInputContainer { padding-bottom: 20px; }
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

# ৩. ফাইল আপলোড ফাংশন (Lazy Loading এর জন্য)
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

# ৪. সাইডবার - টপিক সিলেকশন (ডাইনামিক ফোল্ডার লোডিং)
st.sidebar.title("📚 টপিক সিলেকশন")
knowledge_dir = "knowledge"
subfolders = []
if os.path.exists(knowledge_dir) and os.path.isdir(knowledge_dir):
    subfolders = [f for f in os.listdir(knowledge_dir) if os.path.isdir(os.path.join(knowledge_dir, f))]

selected_folders = st.sidebar.multiselect(
    "কোন টপিকগুলো থেকে উত্তর খুঁজবেন?",
    options=subfolders,
    help="এক বা একাধিক ফোল্ডার সিলেক্ট করুন"
)

# চ্যাট হিস্ট্রি ম্যানেজমেন্ট
if "messages" not in st.session_state:
    st.session_state.messages = []

# আগের মেসেজগুলো স্ক্রিনে রেন্ডার করা
for m in st.session_state.messages:
    with st.chat_message(m["role"]):
        st.markdown(m["content"])

# ৫. মূল চ্যাট এবং ডায়াগনস্টিক ট্র্যাকার লজিক
if prompt := st.chat_input("গাইডলাইন সম্পর্কে প্রশ্ন করুন..."):
    if not selected_folders:
        st.warning("⚠️ তথ্য খোঁজার আগে বাম পাশের সেকশন থেকে অন্তত একটি টপিক সিলেক্ট করে নিন।")
    else:
        # ইউজারের প্রশ্ন দেখানো
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        with st.chat_message("assistant"):
            with st.spinner("গাইডলাইন বিশ্লেষণ করছি..."):
                
                success = False
                attempts = 0
                max_attempts = len(VALID_KEYS)
                diag_logs = [] # এরর ট্র্যাকিং এর জন্য

                while not success and attempts < max_attempts:
                    current_key_num = (st.session_state.key_index % len(VALID_KEYS)) + 1
                    try:
                        configure_next_key()
                        
                        # শুধুমাত্র সিলেক্ট করা ফোল্ডারের ফাইল আপলোড
                        current_files = []
                        for folder in selected_folders:
                            folder_path = os.path.join(knowledge_dir, folder)
                            if os.path.exists(folder_path):
                                for f in os.listdir(folder_path):
                                    if f.lower().endswith(".pdf"):
                                        full_path = os.path.join(folder_path, f)
                                        result = upload_to_gemini(full_path)
                                        if isinstance(result, str) and "ERROR" in result:
                                            raise Exception(result)
                                        current_files.append(result)

                        # মডেল কল (আপনার আগের কাজ করা ভার্সন)
                        model = genai.GenerativeModel('gemini-1.5-flash')
                        
                        # ফাইল এবং প্রশ্ন পাঠিয়ে উত্তর তৈরি
                        response = model.generate_content(current_files + [prompt])
                        
                        if response.text:
                            st.markdown(response.text)
                            st.session_state.messages.append({"role": "assistant", "content": response.text})
                            success = True
                    
                    except Exception as e:
                        err_detail = str(e)
                        diag_logs.append(f"**Key {current_key_num}:** {err_detail}")
                        st.session_state.key_index += 1 # পরের কী-তে সুইচ
                        attempts += 1
                
                # যদি সব কী ব্যর্থ হয়
                if not success:
                    st.error("❌ দুঃখিত, কারিগরি কারণে উত্তর তৈরি করা সম্ভব হয়নি।")
                    with st.expander("🛠️ ডায়াগনস্টিক ট্র্যাকার (এরর ডিটেইলস দেখুন)"):
                        for log in diag_logs:
                            st.write(log)
