document.addEventListener('DOMContentLoaded', () => {
    let currentSessionId = null;
    let isListening = false;
    let recognition = null;

    // Elements
    const loginBtn = document.getElementById('login-button');
    const registerBtn = document.getElementById('register-button');
    const logoutBtn = document.getElementById('logout-button');
    const newChatBtn = document.getElementById('new-chat');
    const sendBtn = document.getElementById('send-button');
    const userInput = document.getElementById('user-input');
    const micButton = document.getElementById('mic-button');

    // Show/hide UI
    function showLoginForm() {
        document.getElementById('login-form').style.display = 'block';
        document.getElementById('register-form').style.display = 'none';
        document.getElementById('chat-container').style.display = 'none';
    }

    function showRegisterForm() {
        document.getElementById('login-form').style.display = 'none';
        document.getElementById('register-form').style.display = 'block';
        document.getElementById('chat-container').style.display = 'none';
    }

    function showChat() {
        document.getElementById('login-form').style.display = 'none';
        document.getElementById('register-form').style.display = 'none';
        document.getElementById('chat-container').style.display = 'flex';
    }

    // Password toggle
    window.togglePasswordVisibility = function (id) {
        const input = document.getElementById(id);
        const icon = input.nextElementSibling;
        if (input.type === "password") {
            input.type = "text";
            icon.classList.replace("fa-eye", "fa-eye-slash");
        } else {
            input.type = "password";
            icon.classList.replace("fa-eye-slash", "fa-eye");
        }
    };

    function showErrorMessage(msg) {
        const div = document.createElement('div');
        div.className = 'error-message';
        div.textContent = msg;
        document.body.appendChild(div);
        setTimeout(() => div.remove(), 3000);
    }

    function createMessageElement(content, isUser) {
        const msg = document.createElement('div');
        msg.className = `message ${isUser ? 'user' : 'bot'}`;
        msg.textContent = content;

        // Time stamp
        const time = document.createElement('div');
        time.className = 'message-time';
        time.innerText = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
        msg.appendChild(time);

        // Add speaker button only for bot
        if (!isUser) {
            const speakerBtn = document.createElement('button');
            speakerBtn.className = 'speaker-button';
            speakerBtn.innerHTML = '<i class="fas fa-volume-up"></i>';
            speakerBtn.title = 'Speak response';
            speakerBtn.onclick = () => speakAloud(content);
            msg.appendChild(speakerBtn);
        }

        return msg;
    }

    function speakAloud(text) {
        if ('speechSynthesis' in window) {
            const utterance = new SpeechSynthesisUtterance(text);
            utterance.lang = 'en-US';
            window.speechSynthesis.speak(utterance);
        }
    }

    function sendMessage(message) {
        const chatBox = document.getElementById('chat-box');
        chatBox.appendChild(createMessageElement(message, true));
        chatBox.scrollTop = chatBox.scrollHeight;

        fetch('/chat', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ message, chatId: currentSessionId })
        })
        .then(res => res.json())
        .then(data => {
            if (data.success) {
                currentSessionId = data.chatId;

                // Create bot message container (empty for now)
                const msg = document.createElement('div');
                msg.className = 'message bot';

                const msgContent = document.createElement('span');
                msg.appendChild(msgContent); // Append empty span to type into

                chatBox.appendChild(msg);
                chatBox.scrollTop = chatBox.scrollHeight;

                // Typing effect
                const fullText = data.reply;
                let i = 0;
                const typing = setInterval(() => {
                    msgContent.textContent += fullText.charAt(i);
                    i++;
                    chatBox.scrollTop = chatBox.scrollHeight;

                    if (i >= fullText.length) {
                        clearInterval(typing);

                        // Add timestamp
                        const timeDiv = document.createElement('div');
                        timeDiv.className = 'message-time';
                        timeDiv.textContent = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
                        msg.appendChild(timeDiv);

                        // Add speaker button
                        const speakerBtn = document.createElement('button');
                        speakerBtn.className = 'speaker-button';
                        speakerBtn.innerHTML = '<i class="fas fa-volume-up"></i>';
                        speakerBtn.title = 'Speak response';
                        speakerBtn.onclick = () => speakAloud(fullText);
                        msg.appendChild(speakerBtn);

                        chatBox.scrollTop = chatBox.scrollHeight;
                        loadChatHistory();
                    }
                }, 30);
            }
        })
        .catch(() => showErrorMessage("Error connecting to server."));
    }

    function loadChatHistory() {
        fetch('/get_chat_history')
            .then(res => res.json())
            .then(data => {
                const list = document.getElementById('chat-history-list');
                list.innerHTML = '';
                if (data.success && data.chat_history.length) {
                    data.chat_history.forEach(chat => {
                        const item = document.createElement('div');
                        item.className = 'chat-history-item';
                        item.dataset.chatId = chat.chat_id;
                        item.innerHTML = `
                            <i class="fas fa-comment-medical"></i>
                            <div class="chat-info">
                                <span class="chat-title">${chat.title}</span>
                                <span class="chat-date">${new Date(chat.created_at).toLocaleDateString()}</span>
                            </div>`;
                        item.onclick = () => loadConversation(chat);
                        list.appendChild(item);
                    });
                } else {
                    list.innerHTML = '<div class="empty-history">No conversations yet</div>';
                }
            });
    }

    function loadConversation(chat) {
        currentSessionId = chat.chat_id;
        const box = document.getElementById('chat-box');
        box.innerHTML = '';
        const messages = Array.isArray(chat.messages) ? chat.messages : JSON.parse(chat.messages);
        messages.forEach(msg => {
            if (msg.role !== 'system') {
                box.appendChild(createMessageElement(msg.content, msg.role === 'user'));
            }
        });
        box.scrollTop = box.scrollHeight;
    }

    // Speech Recognition Setup
    if ('webkitSpeechRecognition' in window) {
        recognition = new webkitSpeechRecognition();
        recognition.continuous = true; // ⬅️ continuous mode
        recognition.interimResults = false;
        recognition.lang = 'en-US';

        recognition.onresult = (event) => {
            let finalTranscript = '';

            for (let i = event.resultIndex; i < event.results.length; ++i) {
                const result = event.results[i];
                if (result.isFinal) {
                    finalTranscript += result[0].transcript;
                }
            }

            if (finalTranscript.trim()) {
                const inputBox = document.getElementById('user-input');
                inputBox.value = finalTranscript.trim();
                inputBox.focus();
            }
        };


        recognition.onerror = () => {
            showErrorMessage("Voice input error.");
        };

    }


    micButton.addEventListener('click', () => {
        if (!recognition) return;

        if (!isListening) {
            recognition.start();
            isListening = true;
            micButton.innerHTML = '<i class="fas fa-microphone-slash"></i>';
            micButton.style.backgroundColor = '#dc2626';
        } else {
            recognition.stop();
            isListening = false;
            micButton.innerHTML = '<i class="fas fa-microphone"></i>';
            micButton.style.backgroundColor = '';
        }
    });



    // Button Handlers
    registerBtn.onclick = () => {
        const u = document.getElementById('register-username').value;
        const p = document.getElementById('register-password').value;
        fetch('/register', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ username: u, password: p })
        })
        .then(r => r.json())
        .then(data => {
            if (data.success) {
                showLoginForm();
                showErrorMessage("Registration successful! Please log in.");
            } else showErrorMessage(data.message);
        });
    };

    loginBtn.onclick = () => {
        const u = document.getElementById('login-username').value;
        const p = document.getElementById('login-password').value;
        fetch('/login', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ username: u, password: p })
        })
        .then(r => r.json())
        .then(data => {
            if (data.success) {
                showChat();
                loadChatHistory();
            } else showErrorMessage(data.message);
        });
    };

    logoutBtn.onclick = () => {
        fetch('/logout', { method: 'POST' }).then(() => location.reload());
    };

    newChatBtn.onclick = () => {
        fetch('/new_chat', { method: 'POST' })
            .then(res => res.json())
            .then(data => {
                if (data.success) {
                    currentSessionId = null;
                    document.getElementById('chat-box').innerHTML = `
                        <div class="chat-welcome">
                            <h3>Welcome to Your Virtual Consultation</h3>
                            <p>Ask your medical questions and receive professional advice</p>
                        </div>`;
                    loadChatHistory();
                }
            });
    };

    sendBtn.onclick = () => {
        const msg = userInput.value.trim();
        if (msg) {
            userInput.value = '';
            sendMessage(msg);
        }
    };

    userInput.addEventListener('keypress', e => {
        if (e.key === 'Enter') sendBtn.click();
    });

    // Initial redirect handling
    fetch('/chat_page')
        .then(res => res.redirected ? showLoginForm() : (showChat(), loadChatHistory()));
});
function showLoginForm() {
    document.getElementById('login-form').style.display = 'block';
    document.getElementById('register-form').style.display = 'none';
    document.getElementById('chat-container').style.display = 'none';
}

function showRegisterForm() {
    document.getElementById('login-form').style.display = 'none';
    document.getElementById('register-form').style.display = 'block';
    document.getElementById('chat-container').style.display = 'none';
}

// ✅ Make accessible globally
window.showRegisterForm = showRegisterForm;
window.showLoginForm = showLoginForm;
