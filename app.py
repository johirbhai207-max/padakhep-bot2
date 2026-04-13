import streamlit as st
import google.generativeai as genai
import os
import PyPDF2

# ১. পেজ কনফিগারেশন
st.set_page_config(page_title="পদক্ষেপ মিত্র", page_icon="🤖", layout="wide")

st.markdown("""
    <style>
    .main-title { font-size: 2.8rem; font-weight: 700; text-align: center; color: white; margin-bottom: 0px; }
    .instruction { text-align: center; color: #B0B0B0; font-size: 1.1rem; margin-bottom: 30px; }
    section[data-testid="stSidebar"] { background-color: #1E1E1E; }
    </style>
    <div class="main-title">🤖 পদক্ষেপ মিত্র (Official Assistant)</div>
    <div class="instruction">তথ্য খোঁজার আগে বাম পাশের সেকশন থেকে টপিক সিলেক্ট করে নিন</div>
    """, unsafe_allow_html=True)

# ২. এপিআই কী রোটেশন সিস্টেম
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

def get_current_api_key():
    if not VALID_KEYS:
        st.error("কোন API Key পাওয়া যায়নি! Secrets চেক করুন।")
        st.stop()
    return VALID_KEYS[st.session_state.key_index % len(VALID_KEYS)]

# ৩. পিডিএফ থেকে টেক্সট এক্সট্রাক্ট করা
@st.cache_data(show_spinner=False)
def extract_text_from_pdf(file_path):
    text = ""
    try:
        with open(file_path, "rb") as f:
            reader = PyPDF2.PdfReader(f)
            for page in reader.pages:
                page_text = page.extract_text()
                if page_text:
                    text += page_text + "\n"
    except Exception as e:
        st.error(f"পিডিএফ রিড করতে সমস্যা: {os.path.basename(file_path)}")
    return text

# ৪. সাইডবার - টপিক সিলেকশন
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

# ৫. চ্যাট হিস্ট্রি
if "messages" not in st.session_state:
    st.session_state.messages = []

for m in st.session_state.messages:
    with st.chat_message(m["role"]):
        st.markdown(m["content"])

# ৬. মূল চ্যাট লজিক
if prompt := st.chat_input("আপনার প্রশ্নটি এখানে লিখুন..."):
    if not selected_folders:
        st.warning("⚠️ তথ্য খোঁজার আগে বাম পাশের সেকশন থেকে অন্তত একটি টপিক সিলেক্ট করে নিন।")
    else:
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        with st.chat_message("assistant"):
            with st.spinner("গাইডলাইন থেকে তথ্য খোঁজা হচ্ছে..."):
                
                context_text = ""
                for folder in selected_folders:
                    folder_path = os.path.join(knowledge_dir, folder)
                    if os.path.exists(folder_path):
                        for f in os.listdir(folder_path):
                            if f.lower().endswith(".pdf"):
                                full_path = os.path.join(folder_path, f)
                                context_text += f"\n--- {f} ---\n"
                                context_text += extract_text_from_pdf(full_path)

                # সাইজ লিমিটেশন (অতিরিক্ত বড় ফাইলের কারণে যেন ক্র্যাশ না করে)
                char_limit = 80000 # প্রায় 20k টোকেন, যা ফ্রি টায়ারের জন্য নিরাপদ
                if len(context_text) > char_limit:
                    st.info(f"আপনার ফাইলে অনেক তথ্য ({len(context_text)} অক্ষর)। দ্রুত উত্তরের জন্য ফাইলের মূল অংশ প্রসেস করা হচ্ছে।")
                    context_text = context_text[:char_limit]

                success = False
                attempts = 0
                max_attempts = len(VALID_KEYS)
                last_error_message = ""
                
                while not success and attempts < max_attempts:
                    try:
                        current_key = get_current_api_key()
                        genai.configure(api_key=current_key)
                        
                        model = genai.GenerativeModel(
                            model_name='gemini-1.5-flash',
                            system_instruction="তুমি 'পদক্ষেপ মিত্র' এআই অ্যাসিস্ট্যান্ট। তোমার কাজ হলো 'পদক্ষেপ মানবিক উন্নয়ন কেন্দ্র'-এর প্রদত্ত গাইডলাইন টেক্সট অনুযায়ী কর্মীদের প্রশ্নের উত্তর দেওয়া।"
                        )
                        
                        final_prompt = f"নিচের গাইডলাইনটি পড়ো:\n{context_text}\n\nপ্রশ্ন: {prompt}"
                        
                        response = model.generate_content(final_prompt)
                        
                        if response.text:
                            st.markdown(response.text)
                            st.session_state.messages.append({"role": "assistant", "content": response.text})
                            success = True
                    
                    except Exception as e:
                        last_error_message = str(e) # আসল এররটি সেভ করে রাখছি
                        st.session_state.key_index += 1
                        attempts += 1
                
                # যদি সব চেষ্টাই ব্যর্থ হয়, তবে গুগল ঠিক কী বলছে তা স্ক্রিনে প্রিন্ট করা
                if not success:
                    st.error("❌ উত্তর তৈরি করা যায়নি!")
                    st.warning(f"Google API Error Details: {last_error_message}")
