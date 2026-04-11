import streamlit as st
import google.generativeai as genai
import os
import time

# ১. এপিআই সেটিংস
if "GEMINI_API_KEY" in st.secrets:
    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
else:
    st.error("API Key খুঁজে পাওয়া যায়নি!")
    st.stop()

# ২. ফাইল আপলোড ফাংশন (পুরো নতুন লজিক)
def get_working_files():
    final_files = []
    knowledge_dir = "knowledge"
    
    if not os.path.exists(knowledge_dir):
        return []

    try:
        # আগে দেখি সার্ভারে কোনো ফাইল অলরেডি আছে কি না
        existing_remote_files = list(genai.list_files())
        remote_dict = {f.display_name: f for f in existing_remote_files}
        
        for f_name in os.listdir(knowledge_dir):
            if f_name.lower().endswith(".pdf"):
                path = os.path.join(knowledge_dir, f_name)
                
                # যদি ফাইল থাকে এবং সেটি ACTIVE থাকে
                if f_name in remote_dict and remote_dict[f_name].state.name == "ACTIVE":
                    final_files.append(remote_dict[f_name])
                else:
                    # নতুন করে আপলোড
                    uploaded = genai.upload_file(path, display_name=f_name)
                    # প্রসেসিং শেষ হওয়া পর্যন্ত অপেক্ষা
                    timeout = 0
                    while uploaded.state.name == "PROCESSING" and timeout < 30:
                        time.sleep(2)
                        uploaded = genai.get_file(uploaded.name)
                        timeout += 2
                    if uploaded.state.name == "ACTIVE":
                        final_files.append(uploaded)
    except Exception as e:
        print(f"File sync error: {e}")
    
    return final_files

# ৩. ইন্টারফেস
st.set_page_config(page_title="পদক্ষেপ মিত্র", page_icon="🤖")
st.title("🤖 পদক্ষেপ মিত্র (Official Assistant)")

# সেশন স্ট্যাটাস চেক
if "messages" not in st.session_state:
    st.session_state.messages = []

# ৪. মডেল ও চ্যাট সেশন হ্যান্ডলিং (মেইন এরর ফিক্স)
if "chat_session" not in st.session_state:
    model = genai.GenerativeModel('gemini-1.5-flash')
    
    with st.spinner("নলেজ বেস চেক করা হচ্ছে..."):
        files = get_working_files()
    
    if files:
        try:
            # ফাইলগুলো পাঠিয়ে চ্যাট শুরু
            st.session_state.chat_session = model.start_chat(history=[
                {"role": "user", "parts": ["গাইডলাইন ফাইলগুলো গ্রহণ করো:", *files]},
                {"role": "model", "parts": ["আমি ফাইলগুলো পেয়েছি এবং পড়েছি। এখন উত্তর দিতে প্রস্তুত।"]}
            ])
            st.success("নলেজ বেস সচল হয়েছে!")
        except Exception:
            # যদি ফাইল নিয়ে স্টার্ট করতে এরর দেয়, তবে ফাইল ছাড়াই শুরু করবে
            st.session_state.chat_session = model.start_chat(history=[])
            st.warning("ফাইল প্রসেসিং-এ সমস্যা হয়েছে, আমি সাধারণ জ্ঞান থেকে উত্তর দিচ্ছি।")
    else:
        st.session_state.chat_session = model.start_chat(history=[])
        st.info("কোনো পিডিএফ ফাইল পাওয়া যায়নি।")

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
            # সরাসরি চ্যাট সেশন থেকে উত্তর নেওয়া
            response = st.session_state.chat_session.send_message(prompt)
            st.markdown(response.text)
            st.session_state.messages.append({"role": "assistant", "content": response.text})
        except Exception as e:
            st.error("দুঃখিত, কানেকশনে সমস্যা হচ্ছে। দয়া করে কিছুক্ষণ পর চেষ্টা করুন।")
