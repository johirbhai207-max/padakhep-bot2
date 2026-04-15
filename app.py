import streamlit as st
import google.generativeai as genai
import os
import time
from datetime import datetime, timedelta

# ১. পেজ কনফিগারেশন
st.set_page_config(page_title="পদক্ষেপ মিত্র", page_icon="🤖", layout="wide")

# ২. টাইটেল এবং স্টাইল
st.markdown("""
    <style>
    .main-title { font-size: 2.8rem; font-weight: 700; text-align: center; color: white; margin-bottom: 0px; }
    .instruction { text-align: center; color: #B0B0B0; font-size: 1.0rem; margin-bottom: 6px; }
    .instruction-warning { text-align: center; color: #FFB347; font-size: 0.95rem; margin-bottom: 6px; }
    .instruction-tip { text-align: center; color: #87CEEB; font-size: 0.95rem; margin-bottom: 20px; }
    </style>
    <div class="main-title">🤖 পদক্ষেপ মিত্র (Official Assistant)</div>
    <div class="instruction">তথ্য খোঁজার আগে বাম পাশের সেকশন থেকে টপিক সিলেক্ট করে নিন</div>
    <div class="instruction-warning">⚠️ টপিক পরিবর্তনের আগে Cache পরিষ্কার করুন</div>
    <div class="instruction-tip">💡 'গাইডলাইনে তথ্য নেই' এমন উত্তর আসলে ভিন্নভাবে প্রশ্নটি করুন</div>
    """, unsafe_allow_html=True)

# ৩. API Key সেটআপ (১০টি পর্যন্ত সাপোর্ট)
API_KEYS = [
    st.secrets.get("GEMINI_API_KEY_1"),
    st.secrets.get("GEMINI_API_KEY_2"),
    st.secrets.get("GEMINI_API_KEY_3"),
    st.secrets.get("GEMINI_API_KEY_4"),
    st.secrets.get("GEMINI_API_KEY_5"),
    st.secrets.get("GEMINI_API_KEY_6"),
    st.secrets.get("GEMINI_API_KEY_7"),
    st.secrets.get("GEMINI_API_KEY_8"),
    st.secrets.get("GEMINI_API_KEY_9"),
    st.secrets.get("GEMINI_API_KEY_10"),
]
VALID_KEYS = [k for k in API_KEYS if k]

# মডেল নাম
MODEL_NAME = "gemini-2.0-flash"

# ৪. Session State Initialize
if "key_index" not in st.session_state:
    st.session_state.key_index = 0
if "key_fail_times" not in st.session_state:
    st.session_state.key_fail_times = {}
if "messages" not in st.session_state:
    st.session_state.messages = []
if "uploaded_files_cache" not in st.session_state:
    st.session_state.uploaded_files_cache = {}
if "file_upload_key_index" not in st.session_state:
    st.session_state.file_upload_key_index = None
if "current_topic" not in st.session_state:
    st.session_state.current_topic = None
if "chat_session" not in st.session_state:
    st.session_state.chat_session = None

# ৫. Smart Key Rotation
COOLDOWN_MINUTES = 60

def get_available_key():
    """সময়-ভিত্তিক smart key rotation"""
    now = datetime.now()
    total = len(VALID_KEYS)
    for i in range(total):
        idx = (st.session_state.key_index + i) % total
        fail_time = st.session_state.key_fail_times.get(idx)
        if fail_time is None or (now - fail_time) > timedelta(minutes=COOLDOWN_MINUTES):
            st.session_state.key_index = idx
            return VALID_KEYS[idx]
    return None

def mark_key_failed():
    """বর্তমান key-কে failed হিসেবে mark করা"""
    st.session_state.key_fail_times[st.session_state.key_index] = datetime.now()
    st.session_state.key_index = (st.session_state.key_index + 1) % len(VALID_KEYS)

def configure_api():
    """নতুন available key দিয়ে API configure করা"""
    key = get_available_key()
    if key:
        genai.configure(api_key=key)
        return True
    return False

def configure_upload_key():
    """Upload-এ ব্যবহৃত সেই একই key দিয়ে API configure করা"""
    saved_idx = st.session_state.file_upload_key_index
    if saved_idx is not None and saved_idx < len(VALID_KEYS):
        genai.configure(api_key=VALID_KEYS[saved_idx])
        return True
    return False

# ৬. PDF Upload with Caching + Same Key Fix
def get_or_upload_files(folder_name):
    """
    Cache থেকে file reference নেয়।
    Cache না থাকলে upload করে cache-এ রাখে।
    upload ও chat-এ একই API key ব্যবহার নিশ্চিত করা হয়।
    """
    if folder_name in st.session_state.uploaded_files_cache:
        configure_upload_key()
        return st.session_state.uploaded_files_cache[folder_name]

    if not configure_api():
        raise Exception("কোনো API key পাওয়া যাচ্ছে না")

    st.session_state.file_upload_key_index = st.session_state.key_index

    uploaded = []
    path = os.path.join("knowledge", folder_name)

    if not os.path.exists(path):
        raise Exception("ফোল্ডার পাওয়া যায়নি")

    pdf_files = [f for f in os.listdir(path) if f.lower().endswith(".pdf")]

    if not pdf_files:
        raise Exception("এই টপিকে কোনো PDF নেই")

    for f in pdf_files:
        file_ref = genai.upload_file(os.path.join(path, f))
        while file_ref.state.name == "PROCESSING":
            time.sleep(1)
            file_ref = genai.get_file(file_ref.name)
        uploaded.append(file_ref)

    st.session_state.uploaded_files_cache[folder_name] = uploaded
    return uploaded

