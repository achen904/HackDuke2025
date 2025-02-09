import streamlit as st
import requests

st.title("DevilDiet Chatbot")

# Updated CSS with working fixed positioning
st.markdown("""
    <style>
    /* Main page layout adjustment */
    .main > div {
        padding-bottom: 10px !important;
        overflow-y: auto;
    }
    [data-testid="column"]>div>div>div>div>div {
        overflow: auto;
        height: 70vh;
    }

    .chat-container {
        height: 5vh;
        padding-bottom: 100px !important;
        max-height: calc(100vh - 160px) !important;
        overflow-y: auto;
        position: relative;
    }

    /* Message styling */
    .user-message {
        background-color: #f0f0f0;
        color: #000000;
        padding: 15px;
        border-radius: 20px;
        margin: 10px 0;
        max-width: 80%;
        margin-left: auto;
        overflow-y:auto;
    }

    .bot-message {
        background-color: #f0f0f0;
        color: #000000;
        padding: 15px;
        border-radius: 20px;
        margin: 10px 0;
        max-width: 80%;
        overflow-y:auto;
    }

    /* Fixed input container */
    .input-container {
        position: fixed !important;
        bottom: 0;
        left: 0;
        right: 0;
        background: #2c2c2c;
        padding: 15px;
        z-index: 9999;
        box-shadow: 0 -2px 15px rgba(0,0,0,0.2);
    }

    /* Textarea adjustments */
    .stTextArea textarea {
        width: calc(100% - 50px) !important;
        min-height: 45px !important;
        max-height: 150px !important;
        resize: none !important;
        line-height: 1.5 !important;
    }

    /* Submit button styling */
    .stButton button {
        width: 45px !important;
        height: 45px !important;
        border-radius: 50% !important;
        background-color: #007bff !important;
        color: white !important;
        margin-top: 2px !important;
    }

    /* Mobile keyboard avoidance */
    @media (max-height: 600px) {
        .chat-container {
            max-height: calc(100vh - 200px) !important;
        }
    }
    </style>
""", unsafe_allow_html=True)

if "messages" not in st.session_state:
    st.session_state.messages = []

def get_response(user_input):
    url = "http://127.0.0.1:5000/predict"
    response = requests.post(url, json={"input": user_input})
    return response.json().get("response", "Error from backend")

# Chat messages container
with st.container(height=500):
    st.markdown("<div class='chat-container'>", unsafe_allow_html=True)
    for message in st.session_state.messages:
        if "user" in message:
            st.markdown(f"<div class='user-message'>{message['user']}</div>", unsafe_allow_html=True)
        else:
            st.markdown(f"<div class='bot-message'>{message['bot']}</div>", unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)

scroll_script = """
<script>
    var container = window.parent.document.querySelector('.element-container');
    container.scrollTop = container.scrollHeight;
</script>
"""

st.markdown(scroll_script, unsafe_allow_html=True)

# Fixed input form at bottom
with st.container():
    st.markdown('<div class="input-container">', unsafe_allow_html=True)
    with st.form(key="chat_form", clear_on_submit=True):
        col1, col2 = st.columns([9, 1])
        
        with col1:
            user_input = st.text_input(
            label="Enter message",
            key="user_input",
            placeholder="Type your message...",
            max_chars=None  # No character limit
        )
        
        with col2:
            submitted = st.form_submit_button("↑")

       
        
        if submitted and user_input.strip():
            st.session_state.messages.append({"user": user_input})
            bot_response = get_response(user_input)
            st.session_state.messages.append({"bot": bot_response})
            st.rerun()

        css='''
        <style>
            section.main>div {
                padding-bottom: 1rem;
            }
            [data-testid="column"]>div>div>div>div>div {
                overflow: auto;
                height: 70vh;
            }
        </style>
        '''

        st.markdown(css, unsafe_allow_html = True)
    st.markdown('</div>', unsafe_allow_html=True)

# Enhanced JavaScript with better scroll handling
st.markdown("""
<script>
document.addEventListener('DOMContentLoaded', function() {
    const chatContainer = document.querySelector('.chat-container');

    function scrollToBottom() {
        setTimeout(() => {
            chatContainer.scrollTo({
                top: chatContainer.scrollHeight,
                behavior: 'smooth'
            });
        }, 200);  // Delay ensures content is fully loaded before scrolling
    }

    // Observe DOM changes and scroll properly
    const observer = new MutationObserver(() => {
        scrollToBottom();
    });

    observer.observe(chatContainer, {
        childList: true,
        subtree: true
    });

    scrollToBottom(); // Scroll to bottom on page load
});
</script>
""", unsafe_allow_html=True)