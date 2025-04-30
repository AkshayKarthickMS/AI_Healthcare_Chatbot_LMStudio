const micBtn = document.getElementById('mic-button');
if ('webkitSpeechRecognition' in window) {
    const recognition = new webkitSpeechRecognition();
    recognition.lang = 'en-US';
    recognition.interimResults = false;

    micBtn.onclick = () => recognition.start();
    recognition.onresult = (e) => {
        document.getElementById('user-input').value = e.results[0][0].transcript;
    };
} else {
    micBtn.style.display = 'none';
}

window.onload = () => {
    fetch('/chat_page')
        .then(r => r.redirected ? showLoginForm() : document.getElementById('chat-container').style.display = 'flex');
};
// Global variables for session management
let currentSessionId = null;
let currentChatHistory = [];

// Toggle between Login and Register forms
function showLoginForm() {
    document.getElementById('login-form').classList.add('active');
    document.getElementById('register-form').classList.remove('active');
}

function showRegisterForm() {
    document.getElementById('login-form').classList.remove('active');
    document.getElementById('register-form').classList.add('active');
}

document.getElementById('send-button').onclick = sendMessage;
document.getElementById('user-input').addEventListener('keypress', e => {
    if (e.key === 'Enter') sendMessage();
});

function sendMessage() {
    const input = document.getElementById('user-input');
    const message = input.value.trim();
    if (!message) return;
    input.value = '';
    appendMessage(message, true);
    fetch('/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message })
    }).then(res => res.json())
      .then(data => {
        if (data.success) {
            appendMessage(data.reply, false, true);
        }
    });
}

function appendMessage(text, isUser, speak = false) {
    const msg = document.createElement('div');
    msg.className = `message ${isUser ? 'user' : 'bot'}`;
    msg.textContent = text;
    document.getElementById('chat-box').appendChild(msg);
    document.getElementById('chat-box').scrollTop = document.getElementById('chat-box').scrollHeight;

    if (!isUser && speak) {
        const utterance = new SpeechSynthesisUtterance(text);
        utterance.lang = 'en-US';
        speechSynthesis.speak(utterance);
    }
}

// Toggle password visibility
function togglePasswordVisibility(inputId) {
    const input = document.getElementById(inputId);
    const icon = input.nextElementSibling;
    if (input.type === "password") {
        input.type = "text";
        icon.classList.remove('fa-eye');
        icon.classList.add('fa-eye-slash');
    } else {
        input.type = "password";
        icon.classList.remove('fa-eye-slash');
        icon.classList.add('fa-eye');
    }
}

// Show message function for validation errors
function showErrorMessage(message) {
    const errorDiv = document.createElement('div');
    errorDiv.className = 'error-message';
    errorDiv.textContent = message;
    errorDiv.style.cssText = `
        position: fixed;
        top: 20px;
        right: 20px;
        background-color: #fed7d7;
        color: #c53030;
        padding: 1rem;
        border-radius: 8px;
        box-shadow: 0 2px 6px rgba(0,0,0,0.1);
        z-index: 1000;
    `;
    document.body.appendChild(errorDiv);
    setTimeout(() => errorDiv.remove(), 3000);
}

// Helper function to create message elements
function createMessageElement(content, isUser, messageId = null) {
    const messageDiv = document.createElement('div');
    messageDiv.className = `message ${isUser ? 'user' : 'bot'}`;
    messageDiv.textContent = content;
    messageDiv.dataset.messageId = messageId;

    if (!isUser) {
        const speakerBtn = document.createElement('button');
        speakerBtn.className = 'speaker-button';
        speakerBtn.title = 'Read Aloud';
        speakerBtn.innerHTML = '<i class="fas fa-volume-up"></i>';
        speakerBtn.onclick = () => {
            const utterance = new SpeechSynthesisUtterance(content);
            utterance.lang = 'en-US';
            speechSynthesis.speak(utterance);
        };
        messageDiv.appendChild(speakerBtn);
    }    

    const timeDiv = document.createElement('div');
    timeDiv.className = 'message-time';
    timeDiv.textContent = new Date().toLocaleTimeString();
    messageDiv.appendChild(timeDiv);

    return messageDiv;
}

// Function to create chat history item


