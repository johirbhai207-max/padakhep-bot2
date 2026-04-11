import streamlit as st
import google.generativeai as genai
import os
import time

# ১. এপিআই সেটিংস
if "GEMINI_API_KEY" in st.secrets:
    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
else:
    st.error("API Key খুঁজে পাওয়া যায়নি! অনুগ্রহ করে Streamlit Secrets চেক করুন।")
    st.stop()

# ২. ফাইল আপলোড লজিক (যা প্রতিবার ফাইল ভেরিফাই করবে)
def get_verified_files():
    verified_files = []
    knowledge_dir = "knowledge"
    
    if not os.path.exists(knowledge_dir):
        return []

    try:
        # বর্তমান সার্ভারে থাকা ফাইলগুলোর তালিকা
        current_files = list(genai.list_files())
        remote_file_map = {f.display_name: f for f in current_files}
        
        for f_name in os.listdir(knowledge_dir):
            if f_name.lower().endswith(".pdf"):
                path = os.path.join(knowledge_dir, f_name)
                
                # যদি ফাইল সার্ভারে থাকে এবং ACTIVE থাকে
                if f_name in remote_file_map and remote_file_map[f_name].state.name == "ACTIVE":
                    verified_files.append(remote_file_map[f_name])
                else:
                    # নতুন করে আপলোড
                    with st.spinner(f"আপলোড হচ্ছে: {f_name}..."):
                        new_file = genai.upload_file(path, display_name=f_name)
                        # প্রসেসিং চেক
                        while new_file.state.name == "PROCESSING":
                            time.sleep(2)
                            new_file = genai.get_file(new_file.name)
                        verified_files.append(new_file)
    except Exception as e:
        st.warning("ফাইল ভেরিফিকেশনে সমস্যা হয়েছে।")
    
    return verified_files

# ৩. ইন্টারফেস সেটিংস
st.set_page_config(page_title="পদক্ষেপ মিত্র", page_icon="🤖")
st.title("🤖 পদক্ষেপ মিত্র (Official Assistant)")

if "messages" not in st.session_state:
    st.session_state.messages = []

# ৪. চ্যাট সেশন হ্যান্ডলিং (মেইন এরর ফিক্স)
# এখানে আমরা @st.cache_resource ব্যবহার করছি না কারণ এটিই মূল সমস্যার কারণ হতে পারে
if "chat_session" not in st.session_state:
    model = genai.GenerativeModel('gemini-1.5-flash')
    files = get_verified_files()
    
    # সেশন শুরু করার সময় যদি ফাইল থাকে তবে কনটেক্সটসহ শুরু করবে
    if files:
        try:
            # প্রথম প্রম্পটেই ফাইলগুলো ইনজেক্ট করা
            st.session_state.chat_session = model.start_chat(history=[])
            st.session_state.chat_session.send_message(["এই ফাইলগুলো তোমার রেফারেন্স হিসেবে ব্যবহার করো:", *files])
            st.toast("নলেজ বেস যুক্ত হয়েছে!", icon="✅")
        except Exception:
            st.session_state.chat_session = model.start_chat(history=[])
            st.info("সরাসরি সাধারণ চ্যাট মোডে চালু হয়েছে।")
    else:
        st.session_state.chat_session = model.start_chat(history=[])

# চ্যাট হিস্ট্রি প্রদর্শন
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# ৫. ইউজার ইনপুট প্রসেসিং
if prompt := st.chat_input("গাইডলাইন সম্পর্কে প্রশ্ন করুন..."):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        try:
            # স্ট্রিমিং অন রাখা হয়েছে যাতে কানেকশন ড্রপ হলেও যতটুকু রেসপন্স আসে তা দেখা যায়
            response = st.session_state.chat_session.send_message(prompt, stream=True)
            full_res = ""
            placeholder = st.empty()
            
            for chunk in response:
                full_res += chunk.text
                placeholder.markdown(full_res + "▌")
            
            placeholder.markdown(full_res)
            st.session_state.messages.append({"role": "assistant", "content": full_res})
        except Exception as e:
            st.error("দুঃখিত, সংযোগে সমস্যা হয়েছে।")
            st.info("আপনার API Key-র লিমিট শেষ হতে পারে অথবা ইন্টারনেট সমস্যা হতে পারে।")
