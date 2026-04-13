import streamlit as st
import google.generativeai as genai
import os
import time

# ১. পেজ সেটিংস
st.set_page_config(page_title="পদক্ষেপ মিত্র", page_icon="🤖", layout="wide")

# ২. মডার্ন ইউআই এবং ইন্সট্রাকশন
st.markdown("""
    <style>
    .main-title { font-size: 2.8rem !important; font-weight: 700; text-align: center; color: white; margin-bottom: 5px; }
    .instruction { text-align: center; color: #B0B0B0; font-size: 1.1rem; margin-bottom: 30px; }
    </style>
    <div class="main-title">🤖 পদক্ষেপ মিত্র (Official Assistant)</div>
    <div class="instruction">তথ্য খোঁজার আগে বাম পাশের সেকশন থেকে টপিক সিলেক্ট করে নিন</div>
    """, unsafe_allow_html=True)

# ৩. এপিআই কী রোটেশন লজিক
def get_api_keys():
    keys = []
    for i in range(1, 6):
        k = st.secrets.get(f"GEMINI_API_KEY_{i}")
        if k: keys.append(k)
    return keys

if "key_index" not in st.session_state:
    st.session_state.key_index = 0

def configure_genai():
    keys = get_api_keys()
    if not keys:
        st.error("Secrets-এ কোন API Key পাওয়া যায়নি!")
        st.stop()
    current_key = keys[st.session_state.key_index % len(keys)]
    genai.configure(api_key=current_key)

# ৪. ফাইল আপলোড লজিক (একবার আপলোড হবে এমন ভাবে)
@st.cache_resource(show_spinner="নলেজ বেস তৈরি হচ্ছে...")
def upload_files_once(folder_list):
    configure_genai()
    uploaded_files_map = {}
    knowledge_dir = "knowledge"
    
    for folder in folder_list:
        path = os.path.join(knowledge_dir, folder)
        files_in_folder = []
        for f in os.listdir(path):
            if f.lower().endswith(".pdf"):
                file_path = os.path.join(path, f)
                try:
                    # ফাইল আপলোড
                    gf = genai.upload_file(file_path)
                    while gf.state.name == "PROCESSING":
                        time.sleep(2)
                        gf = genai.get_file(gf.name)
                    files_in_folder.append(gf)
                except Exception:
                    continue
        uploaded_files_map[folder] = files_in_folder
    return uploaded_files_map

# ৫. সাইডবার
st.sidebar.title("📚 টপিক সিলেকশন")
knowledge_dir = "knowledge"
subfolders = [f for f in os.listdir(knowledge_dir) if os.path.isdir(os.path.join(knowledge_dir, f))]

selected_folders = st.sidebar.multiselect(
    "কোন টপিকগুলো থেকে উত্তর খুঁজবেন?",
    options=subfolders,
    default=None
)

# ৬. চ্যাট হিস্ট্রি
if "messages" not in st.session_state:
    st.session_state.messages = []

for m in st.session_state.messages:
    with st.chat_message(m["role"]):
        st.markdown(m["content"])

# ৭. রেসপন্স জেনারেশন
if prompt := st.chat_input("আপনার প্রশ্নটি এখানে লিখুন..."):
    if not selected_folders:
        st.warning("দয়া করে বাম পাশ থেকে অন্তত একটি টপিক সিলেক্ট করুন।")
    else:
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        with st.chat_message("assistant"):
            # শুধু সিলেক্ট করা ফোল্ডারগুলোর ফাইল ম্যাপ করা
            all_files_map = upload_files_once(tuple(subfolders)) # সব ফাইল একবার ক্যাশ হবে
            active_files = []
            for fld in selected_folders:
                active_files.extend(all_files_map.get(fld, []))

            success = False
            retries = 0
            keys_count = len(get_api_keys())

            while not success and retries < keys_count:
                try:
                    configure_genai()
                    model = genai.GenerativeModel(
                        model_name='gemini-1.5-flash',
                        system_instruction="তুমি পদক্ষেপের বিশেষজ্ঞ। শুধুমাত্র ফাইল থেকে উত্তর দাও।"
                    )
                    
                    response = model.generate_content([*active_files, prompt])
                    st.markdown(response.text)
                    st.session_state.messages.append({"role": "assistant", "content": response.text})
                    success = True
                except Exception as e:
                    # লিমিট শেষ হলে পরের কী-তে সুইচ করা
                    st.session_state.key_index += 1
                    retries += 1
                    if retries == keys_count:
                        st.error("সবগুলো এপিআই কী-এর লিমিট শেষ। কিছুক্ষণ পর চেষ্টা করুন।")
