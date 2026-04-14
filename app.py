import streamlit as st
import google.generativeai as genai
import os
import time
from datetime import datetime, timedelta

# ১. পেজ কনফিগারেশন
st.set_page_config(page_title="পদক্ষেপ মিত্র", page_icon="🤖", layout="wide")

st.markdown("""
    <style>
    .main-title { font-size: 2.8rem; font-weight: 700; text-align: center; color: white; margin-bottom: 0px; }
    .instruction { text-align: center; color: #B0B0B0; font-size: 1.1rem; margin-bottom: 30px; }
    </style>
    <div class="main-title">🤖 পদক্ষেপ মিত্র (Official Assistant)</div>
    <div class="instruction">তথ্য খোঁজার আগে বাম পাশের সেকশন থেকে টপিক সিলেক্ট করে নিন</div>
    """, unsafe_allow_html=True)

# ২. API Key সেটআপ
API_KEYS = [
    st.secrets.get("GEMINI_API_KEY_1"),
    st.secrets.get("GEMINI_API_KEY_2"),
    st.secrets.get("GEMINI_API_KEY_3"),
    st.secrets.get("GEMINI_API_KEY_4"),
    st.secrets.get("GEMINI_API_KEY_5"),
]
VALID_KEYS = [k for k in API_KEYS if k]

# Session state initialize
if "key_index" not in st.session_state:
    st.session_state.key_index = 0
if "key_fail_times" not in st.session_state:
    st.session_state.key_fail_times = {}  # key_index: datetime
if "messages" not in st.session_state:
    st.session_state.messages = []
if "uploaded_files_cache" not in st.session_state:
    st.session_state.uploaded_files_cache = {}  # folder_name: [gemini_file_refs]
if "current_topic" not in st.session_state:
    st.session_state.current_topic = None
if "chat_session" not in st.session_state:
    st.session_state.chat_session = None

# ৩. Smart Key Rotation
COOLDOWN_MINUTES = 60  # কত মিনিট পর আবার try করবে

def get_available_key():
    """সময়-ভিত্তিক smart key rotation"""
    now = datetime.now()
    total = len(VALID_KEYS)
    
    for i in range(total):
        idx = (st.session_state.key_index + i) % total
        fail_time = st.session_state.key_fail_times.get(idx)
        
        # যদি fail না হয়ে থাকে অথবা cooldown শেষ হয়ে গেছে
        if fail_time is None or (now - fail_time) > timedelta(minutes=COOLDOWN_MINUTES):
            st.session_state.key_index = idx
            return VALID_KEYS[idx]
    
    return None  # সব key limit-এ

def mark_key_failed():
    """বর্তমান key-কে failed হিসেবে mark করা"""
    st.session_state.key_fail_times[st.session_state.key_index] = datetime.now()
    st.session_state.key_index = (st.session_state.key_index + 1) % len(VALID_KEYS)

def configure_api():
    key = get_available_key()
    if key:
        genai.configure(api_key=key, transport='rest')
        return True
    return False

# ৪. PDF Upload with Caching (সবচেয়ে গুরুত্বপূর্ণ অপ্টিমাইজেশন)
def get_or_upload_files(folder_name):
    """
    Cache থেকে file reference নেয়।
    Cache না থাকলে upload করে cache-এ রাখে।
    ফলে একই topic-এ বারবার upload হয় না।
    """
    if folder_name in st.session_state.uploaded_files_cache:
        # ✅ Cache hit - আর upload হবে না!
        return st.session_state.uploaded_files_cache[folder_name], False

    # Cache miss - প্রথমবার upload করতে হবে
    if not configure_api():
        return None, "API key পাওয়া যাচ্ছে না"

    uploaded = []
    path = os.path.join("knowledge", folder_name)
    
    if not os.path.exists(path):
        return None, "ফোল্ডার পাওয়া যায়নি"

    pdf_files = [f for f in os.listdir(path) if f.lower().endswith(".pdf")]
    
    if not pdf_files:
        return None, "এই টপিকে কোনো PDF নেই"

    for f in pdf_files:
        try:
            file_ref = genai.upload_file(os.path.join(path, f))
            # Processing শেষ হওয়া পর্যন্ত অপেক্ষা
            while file_ref.state.name == "PROCESSING":
                time.sleep(1)
                file_ref = genai.get_file(file_ref.name)
            uploaded.append(file_ref)
        except Exception as e:
            return None, f"Upload error: {str(e)}"

    # Cache-এ সেভ করা
    st.session_state.uploaded_files_cache[folder_name] = uploaded
    return uploaded, True  # True = নতুন upload হয়েছে

