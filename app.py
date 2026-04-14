import streamlit as st
import google.generativeai as genai
import os
import time
from datetime import datetime, timedelta

# ══════════════════════════════════════════════
# ১. পেজ কনফিগারেশন
# ══════════════════════════════════════════════
st.set_page_config(
    page_title="পদক্ষেপ মিত্র",
    page_icon="🤖",
    layout="wide"
)

st.markdown("""
<style>
    .main-title {
        font-size: 2.8rem;
        font-weight: 700;
        text-align: center;
        color: white;
        margin-bottom: 0px;
    }
    .instruction {
        text-align: center;
        color: #B0B0B0;
        font-size: 1.0rem;
        margin-bottom: 6px;
    }
    .instruction-warning {
        text-align: center;
        color: #FFB347;
        font-size: 0.95rem;
        margin-bottom: 6px;
    }
    .instruction-tip {
        text-align: center;
        color: #87CEEB;
        font-size: 0.95rem;
        margin-bottom: 20px;
    }
</style>
<div class="main-title">🤖 পদক্ষেপ মিত্র (Official Assistant)</div>
<div class="instruction">তথ্য খোঁজার আগে বাম পাশের সেকশন থেকে টপিক সিলেক্ট করে নিন</div>
<div class="instruction-warning">⚠️ টপিক পরিবর্তনের আগে Cache পরিষ্কার করুন</div>
<div class="instruction-tip">💡 'গাইডলাইনে তথ্য নেই' এমন উত্তর আসলে ভিন্নভাবে প্রশ্নটি করুন</div>
""", unsafe_allow_html=True)


# ══════════════════════════════════════════════
# ২. API Key সেটআপ
# ══════════════════════════════════════════════
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
    st.session_state.key_fail_times = {}
if "messages" not in st.session_state:
    st.session_state.messages = []
if "uploaded_files_cache" not in st.session_state:
    st.session_state.uploaded_files_cache = {}
if "current_topic" not in st.session_state:
    st.session_state.current_topic = None
if "chat_session" not in st.session_state:
    st.session_state.chat_session = None


# ══════════════════════════════════════════════
# ৩. Smart Key Rotation
# ══════════════════════════════════════════════
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
    key = get_available_key()
    if key:
        genai.configure(api_key=key, transport='rest')
        return True
    return False


# ══════════════════════════════════════════════
# ৪. PDF Split Helper (বড় ফাইলের জন্য)
# ══════════════════════════════════════════════
MAX_FILE_SIZE_MB = 4  # এর বেশি হলে ভেঙে upload করা হবে

