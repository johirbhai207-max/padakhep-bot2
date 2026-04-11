import streamlit as st
import google.generativeai as genai
import os
import time

# --- ১. এপিআই সেটিংস ---
if "GEMINI_API_KEY" in st.secrets:
    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
else:
    st.error("API Key খুঁজে পাওয়া যায়নি! অনুগ্রহ করে Streamlit Secrets চেক করুন।")
    st.stop()

# --- ২. বুদ্ধিমান ফাইল আপলোডার ---
def sync_knowledge_base():
    knowledge_dir = "knowledge"
    final_files = []
    
    if not os.path.exists(knowledge_dir):
        return []

    # বর্তমানে গুগল সার্ভারে কী কী ফাইল আছে তা দেখা
    current_remote_files = {f.display_name: f for f in genai.list_files()}
    
    for filename in os.listdir(knowledge_dir):
        if filename.lower().endswith(".pdf"):
            filepath = os.path.join(knowledge_dir, filename)
            
            # যদি ফাইলটি সার্ভারে থাকে এবং সেটি সক্রিয় থাকে
            if filename in current_remote_files and current_remote_files[filename].state.name == "ACTIVE":
                final_files.append(current_remote_files[filename])
            else:
                # নতুন করে আপলোড করা
                try:
                    with st.status(f"প্রসেসিং: {filename}...", expanded=False):
                        new_file = genai.upload_file(filepath, display_name=filename)
                        while new_file.state.name == "PROCESSING":
                            time.sleep(2)
                            new_file = genai.get_file(new_file.name)
                        final_files.append(new_file)
                except Exception as e:
                    st.warning(f"{filename} আপলোড করা সম্ভব হয়নি।")
    
    return final_files

# --- ৩. ইন্টারফেস সেটিংস ---
st.set_page_config(page_title="পদক্ষেপ মিত্র", page_icon="🤖")
st.title("🤖 পদক্ষেপ মিত্র (Official Assistant)")

if "messages" not in st.session_state:
    st.session_state.messages = []

# ফাইল সিঙ্ক্রোনাইজেশন (প্রতিবার রিবুটে এটি চেক করবে)
if "active_files" not in st.session_state:
    st.session_state.active_files = sync_knowledge_base()

# মডেল ইনিশিয়ালাইজেশন
model = genai.GenerativeModel(
    model_name='gemini-1.5-flash',
    system_instruction="তুমি পদক্ষেপ মানবিক উন্নয়ন কেন্দ্রের সহকারী 'পদক্ষেপ মিত্র'। প্রদত্ত ফাইল থেকে তথ্য দাও।"
)

# চ্যাট সেশন শুরু
if "chat" not in st.session_state:
    # ফাইলগুলো সহ সেশন শুরু
    if st.session_state.active_files:
        st.session_state.chat = model.start_chat(history=[
            {"role": "user", "parts": ["এখানে গাইডলাইন ফাইলগুলো আছে।", *st.session_state.active_files]},
            {"role": "model", "parts": ["বুঝতে পেরেছি। আমি ফাইলগুলো পড়েছি। এখন প্রশ্ন করুন।"]}
        ])
    else:
        st.session_state.chat = model.start_chat(history=[])

# চ্যাট হিস্ট্রি প্রদর্শন
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# ইউজার ইনপুট
if prompt := st.chat_input("গাইডলাইন সম্পর্কে প্রশ্ন করুন..."):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        try:
            # সরাসরি জেনারেট করা
            response = st.session_state.chat.send_message(prompt)
            st.markdown(response.text)
            st.session_state.messages.append({"role": "assistant", "content": response.text})
        except Exception as e:
            st.error("ফাইলগুলো খুঁজে পাওয়া যাচ্ছে না। অনুগ্রহ করে 'Reboot App' দিন।")
            # ক্যাশ ক্লিয়ার করে দেওয়া যাতে পরের বার নতুন করে ফাইল আপলোড হয়
            del st.session_state.active_files