# ৫. Chat Session তৈরি/রিসেট
def create_chat_session(file_refs):
    """নতুন topic-এর জন্য নতুন chat session"""
    if not configure_api():
        return None
    
    try:
        available_models = [
            m.name for m in genai.list_models()
            if 'generateContent' in m.supported_generation_methods
        ]
        model_name = next(
            (m for m in available_models if 'flash' in m),
            "models/gemini-1.5-flash"
        )
        
        system_prompt = """আপনি 'পদক্ষেপ মিত্র' - পদক্ষেপ মানবিক উন্নয়ন কেন্দ্রের অফিসিয়াল AI সহকারী।
আপনার কাজ: প্রদত্ত গাইডলাইন PDF অনুযায়ী কর্মীদের প্রশ্নের সঠিক ও নির্ভুল উত্তর দেওয়া।

নিয়মাবলী:
- শুধুমাত্র প্রদত্ত গাইডলাইন থেকে উত্তর দিন
- গাইডলাইনে না থাকলে স্পষ্টভাবে বলুন "এই বিষয়ে গাইডলাইনে তথ্য নেই"
- সবসময় বাংলায় উত্তর দিন
- উত্তর সংক্ষিপ্ত কিন্তু সম্পূর্ণ রাখুন"""
        
        model = genai.GenerativeModel(
            model_name=model_name,
            system_instruction=system_prompt
        )
        
        # File references সহ chat শুরু
        chat = model.start_chat(history=[])
        
        # প্রথম message-এ files পাঠানো (context set করা)
        chat.send_message(file_refs + ["এই গাইডলাইনগুলো মনোযোগ দিয়ে পড়ুন। আমি প্রস্তুত।"])
        
        return chat
    except Exception as e:
        st.error(f"Chat session error: {e}")
        return None

# ৬. সাইডবার
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

# Cache status sidebar-এ দেখানো
if st.sidebar.button("🗑️ Cache পরিষ্কার করুন"):
    st.session_state.uploaded_files_cache = {}
    st.session_state.chat_session = None
    st.sidebar.success("Cache পরিষ্কার হয়েছে!")

cached_topics = list(st.session_state.uploaded_files_cache.keys())
if cached_topics:
    st.sidebar.markdown("**✅ Cached Topics:**")
    for t in cached_topics:
        st.sidebar.markdown(f"- {t}")

# ৭. চ্যাট মেসেজ দেখানো
for m in st.session_state.messages:
    with st.chat_message(m["role"]):
        st.markdown(m["content"])

# ৮. মূল চ্যাট লজিক
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
                    # PDF upload (cache থাকলে skip)
                    with st.spinner("📄 গাইডলাইন লোড করছি..."):
                        file_refs, upload_status = get_or_upload_files(selected_folder)
                    
                    if file_refs is None:
                        st.error(f"❌ {upload_status}")
                        break

                    # Chat session না থাকলে তৈরি করা
                    if st.session_state.chat_session is None:
                        with st.spinner("🔧 সেশন তৈরি করছি..."):
                            st.session_state.chat_session = create_chat_session(file_refs)

                    if st.session_state.chat_session is None:
                        raise Exception("Chat session তৈরি হয়নি")

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
                    
                    # Rate limit error হলে key rotate করা
                    if "quota" in error_msg.lower() or "rate" in error_msg.lower() or "429" in error_msg:
                        mark_key_failed()
                        st.session_state.chat_session = None  # নতুন key দিয়ে নতুন session
                    
                    attempts += 1

            if not success:
                st.error("❌ সব API Key-এর limit শেষ হয়েছে। কিছুক্ষণ পর আবার চেষ্টা করুন।")
                with st.expander("🛠️ বিস্তারিত দেখুন"):
                    for log in error_logs:
                        st.write(log)