def split_pdf_if_large(pdf_path):
    """
    PDF যদি MAX_FILE_SIZE_MB-এর বেশি হয়,
    তাহলে ছোট ছোট ভাগে ভেঙে temp list return করে।
    নইলে original path-ই return করে।
    """
    file_size_mb = os.path.getsize(pdf_path) / (1024 * 1024)
    if file_size_mb <= MAX_FILE_SIZE_MB:
        return [pdf_path], False  # ছোট ফাইল — ভাঙার দরকার নেই

    try:
        from pypdf import PdfReader, PdfWriter

        reader = PdfReader(pdf_path)
        total_pages = len(reader.pages)
        pages_per_chunk = max(1, total_pages // 3)  # ৩ ভাগে ভাগ করো

        chunks = []
        base_name = os.path.splitext(pdf_path)[0]

        for i in range(0, total_pages, pages_per_chunk):
            writer = PdfWriter()
            end = min(i + pages_per_chunk, total_pages)
            for page_num in range(i, end):
                writer.add_page(reader.pages[page_num])

            chunk_path = f"{base_name}_part{i // pages_per_chunk + 1}.pdf"
            with open(chunk_path, "wb") as f:
                writer.write(f)
            chunks.append(chunk_path)

        return chunks, True  # বড় ফাইল — ভাঙা হয়েছে

    except Exception as e:
        # pypdf না থাকলে বা error হলে original ফাইলই ব্যবহার করো
        st.warning(f"⚠️ PDF split করা যায়নি, original ফাইল ব্যবহার হচ্ছে: {e}")
        return [pdf_path], False


# ══════════════════════════════════════════════
# ৫. File Validation (Expire চেক)
# ══════════════════════════════════════════════
def is_file_valid(file_ref):
    """
    Gemini-তে uploaded file এখনো valid/accessible কিনা চেক করা।
    ৪৮ ঘণ্টা পর file expire হয়ে যায়।
    """
    try:
        genai.get_file(file_ref.name)
        return True
    except Exception:
        return False


# ══════════════════════════════════════════════
# ৬. PDF Upload with Caching + Validation
# ══════════════════════════════════════════════
def get_or_upload_files(folder_name):
    """
    ১. Cache-এ থাকলে — validate করো।
       - Valid হলে → সরাসরি ব্যবহার করো (re-upload নয়)
       - Expired হলে → cache মুছে re-upload করো
    ২. Cache-এ না থাকলে → upload করে cache-এ রাখো
    """
    # Cache hit — validate করো
    if folder_name in st.session_state.uploaded_files_cache:
        cached = st.session_state.uploaded_files_cache[folder_name]
        with st.spinner("🔍 Cache যাচাই করছি..."):
            if all(is_file_valid(f) for f in cached):
                return cached, False  # ✅ Valid cache — re-upload নয়
            else:
                # Expired — cache সরাও, নতুনভাবে upload করতে হবে
                del st.session_state.uploaded_files_cache[folder_name]
                st.info("🔄 পুরনো file expire হয়েছে, পুনরায় upload করা হচ্ছে...")

    # Cache miss বা expired — upload করো
    if not configure_api():
        return None, "API key পাওয়া যাচ্ছে না"

    path = os.path.join("knowledge", folder_name)
    if not os.path.exists(path):
        return None, "ফোল্ডার পাওয়া যায়নি"

    pdf_files = [f for f in os.listdir(path) if f.lower().endswith(".pdf")]
    if not pdf_files:
        return None, "এই টপিকে কোনো PDF নেই"

    uploaded = []
    temp_chunks = []  # পরে মুছে দেওয়ার জন্য

    for pdf_name in pdf_files:
        pdf_path = os.path.join(path, pdf_name)

        # বড় PDF হলে ভাঙো
        file_paths, was_split = split_pdf_if_large(pdf_path)
        if was_split:
            temp_chunks.extend(file_paths)

        for chunk_path in file_paths:
            try:
                with st.spinner(f"📄 '{os.path.basename(chunk_path)}' upload হচ্ছে..."):
                    file_ref = genai.upload_file(chunk_path)
                    # Processing শেষ হওয়া পর্যন্ত অপেক্ষা
                    while file_ref.state.name == "PROCESSING":
                        time.sleep(1)
                        file_ref = genai.get_file(file_ref.name)
                    uploaded.append(file_ref)
            except Exception as e:
                # Temp chunks মুছো
                for tmp in temp_chunks:
                    if os.path.exists(tmp):
                        os.remove(tmp)
                return None, f"Upload error: {str(e)}"

    # Temp chunk files মুছো (split করা হয়েছিল)
    for tmp in temp_chunks:
        if os.path.exists(tmp):
            os.remove(tmp)

    # Cache-এ সেভ করো
    st.session_state.uploaded_files_cache[folder_name] = uploaded
    return uploaded, True


# ══════════════════════════════════════════════
# ৭. Chat Session তৈরি
# ══════════════════════════════════════════════
def create_chat_session(file_refs):
    """নতুন topic-এর জন্য নতুন chat session"""
    if not configure_api():
        return None
    try:
        model = genai.GenerativeModel(
            model_name="models/gemini-1.5-flash",
            system_instruction="""আপনি 'পদক্ষেপ মিত্র' - পদক্ষেপ মানবিক উন্নয়ন কেন্দ্রের অফিসিয়াল AI সহকারী।
আপনার কাজ: প্রদত্ত গাইডলাইন PDF অনুযায়ী কর্মীদের প্রশ্নের সঠিক ও নির্ভুল উত্তর দেওয়া।

নিয়মাবলী:
- শুধুমাত্র প্রদত্ত গাইডলাইন থেকে উত্তর দিন
- গাইডলাইনে না থাকলে স্পষ্টভাবে বলুন "এই বিষয়ে গাইডলাইনে তথ্য নেই"
- সবসময় বাংলায় উত্তর দিন
- উত্তর সংক্ষিপ্ত কিন্তু সম্পূর্ণ রাখুন"""
        )

        chat = model.start_chat(history=[])
        # প্রথম message-এ files পাঠানো (context set করা)
        chat.send_message(
            file_refs + ["এই গাইডলাইনগুলো মনোযোগ দিয়ে পড়ুন। আমি প্রস্তুত।"]
        )
        return chat

    except Exception as e:
        st.error(f"Chat session error: {e}")
        return None


# ══════════════════════════════════════════════
# ৮. সাইডবার
# ══════════════════════════════════════════════
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

# Cache পরিষ্কার বাটন
if st.sidebar.button("🗑 Cache পরিষ্কার করুন"):
    st.session_state.uploaded_files_cache = {}
    st.session_state.chat_session = None
    st.session_state.messages = []
    st.sidebar.success("✅ Cache পরিষ্কার হয়েছে!")

# Cached topics দেখানো
cached_topics = list(st.session_state.uploaded_files_cache.keys())
if cached_topics:
    st.sidebar.markdown("**✅ Cached Topics:**")
    for t in cached_topics:
        st.sidebar.markdown(f"- {t}")


# ══════════════════════════════════════════════
# ৯. চ্যাট মেসেজ দেখানো
# ══════════════════════════════════════════════
for m in st.session_state.messages:
    with st.chat_message(m["role"]):
        st.markdown(m["content"])


# ══════════════════════════════════════════════
# ১০. মূল চ্যাট লজিক
# ══════════════════════════════════════════════
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
                    # PDF upload (cache valid থাকলে skip)
                    file_refs, upload_status = get_or_upload_files(selected_folder)

                    if file_refs is None:
                        st.error(f"❌ {upload_status}")
                        break

                    # Chat session না থাকলে তৈরি করো
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

                    # Permission / file not found error → cache মুছো
                    if "permission" in error_msg.lower() or "does not exist" in error_msg.lower() or "not exist" in error_msg.lower():
                        if selected_folder in st.session_state.uploaded_files_cache:
                            del st.session_state.uploaded_files_cache[selected_folder]
                        st.session_state.chat_session = None
                        st.info("🔄 File permission error — পুনরায় upload করা হচ্ছে...")

                    # Rate limit error → key rotate করো
                    elif "quota" in error_msg.lower() or "rate" in error_msg.lower() or "429" in error_msg:
                        mark_key_failed()
                        st.session_state.chat_session = None

                    attempts += 1

            if not success:
                st.error("❌ সমস্যা সমাধান হয়নি। Cache পরিষ্কার করে আবার চেষ্টা করুন।")
                with st.expander("🛠 বিস্তারিত দেখুন"):
                    for log in error_logs:
                        st.write(log)