// Function to regenerate a response
function regenerateResponse(messageId) {
    const chatBox = document.getElementById('chat-box');
    const messages = Array.from(chatBox.children);
    const messageIndex = messages.findIndex(msg => msg.dataset.messageId === messageId);
    
    if (messageIndex >= 0) {
        const userMessage = messages[messageIndex - 1].textContent;
        const previousMessages = [];
        
        // Collect conversation history up to this point
        for (let i = 0; i < messageIndex; i++) {
            const msg = messages[i];
            previousMessages.push({
                role: msg.classList.contains('user') ? 'user' : 'assistant',
                content: msg.textContent.replace(/\n.*$/, '') // Remove timestamp
            });
        }

        // Send regenerate request
        fetch('/chat', {
            method: 'POST',
            headers: { 
                'Content-Type': 'application/json',
                'X-Session-ID': currentSessionId
            },
            body: JSON.stringify({
                message: userMessage,
                regenerate: true,
                previousMessages: previousMessages,
                messageId: messageId
            })
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                messages[messageIndex].replaceWith(
                    createMessageElement(data.reply, false, messageId)
                );
            }
        })
        .catch(console.error);
    }
}

// Register button click event
document.getElementById('register-button').onclick = () => {
    const u = document.getElementById('register-username').value;
    const p = document.getElementById('register-password').value;
    fetch('/register', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username: u, password: p })
    }).then(r => r.json()).then(data => {
        if (data.success) showLoginForm();
        else alert(data.message);
    });
};

// Login button click event
document.getElementById('login-button').onclick = () => {
    const u = document.getElementById('login-username').value;
    const p = document.getElementById('login-password').value;
    fetch('/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username: u, password: p })
    }).then(r => r.json()).then(data => {
        if (data.success) {
            document.getElementById('chat-container').style.display = 'flex';
            document.getElementById('login-form').style.display = 'none';
        } else alert(data.message);
    });
};

// Show the chat window after logging in
function showChat() {
    document.getElementById('login-form').style.display = "none";
    document.getElementById('register-form').style.display = "none";
    document.getElementById('chat-container').style.display = "flex";
}



// Logout button click event
document.getElementById('logout-button').onclick = () => {
    fetch('/logout', { method: 'POST' }).then(() => location.reload());
};



// Enter key event listeners
document.getElementById('login-password').addEventListener('keypress', function(event) {
    if (event.key === 'Enter') {
        event.preventDefault();
        document.getElementById('login-button').click();
    }
});

document.getElementById('register-password').addEventListener('keypress', function(event) {
    if (event.key === 'Enter') {
        event.preventDefault();
        document.getElementById('register-button').click();
    }
});

document.getElementById('user-input').addEventListener('keypress', function(event) {
    if (event.key === 'Enter') {
        event.preventDefault();
        document.getElementById('send-button').click();
    }
});

// Initialize the page
document.addEventListener('DOMContentLoaded', function() {
    fetch('/chat_page')
        .then(response => {
            if (response.redirected) {
                showLoginForm();
            } else {
                showChat();
                loadChatHistory();
            }
        })
        .catch(console.error);
});
// Function to create conversation history item
function createConversationItem(chat) {
    const item = document.createElement('div');
    item.className = 'chat-history-item';
    item.dataset.chatId = chat.chat_id;
    
    // Get chat title or use first user message as title
    const messages = Array.isArray(chat.messages) ? chat.messages : JSON.parse(chat.messages);
    const firstUserMessage = messages.find(msg => msg.role === 'user')?.content || 'New Chat';
    const title = chat.title || (firstUserMessage.length > 30 ? firstUserMessage.substring(0, 30) + '...' : firstUserMessage);
    
    // Format date
    const date = new Date(chat.created_at);
    const formattedDate = date.toLocaleDateString('en-US', {
        month: 'short',
        day: 'numeric',
        year: date.getFullYear() !== new Date().getFullYear() ? 'numeric' : undefined
    });
    
    // Create chat item content
    item.innerHTML = `
        <i class="fas fa-comment-medical"></i>
        <div class="chat-info">
            <span class="chat-title">${title}</span>
            <span class="chat-date">${formattedDate}</span>
        </div>
    `;
    
    // Add active class if this is the current chat
    if (currentSessionId === chat.chat_id) {
        item.classList.add('active');
    }
    
    // Add click handler to load the entire conversation
    item.onclick = () => loadConversation(chat);
    
    return item;
}

// Function to load a specific conversation
function loadConversation(chat) {
    currentSessionId = chat.chat_id;
    
    // Update active state in sidebar
    document.querySelectorAll('.chat-history-item').forEach(item => {
        item.classList.remove('active');
        if (item.dataset.chatId === chat.chat_id) {
            item.classList.add('active');
        }
    });
    
    const chatBox = document.getElementById('chat-box');
    chatBox.innerHTML = ''; // Clear current chat
    
    // Parse messages if they're stored as string
    const messages = Array.isArray(chat.messages) ? chat.messages : JSON.parse(chat.messages);
    
    // Display all messages in the conversation
    messages.forEach((message, index) => {
        if (message.role !== 'system') {
            const isUser = message.role === 'user';
            const messageElement = createMessageElement(
                message.content,
                isUser,
                !isUser ? 'msg-' + index : null
            );
            chatBox.appendChild(messageElement);
        }
    });
    
    // Scroll to bottom of chat
    chatBox.scrollTop = chatBox.scrollHeight;
}

