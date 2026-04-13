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
    .stChatInputContainer { padding-bottom: 20px; }
    /* সাইডবার স্টাইল */
    section[data-testid="stSidebar"] { background-color: #1E1E1E; }
    </style>
    <div class="main-title">🤖 পদক্ষেপ মিত্র (Official Assistant)</div>
    <div class="instruction">তথ্য খোঁজার আগে বাম পাশের সেকশন থেকে টপিক সিলেক্ট করে নিন</div>
    """, unsafe_allow_html=True)

# ২. এপিআই কী রোটেশন সিস্টেম (৫টি কী এর জন্য)
API_KEYS = [
    st.secrets.get("GEMINI_API_KEY_1"),
    st.secrets.get("GEMINI_API_KEY_2"),
    st.secrets.get("GEMINI_API_KEY_3"),
    st.secrets.get("GEMINI_API_KEY_4"),
    st.secrets.get("GEMINI_API_KEY_5")
]
# শুধুমাত্র সচল কী-গুলো ফিল্টার করা
VALID_KEYS = [k for k in API_KEYS if k]

if "key_index" not in st.session_state:
    st.session_state.key_index = 0

def configure_with_current_key():
    if not VALID_KEYS:
        st.error("কোন API Key পাওয়া যায়নি! Secrets চেক করুন।")
        st.stop()
    current_key = VALID_KEYS[st.session_state.key_index % len(VALID_KEYS)]
    genai.configure(api_key=current_key)

# ৩. ফাইল আপলোড ফাংশন (Lazy Loading এর জন্য)
def upload_to_gemini(path):
    try:
        configure_with_current_key()
        file = genai.upload_file(path, mime_type="application/pdf")
        while file.state.name == "PROCESSING":
            time.sleep(1)
            file = genai.get_file(file.name)
        return file
    except Exception:
        # বর্তমান কী কাজ না করলে পরের কী ব্যবহার করবে
        st.session_state.key_index += 1
        return None

# ৪. সাইডবার - টপিক সিলেকশন (এটি শুরুতেই ফাইল লোড করবে না)
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

# ৫. চ্যাট হিস্ট্রি ম্যানেজমেন্ট
if "messages" not in st.session_state:
    st.session_state.messages = []

# আগের মেসেজগুলো স্ক্রিনে দেখানো
for m in st.session_state.messages:
    with st.chat_message(m["role"]):
        st.markdown(m["content"])

# ৬. মূল চ্যাট লজিক (ইউজার প্রশ্ন করলে যা হবে)
if prompt := st.chat_input("আপনার প্রশ্নটি এখানে লিখুন..."):
    if not selected_folders:
        st.warning("⚠️ তথ্য খোঁজার আগে বাম পাশের সেকশন থেকে অন্তত একটি টপিক সিলেক্ট করে নিন।")
    else:
        # ইউজারের প্রশ্ন সংরক্ষণ ও দেখানো
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        with st.chat_message("assistant"):
            with st.spinner("আপনার সিলেক্ট করা টপিক থেকে ফাইলগুলো বিশ্লেষণ করছি..."):
                # অন-ডিমান্ড ফাইল প্রসেসিং (Lazy Loading)
                relevant_files = []
                for folder in selected_folders:
                    folder_path = os.path.join(knowledge_dir, folder)
                    if os.path.exists(folder_path):
                        for f in os.listdir(folder_path):
                            if f.lower().endswith(".pdf"):
                                full_path = os.path.join(folder_path, f)
                                uploaded = upload_to_gemini(full_path)
                                if uploaded:
                                    relevant_files.append(uploaded)

                # এআই রেসপন্স তৈরির চেষ্টা
                success = False
                attempts = 0
                max_attempts = len(VALID_KEYS)
                
                while not success and attempts < max_attempts:
                    try:
                        configure_with_current_key()
                        # মডেল সেটআপ
                        model = genai.GenerativeModel(
                            model_name='gemini-1.5-flash',
                            system_instruction="তুমি 'পদক্ষেপ মিত্র' এআই অ্যাসিস্ট্যান্ট। তোমার কাজ হলো 'পদক্ষেপ মানবিক উন্নয়ন কেন্দ্র'-এর প্রদত্ত গাইডলাইন অনুযায়ী কর্মীদের প্রশ্নের উত্তর দেওয়া। শুধুমাত্র দেওয়া পিডিএফ ফাইলগুলো থেকে তথ্য ব্যবহার করবে। উত্তর স্পষ্ট এবং বাংলায় হবে।"
                        )
                        
                        # ফাইল ও টেক্সট ইনপুট
                        response = model.generate_content(relevant_files + [prompt])
                        
                        if response.text:
                            st.markdown(response.text)
                            st.session_state.messages.append({"role": "assistant", "content": response.text})
                            success = True
                    except Exception as e:
                        # এরর আসলে পরের কী-তে সুইচ করা
                        st.session_state.key_index += 1
                        attempts += 1
                        configure_with_current_key()
                
                if not success:
                    st.error("❌ সবগুলো এপিআই কী-এর লিমিট শেষ হয়ে গেছে। দয়া করে কিছুক্ষণ পর আবার চেষ্টা করুন।")
