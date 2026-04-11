import streamlit as st
import google.generativeai as genai
import os
import time

# ১. এপিআই সেটিংস (v1beta এর ঝামেলা এড়াতে সরাসরি কনফিগারেশন)
if "GEMINI_API_KEY" in st.secrets:
    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
else:
    st.error("API Key খুঁজে পাওয়া যায়নি!")
    st.stop()

# ২. ফাইল প্রসেসিং ফাংশন (যাতে একই ফাইল বারবার আপলোড না হয়)
def get_or_upload_files():
    uploaded_gemini_files = []
    knowledge_dir = "knowledge"
    
    # বর্তমান জেমিনি স্টোরেজে কী কী ফাইল আছে তা দেখা
    existing_files = {f.display_name: f for f in genai.list_files()}
    
    if os.path.exists(knowledge_dir):
        for f_name in os.listdir(knowledge_dir):
            if f_name.endswith(".pdf"):
                if f_name in existing_files:
                    uploaded_gemini_files.append(existing_files[f_name])
                else:
                    # নতুন ফাইল হলে আপলোড করা
                    path = os.path.join(knowledge_dir, f_name)
                    new_file = genai.upload_file(path, display_name=f_name)
                    while new_file.state.name == "PROCESSING":
                        time.sleep(2)
                        new_file = genai.get_file(new_file.name)
                    uploaded_gemini_files.append(new_file)
    return uploaded_gemini_files

# ৩. মূল চ্যাটবট লজিক
st.set_page_config(page_title="পদক্ষেপ মিত্র", page_icon="🤖")
st.title("🤖 পদক্ষেপ মিত্র (Official Assistant)")

# ফাইলগুলো একবারই লোড হবে
if "knowledge_files" not in st.session_state:
    with st.spinner("নলেজ বেস আপডেট হচ্ছে..."):
        st.session_state.knowledge_files = get_or_upload_files()

# মডেল সেটআপ
model = genai.GenerativeModel(
    model_name='gemini-1.5-flash',
    system_instruction="তুমি 'পদক্ষেপ মিত্র'। সরবরাহকৃত ফাইলগুলো থেকে উত্তর দাও। তথ্য না থাকলে বানিয়ে বলবে না।"
)

if "chat_history" not in st.session_state:
    # ইতিহাসে ফাইলগুলো জুড়ে দেওয়া
    initial_parts = ["এখানে পদক্ষেপের গাইডলাইনগুলো দেওয়া হলো:"]
    initial_parts.extend(st.session_state.knowledge_files)
    st.session_state.chat_history = model.start_chat(history=[])
    # প্রথম মেসেজেই ফাইলগুলো পাঠিয়ে দেওয়া (স্ট্যাবল মেথড)
    st.session_state.chat_history.send_message(initial_parts)

# চ্যাট ইন্টারফেস
if "display_messages" not in st.session_state:
    st.session_state.display_messages = []

for msg in st.session_state.display_messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

if prompt := st.chat_input("প্রশ্ন করুন..."):
    st.session_state.display_messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        try:
            response = st.session_state.chat_history.send_message(prompt)
            st.markdown(response.text)
            st.session_state.display_messages.append({"role": "assistant", "content": response.text})
        except Exception as e:
            st.error(f"দুঃখিত, সমস্যা হয়েছে। এরর: {e}")
