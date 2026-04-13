import streamlit as st
import google.generativeai as genai
import os
import time
import random

# ১. পেজ কনফিগারেশন
st.set_page_config(page_title="পদক্ষেপ মিত্র", page_icon="🤖", layout="wide")

# ২. কাস্টম CSS (Modern Look)
st.markdown("""
    <style>
    .main-title {
        font-size: 2.8rem !important;
        font-weight: 700;
        text-align: center;
        color: white;
        margin-bottom: 5px;
    }
    .instruction {
        text-align: center;
        color: #B0B0B0;
        font-size: 1.1rem;
        margin-bottom: 30px;
    }
    </style>
    <div class="main-title">🤖 পদক্ষেপ মিত্র (Official Assistant)</div>
    <div class="instruction">তথ্য খোঁজার আগে বাম পাশের সেকশন থেকে টপিক সিলেক্ট করে নিন</div>
    """, unsafe_allow_html=True)

# ৩. এপিআই কী রোটেশন সিস্টেম (৫টি কী এর জন্য)
def configure_next_api_key():
    api_keys = [
        st.secrets.get("GEMINI_API_KEY_1"),
        st.secrets.get("GEMINI_API_KEY_2"),
        st.secrets.get("GEMINI_API_KEY_3"),
        st.secrets.get("GEMINI_API_KEY_4"),
        st.secrets.get("GEMINI_API_KEY_5")
    ]
    # শুধু যেগুলোতে ভ্যালু আছে সেগুলো ফিল্টার করা
    valid_keys = [k for k in api_keys if k]
    
    if not valid_keys:
        st.error("কোন API Key পাওয়া যায়নি! Secrets চেক করুন।")
        st.stop()
    
    # বর্তমান সেশনে কোন কী ব্যবহার হচ্ছে তা ট্র্যাক করা
    if "key_index" not in st.session_state:
        st.session_state.key_index = 0
    
    current_key = valid_keys[st.session_state.key_index % len(valid_keys)]
    genai.configure(api_key=current_key)
    return current_key

# ৪. ফাইল প্রসেসিং এবং ফোল্ডার সিলেকশন লজিক
def upload_to_gemini(path, mime_type="application/pdf"):
    try:
        configure_next_api_key()
        file = genai.upload_file(path, mime_type=mime_type)
        while file.state.name == "PROCESSING":
            time.sleep(2)
            file = genai.get_file(file.name)
        return file
    except Exception as e:
        # কী এরর হলে ইন্ডেক্স বাড়িয়ে আবার ট্রাই করার লজিক এখানে যুক্ত করা যায়
        st.session_state.key_index += 1
        return None

# ৫. সাইডবার - ফোল্ডার সিলেকশন
st.sidebar.title("📚 টপিক সিলেকশন")
knowledge_dir = "knowledge"
subfolders = [f for f in os.listdir(knowledge_dir) if os.path.isdir(os.path.join(knowledge_dir, f))]

selected_folders = st.sidebar.multiselect(
    "কোন টপিকগুলো থেকে উত্তর খুঁজবেন?",
    options=subfolders,
    default=None
)

# সিলেক্ট করা ফোল্ডারের ফাইলগুলো প্রসেস করা
@st.cache_resource(show_spinner="ফাইলগুলো প্রস্তুত করা হচ্ছে...")
def prepare_selected_knowledge(folders):
    files_to_use = []
    for folder in folders:
        folder_path = os.path.join(knowledge_dir, folder)
        for f in os.listdir(folder_path):
            if f.lower().endswith(".pdf"):
                path = os.path.join(folder_path, f)
                gemini_file = upload_to_gemini(path)
                if gemini_file:
                    files_to_use.append(gemini_file)
    return files_to_use

# ৬. মডেল সেটআপ
def get_chat_response(prompt, files):
    try:
        configure_next_api_key()
        model = genai.GenerativeModel(
            model_name='gemini-1.5-flash',
            system_instruction="তুমি পদক্ষেপ মানবিক উন্নয়ন কেন্দ্রের বিশেষজ্ঞ। শুধুমাত্র প্রদত্ত ফাইল থেকে সঠিক তথ্য দাও।"
        )
        # ফাইল এবং প্রম্পট একসাথে পাঠানো
        content = []
        content.extend(files)
        content.append(prompt)
        return model.generate_content(content)
    except Exception as e:
        # যদি এই কী তে এরর আসে (যেমন Rate Limit), পরের কী দিয়ে ট্রাই করবে
        st.session_state.key_index += 1
        configure_next_api_key()
        return "এপিআই লিমিট জনিত সমস্যা, দয়া করে আবার সেন্ড করুন।"

# ৭. চ্যাট ইন্টারফেস
if "messages" not in st.session_state:
    st.session_state.messages = []

for m in st.session_state.messages:
    with st.chat_message(m["role"]):
        st.markdown(m["content"])

if prompt := st.chat_input("আপনার প্রশ্নটি এখানে লিখুন..."):
    if not selected_folders:
        st.warning("দয়া করে বাম পাশ থেকে অন্তত একটি টপিক সিলেক্ট করুন।")
    else:
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        with st.chat_message("assistant"):
            uploaded_files = prepare_selected_knowledge(selected_folders)
            response = get_chat_response(prompt, uploaded_files)
            
            # রেসপন্স টেক্সট হ্যান্ডলিং
            res_text = response.text if hasattr(response, 'text') else str(response)
            st.markdown(res_text)
            st.session_state.messages.append({"role": "assistant", "content": res_text})
