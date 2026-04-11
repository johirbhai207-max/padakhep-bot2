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

# ২. ফাইল আপলোড ফাংশন (আরও শক্তিশালী এবং এরর-প্রুফ)
def upload_files_safely():
    uploaded_gemini_files = []
    knowledge_dir = "knowledge"
    
    if os.path.exists(knowledge_dir):
        # জেমিনি সার্ভারে বর্তমানে থাকা ফাইলগুলোর লিস্ট নেওয়া
        remote_files = list(genai.list_files())
        remote_file_names = {f.display_name: f for f in remote_files}
        
        for f_name in os.listdir(knowledge_dir):
            if f_name.lower().endswith(".pdf"):
                path = os.path.join(knowledge_dir, f_name)
                
                # ফাইল যদি অলরেডি সার্ভারে থাকে তবে সেটি ব্যবহার করবে
                if f_name in remote_file_names:
                    uploaded_gemini_files.append(remote_file_names[f_name])
                else:
                    # নতুন ফাইল আপলোড
                    try:
                        new_file = genai.upload_file(path, display_name=f_name)
                        while new_file.state.name == "PROCESSING":
                            time.sleep(2)
                            new_file = genai.get_file(new_file.name)
                        uploaded_gemini_files.append(new_file)
                    except Exception as e:
                        st.warning(f"ফাইল {f_name} আপলোড করা যায়নি: {e}")
    return uploaded_gemini_files

# ৩. ইন্টারফেস সেটিংস
st.set_page_config(page_title="পদক্ষেপ মিত্র", page_icon="🤖")
st.title("🤖 পদক্ষেপ মিত্র (Official Assistant)")

# সেশন স্টেট ইনিশিয়ালাইজেশন
if "display_messages" not in st.session_state:
    st.session_state.display_messages = []

# নলেজ বেস লোড করা (একবারই হবে)
if "knowledge_files" not in st.session_state:
    with st.spinner("নলেজ বেস আপডেট হচ্ছে..."):
        st.session_state.knowledge_files = upload_files_safely()

# মডেল সেটআপ
model = genai.GenerativeModel(
    model_name='gemini-1.5-flash',
    system_instruction="তুমি 'পদক্ষেপ মিত্র'। সরবরাহকৃত ফাইলগুলো থেকে সঠিক উত্তর দাও। তথ্য না থাকলে বানিয়ে বলবে না।"
)

# চ্যাট সেশন শুরু করা (এরর হ্যান্ডলিং সহ)
if "chat_history" not in st.session_state:
    st.session_state.chat_history = model.start_chat(history=[])
    
    # প্রথম মেসেজে ফাইলগুলো ইনজেক্ট করা
    if st.session_state.knowledge_files:
        try:
            initial_prompt = "নিচের ফাইলগুলো তোমার জ্ঞানভাণ্ডার হিসেবে গ্রহণ করো:"
            content_to_send = [initial_prompt] + st.session_state.knowledge_files
            st.session_state.chat_history.send_message(content_to_send)
        except Exception as e:
            st.warning("ফাইলগুলো প্রসেস করতে সমস্যা হচ্ছে, আমি সাধারণ বুদ্ধিমত্তা দিয়ে উত্তর দিচ্ছি।")

# চ্যাট হিস্ট্রি প্রদর্শন
for msg in st.session_state.display_messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# ইউজার ইনপুট প্রসেসিং
if prompt := st.chat_input("প্রশ্ন করুন..."):
    st.session_state.display_messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        try:
            # স্ট্রিমিং রেসপন্স (দ্রুত রেসপন্সের জন্য)
            response = st.session_state.chat_history.send_message(prompt, stream=True)
            full_res = ""
            placeholder = st.empty()
            
            for chunk in response:
                full_res += chunk.text
                placeholder.markdown(full_res + "▌")
            
            placeholder.markdown(full_res)
            st.session_state.display_messages.append({"role": "assistant", "content": full_res})
        except Exception as e:
            st.error(f"দুঃখিত, সমস্যা হয়েছে। পেজটি রিফ্রেশ করে আবার চেষ্টা করুন।")