// Updated chat message handling for maintaining conversation context
function handleChatMessage(message) {
    if (!currentSessionId) {
        // Create new chat session if none exists
        currentSessionId = 'chat-' + Date.now();
    }

    const chatBox = document.getElementById('chat-box');
    chatBox.appendChild(createMessageElement(message, true));

    fetch('/chat', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({
            message: message,
            chatId: currentSessionId
        })
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            // Add bot response to chat
            const botMsg = createMessageElement("", false, "msg-" + Date.now());
            chatBox.appendChild(botMsg);
            let index = 0;
            const interval = setInterval(() => {
                if (index < data.reply.length) {
                    botMsg.textContent += data.reply.charAt(index++);
                } else {
                    clearInterval(interval);
                }
            }, 20);

            chatBox.scrollTop = chatBox.scrollHeight;
            
            // Refresh sidebar only if starting a new session
            if (!data.isContinuedSession) {  // Assuming backend provides this flag for clarity
                loadChatHistory();
            }
        }
    })
    .catch(error => {
        console.error('Chat error:', error);
        chatBox.appendChild(createMessageElement(
            "Sorry, I'm having trouble connecting right now. Please try again later.",
            false
        ));
    });
}


// Updated loadChatHistory function
function loadChatHistory() {
    const sidebar = document.getElementById('chat-history-list');

    fetch('/get_chat_history')
        .then(response => response.json())
        .then(data => {
            if (data.success && Array.isArray(data.chat_history)) {
                sidebar.innerHTML = ''; // Clear existing items

                if (data.chat_history.length === 0) {
                    sidebar.innerHTML = '<div class="empty-history">No conversations yet</div>';
                    return;
                }

                // Create and append conversation items only for unique sessions
                data.chat_history.forEach(chat => {
                    const chatItem = createConversationItem(chat);
                    sidebar.appendChild(chatItem);
                });
            }
        })
        .catch(error => {
            console.error('Error loading chat history:', error);
            sidebar.innerHTML = '<div class="empty-history">Error loading history</div>';
        });
}

// Updated styling
const style = document.createElement('style');
style.textContent = `
    .chat-history-item {
        display: flex;
        align-items: center;
        padding: 12px 16px;
        margin: 4px 8px;
        border-radius: 8px;
        cursor: pointer;
        transition: all 0.2s ease;
        color: #e4e4e7;
    }
    
    .chat-history-item:hover {
        background-color: rgba(255, 255, 255, 0.1);
    }
    
    .chat-history-item.active {
        background-color: rgba(255, 255, 255, 0.15);
    }
    
    .chat-history-item i {
        font-size: 1.2em;
        margin-right: 12px;
        color: #a0aec0;
    }
    
    .chat-info {
        flex: 1;
        min-width: 0; /* Enables text truncation */
        display: flex;
        flex-direction: column;
    }
    
    .chat-title {
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
        font-size: 0.95em;
    }
    
    .chat-date {
        font-size: 0.8em;
        color: #a0aec0;
        margin-top: 2px;
    }
    
    .empty-history {
        text-align: center;
        padding: 20px;
        color: #a0aec0;
        font-size: 0.9em;
    }
    
    #chat-box {
        display: flex;
        flex-direction: column;
        gap: 16px;
        padding: 20px;
        overflow-y: auto;
    }
    
    .message {
        max-width: 80%;
        padding: 12px 16px;
        border-radius: 8px;
        position: relative;
        line-height: 1.5;
    }
    
    .message.user {
        background-color: #2563eb;
        color: white;
        align-self: flex-end;
    }
    
    .message.bot {
        background-color: #3f3f46;
        color: white;
        align-self: flex-start;
    }
    
    .message-time {
        font-size: 0.75em;
        color: rgba(255, 255, 255, 0.7);
        margin-top: 6px;
    }
`;
document.head.appendChild(style);

// Update the send button handler
document.getElementById('send-button').onclick = function() {
    const inputElement = document.getElementById('user-input');
    const message = inputElement.value.trim();
    
    if (!message) return;
    
    inputElement.value = '';
    handleChatMessage(message);
};

// Update new chat button handler
document.getElementById('new-chat').onclick = function() {
    fetch('/new_chat', {
        method: 'POST'
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            currentSessionId = null;
            document.getElementById('chat-box').innerHTML = `
                <div class="chat-welcome">
                    <h3>Welcome to Your Virtual Consultation</h3>
                    <p>Ask your medical questions and receive professional advice</p>
                </div>
            `;
            loadChatHistory();
        }
    })
    .catch(error => showErrorMessage("Error starting new chat"));
};