# ৭. Chat Session তৈরি — ✅ এখন exception raise করে, return None করে না
def create_chat_session(file_refs):
    """
    গুরুত্বপূর্ণ পরিবর্তন: আগে error হলে return None করত,
    এখন exception raise করে যাতে key rotation কাজ করে।
    """
    system_prompt = """আপনি 'পদক্ষেপ মিত্র' - পদক্ষেপ মানবিক উন্নয়ন কেন্দ্রের অফিসিয়াল AI সহকারী।
আপনার কাজ: প্রদত্ত গাইডলাইন PDF অনুযায়ী কর্মীদের প্রশ্নের সঠিক ও নির্ভুল উত্তর দেওয়া।

নিয়মাবলী:
- শুধুমাত্র প্রদত্ত গাইডলাইন থেকে উত্তর দিন
- গাইডলাইনে না থাকলে স্পষ্টভাবে বলুন "এই বিষয়ে গাইডলাইনে তথ্য নেই"
- সবসময় বাংলায় উত্তর দিন
- উত্তর সংক্ষিপ্ত কিন্তু সম্পূর্ণ রাখুন"""

    model = genai.GenerativeModel(
        model_name=MODEL_NAME,
        system_instruction=system_prompt
    )

    chat = model.start_chat(history=[])
    # ✅ এই line-এ exception হলে সরাসরি caller-এর except block-এ যাবে
    chat.send_message(file_refs + ["এই গাইডলাইনগুলো মনোযোগ দিয়ে পড়ুন। আমি প্রস্তুত।"])
    return chat

# ৮. সাইডবার
st.sidebar.title("📚 টপিক সিলেকশন")
knowledge_dir = "knowledge"
subfolders = []
if os.path.exists(knowledge_dir):
    subfolders = sorted([
        f for f in os.listdir(knowledge_dir)
        if os.path.isdir(os.path.join(knowledge_dir, f))
    ])

selected_folder = st.sidebar.selectbox(
    "একটি টপিক নির্বাচন করুন:",
    options=["সিলেক্ট করুন"] + subfolders
)

# Topic পরিবর্তন হলে chat reset
if selected_folder != st.session_state.current_topic:
    st.session_state.current_topic = selected_folder
    st.session_state.messages = []
    st.session_state.chat_session = None

# Cache clear বাটন
if st.sidebar.button("🗑️ Cache পরিষ্কার করুন"):
    st.session_state.uploaded_files_cache = {}
    st.session_state.chat_session = None
    st.session_state.messages = []
    st.session_state.file_upload_key_index = None
    st.sidebar.success("✅ Cache পরিষ্কার হয়েছে!")

# Active key ও cached topic সাইডবারে দেখানো
st.sidebar.markdown("---")
st.sidebar.markdown(f"🔑 **Active Key:** {st.session_state.key_index + 1} / {len(VALID_KEYS)}")
st.sidebar.markdown(f"🤖 **Model:** {MODEL_NAME}")

cached_topics = list(st.session_state.uploaded_files_cache.keys())
if cached_topics:
    st.sidebar.markdown("**✅ Cached Topics:**")
    for t in cached_topics:
        st.sidebar.markdown(f"- {t}")

# ৯. চ্যাট মেসেজ দেখানো
for m in st.session_state.messages:
    with st.chat_message(m["role"]):
        st.markdown(m["content"])

# ১০. মূল চ্যাট লজিক
if prompt := st.chat_input("গাইডলাইন সম্পর্কে প্রশ্ন করুন..."):
    if selected_folder == "সিলেক্ট করুন":
        st.warning("⚠️ আগে বাম পাশের সেকশন থেকে একটি টপিক সিলেক্ট করুন।")
    else:
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        with st.chat_message("assistant"):
            success = False
            attempts = 0
            error_logs = []

            while not success and attempts < len(VALID_KEYS):
                try:
                    # PDF upload (cache থাকলে skip, একই key active হবে)
                    with st.spinner("📄 গাইডলাইন লোড করছি..."):
                        file_refs = get_or_upload_files(selected_folder)

                    # Chat session না থাকলে তৈরি করা
                    if st.session_state.chat_session is None:
                        with st.spinner("🔧 সেশন তৈরি করছি..."):
                            # ✅ এখন exception raise হলে নিচের except block ধরবে
                            st.session_state.chat_session = create_chat_session(file_refs)

                    # প্রশ্ন পাঠানো
                    with st.spinner("💭 উত্তর তৈরি করছি..."):
                        response = st.session_state.chat_session.send_message(prompt)

                    if response.text:
                        st.markdown(response.text)
                        st.session_state.messages.append({
                            "role": "assistant",
                            "content": response.text
                        })
                        success = True

                except Exception as e:
                    error_msg = str(e)
                    error_logs.append(f"Key {st.session_state.key_index + 1}: {error_msg}")

                    # ✅ যেকোনো error-এই key rotate করা হচ্ছে
                    mark_key_failed()
                    st.session_state.chat_session = None
                    st.session_state.uploaded_files_cache = {}
                    st.session_state.file_upload_key_index = None

                    attempts += 1

            if not success:
                st.error("❌ সব API Key-এর limit শেষ হয়েছে। কিছুক্ষণ পর আবার চেষ্টা করুন।")
                with st.expander("🛠️ বিস্তারিত দেখুন"):
                    for log in error_logs:
                        st.write(log)
