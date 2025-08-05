let conversationHistory = [];
let mealPlan: any = null;

export function renderChatbot(container: HTMLElement, onNewPlan: (plan: any) => void) {
    container.innerHTML = `
        <div id="chatbot-header">Chat with Duke Eats</div>
        <div id="chatbot-container">
            <div id="chatbot-messages"></div>
            <div id="chatbot-input-container">
                <input type="text" id="chatbot-input" placeholder="Refine your meal plan...">
                <button id="chatbot-send">Send</button>
            </div>
        </div>
    `;

    const header = document.getElementById('chatbot-header');
    const input = document.getElementById('chatbot-input') as HTMLInputElement;
    const chatbotContainer = document.getElementById('chatbot'); // The parent div

    const setPlan = (newPlan: any) => {
        mealPlan = newPlan;
    };

    const toggleChatbot = () => {
        if (chatbotContainer) {
            chatbotContainer.classList.toggle('collapsed');
        }
    };
    
    if (header) {
        header.addEventListener('click', toggleChatbot);
    }
    
    // Start collapsed
    if (chatbotContainer && !chatbotContainer.classList.contains('collapsed')) {
        chatbotContainer.classList.add('collapsed');
    }

    const sendButton = document.getElementById('chatbot-send');
    
    const sendMessage = async () => {
        const message = input.value.trim();
        if (message) {
            displayUserMessage(message);
            input.value = '';
            displayBotMessage("Thinking...", true); // Show loading indicator

            try {
                // Direct communication with the AI agent
                const chatRequest = {
                    message: message,
                    currentPlan: mealPlan, // Include the current plan for context
                };

                const response = await fetch('http://localhost:3000/api/chat', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify(chatRequest),
                });

                if (!response.ok) {
                    const errorData = await response.text();
                    throw new Error(`Backend server error: ${response.status} ${errorData}`);
                }

                const responseData = await response.json();
                
                if (responseData.success && responseData.response) {
                    updateLastBotMessage(responseData.response);
                } else {
                    updateLastBotMessage("I'm sorry, I couldn't process your request. Please try again.");
                }

            } catch (error) {
                console.error("Error communicating with agent:", error);
                let errorMessage = "Sorry, I'm having trouble connecting to the AI assistant.";
                if (error instanceof Error) {
                    errorMessage += ` Please try again.`;
                }
                updateLastBotMessage(errorMessage);
            }
        }
    };

    if (sendButton) {
        sendButton.addEventListener('click', sendMessage);
    }

    input.addEventListener('keypress', (e) => {
        if (e.key === 'Enter') {
            sendMessage();
        }
    });
}

function displayUserMessage(message: string) {
    const messagesContainer = document.getElementById('chatbot-messages');
    if (messagesContainer) {
        const userMessageDiv = document.createElement('div');
        userMessageDiv.className = 'message user-message';
        userMessageDiv.textContent = message;
        messagesContainer.appendChild(userMessageDiv);
        // Ensure smooth scrolling to bottom
        setTimeout(() => {
            messagesContainer.scrollTop = messagesContainer.scrollHeight;
        }, 10);
    }
}

function displayBotMessage(message: string, isLoading: boolean = false) {
    const messagesContainer = document.getElementById('chatbot-messages');
    if (messagesContainer) {
        const botMessageDiv = document.createElement('div');
        botMessageDiv.className = 'message bot-message';
        if (isLoading) {
            botMessageDiv.innerHTML = `${message} <span class="loading-indicator"><span>.</span><span>.</span><span>.</span></span>`;
        } else {
            botMessageDiv.innerHTML = formatResponse(message);
        }
        messagesContainer.appendChild(botMessageDiv);
        // Ensure smooth scrolling to bottom
        setTimeout(() => {
            messagesContainer.scrollTop = messagesContainer.scrollHeight;
        }, 10);
    }
}

function updateLastBotMessage(htmlContent: string) {
    const messagesContainer = document.getElementById('chatbot-messages');
    if (messagesContainer) {
        const lastMessage = messagesContainer.querySelector('.bot-message:last-child');
        if (lastMessage) {
            lastMessage.innerHTML = formatResponse(htmlContent);
            // Ensure smooth scrolling to bottom
            setTimeout(() => {
                messagesContainer.scrollTop = messagesContainer.scrollHeight;
            }, 10);
        }
    }
}

function formatResponse(text: string): string {
    // Convert newlines to <br> and bold meal headers
    return text
        .replace(/\n/g, '<br>')
        .replace(/(Breakfast|Lunch|Dinner|Snacks) —/g, '<strong>$1 —</strong>');
}