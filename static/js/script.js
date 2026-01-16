document.addEventListener('DOMContentLoaded', () => {
    const chatForm = document.getElementById('chat-form');
    const userInput = document.getElementById('user-input');
    const chatMessages = document.getElementById('chat-messages');

    // Auto-scroll to bottom
    function scrollToBottom() {
        chatMessages.scrollTop = chatMessages.scrollHeight;
    }

    // Add User Message
    function addUserMessage(message) {
        const div = document.createElement('div');
        div.className = 'message user-message';
        div.innerHTML = `
            <div class="message-content">${message}</div>
            <div class="avatar"><i class="fa-solid fa-user"></i></div>
        `;
        chatMessages.appendChild(div);
        scrollToBottom();
    }

    // Add Bot Message
    function addBotMessage(message) {
        const div = document.createElement('div');
        div.className = 'message bot-message';
        div.innerHTML = `
            <div class="avatar"><i class="fa-solid fa-robot"></i></div>
            <div class="message-content">${message}</div>
        `;
        chatMessages.appendChild(div);
        scrollToBottom();
    }

    // Show Typing Indicator
    function showTypingIndicator() {
        const div = document.createElement('div');
        div.className = 'typing-indicator';
        div.id = 'typing-indicator';
        div.innerHTML = `
            <div class="dot"></div>
            <div class="dot"></div>
            <div class="dot"></div>
        `;
        chatMessages.appendChild(div);
        div.style.display = 'flex';
        scrollToBottom();
    }

    // Remove Typing Indicator
    function removeTypingIndicator() {
        const indicator = document.getElementById('typing-indicator');
        if (indicator) {
            indicator.remove();
        }
    }

    // Handle Form Submit
    chatForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        const message = userInput.value.trim();
        if (!message) return;

        // 1. Show user message
        addUserMessage(message);
        userInput.value = '';

        // 2. Show typing indicator
        showTypingIndicator();

        try {
            // 3. Call Backend
            const response = await fetch('/chat', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ message: message })
            });

            const data = await response.json();

            // 4. Remove typing indicator and show bot response
            // Simulate a small delay for realism
            setTimeout(() => {
                removeTypingIndicator();
                addBotMessage(data.response);
            }, 600);

        } catch (error) {
            removeTypingIndicator();
            addBotMessage("Sorry, I'm having trouble connecting to the server.");
            console.error('Error:', error);
        }
    });
});
