/**
 * Tax Chatbot Widget - AI-powered tax assistant
 */

class TaxChatbot {
    constructor() {
        this.isOpen = false;
        this.topics = [];
        this.isLoading = false;
        this.init();
    }

    init() {
        this.createWidget();
        this.bindEvents();
        this.loadTopics();
        this.addWelcomeMessage();
    }

    createWidget() {
        const widget = document.createElement('div');
        widget.className = 'chatbot-widget';
        widget.id = 'taxChatbot';
        widget.innerHTML = `
            <button class="chatbot-toggle" id="chatbotToggle">
                <span>🤖</span>
                <div class="chatbot-badge" id="chatBadge">1</div>
            </button>
            <div class="chatbot-container" id="chatbotContainer">
                <div class="chatbot-header">
                    <div class="avatar">🤖</div>
                    <div class="info">
                        <h4>Tax Assistant</h4>
                        <p id="chatbotModeLabel">AI-powered help for tax queries</p>
                    </div>
                    <button class="close-btn" id="closeChatbot">&times;</button>
                </div>
                <div class="chatbot-messages" id="chatMessages">
                </div>
                <div class="quick-topics" id="quickTopics">
                    <h5>Quick Topics</h5>
                    <div class="topic-chips" id="topicChips">
                    </div>
                </div>
                <div class="chatbot-input">
                    <input type="text" id="chatInput" placeholder="Ask about tax deductions, regimes..." />
                    <button id="sendMessage">
                        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                            <line x1="22" y1="2" x2="11" y2="13"></line>
                            <polygon points="22 2 15 22 11 13 2 9 22 2"></polygon>
                        </svg>
                    </button>
                </div>
            </div>
        `;
        document.body.appendChild(widget);

        // Cache elements
        this.toggle = document.getElementById('chatbotToggle');
        this.container = document.getElementById('chatbotContainer');
        this.messages = document.getElementById('chatMessages');
        this.input = document.getElementById('chatInput');
        this.sendBtn = document.getElementById('sendMessage');
        this.topicChips = document.getElementById('topicChips');
        this.badge = document.getElementById('chatBadge');
        this.modeLabel = document.getElementById('chatbotModeLabel');
    }

    bindEvents() {
        this.toggle.addEventListener('click', () => this.toggleChat());
        document.getElementById('closeChatbot').addEventListener('click', () => this.closeChat());
        this.sendBtn.addEventListener('click', () => this.sendMessage());
        this.input.addEventListener('keypress', (e) => {
            if (e.key === 'Enter') this.sendMessage();
        });
    }

    toggleChat() {
        if (this.isOpen) {
            this.closeChat();
        } else {
            this.openChat();
        }
    }

    openChat() {
        this.isOpen = true;
        this.container.classList.add('open');
        this.toggle.classList.add('active');
        this.badge.classList.remove('show');
        this.input.focus();
    }

    closeChat() {
        this.isOpen = false;
        this.container.classList.remove('open');
        this.toggle.classList.remove('active');
    }

    async loadTopics() {
        try {
            const response = await API.ai.getChatTopics();
            this.topics = response.topics || [];
            this.renderTopics();
        } catch (error) {
            console.error('Failed to load topics:', error);
            // Use default topics
            this.topics = [
                { id: '80c', title: '80C Deductions', query: 'What is 80C?' },
                { id: '80d', title: '80D Health', query: 'What is 80D?' },
                { id: 'regime', title: 'Tax Regimes', query: 'New vs old regime' },
            ];
            this.renderTopics();
        }
    }

    renderTopics() {
        this.topicChips.innerHTML = this.topics.slice(0, 5).map(topic => 
            `<button class="topic-chip" data-query="${topic.query}">${topic.title}</button>`
        ).join('');

        // Bind topic click events
        this.topicChips.querySelectorAll('.topic-chip').forEach(chip => {
            chip.addEventListener('click', (e) => {
                const query = e.target.dataset.query;
                this.input.value = query;
                this.sendMessage();
            });
        });
    }

    addWelcomeMessage() {
        const welcomeMsg = `
            <div class="chat-message bot">
                <div>👋 Hi! I'm your Tax Assistant. I can help you with:</div>
                <ul style="margin: 8px 0 0 16px; padding: 0;">
                    <li>Tax deductions (80C, 80D, HRA)</li>
                    <li>Old vs New tax regime comparison</li>
                    <li>ITR filing guidance</li>
                    <li>Capital gains & other income</li>
                </ul>
                <div style="margin-top: 8px;">Ask me anything about Indian taxes! 🇮🇳</div>
            </div>
        `;
        this.messages.innerHTML = welcomeMsg;
    }

    addMessage(text, isUser = false, suggestions = []) {
        const messageDiv = document.createElement('div');
        messageDiv.className = `chat-message ${isUser ? 'user' : 'bot'}`;
        
        // Format text - convert **text** to bold
        let formattedText = text.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
        // Convert newlines to <br>
        formattedText = formattedText.replace(/\n/g, '<br>');
        
        messageDiv.innerHTML = `<div>${formattedText}</div>`;
        
        // Add suggestions if provided
        if (suggestions && suggestions.length > 0) {
            const suggestionsDiv = document.createElement('div');
            suggestionsDiv.className = 'suggestions';
            suggestions.forEach(suggestion => {
                const btn = document.createElement('button');
                btn.className = 'suggestion-btn';
                btn.textContent = suggestion;
                btn.addEventListener('click', () => {
                    this.input.value = suggestion;
                    this.sendMessage();
                });
                suggestionsDiv.appendChild(btn);
            });
            messageDiv.appendChild(suggestionsDiv);
        }
        
        this.messages.appendChild(messageDiv);
        this.scrollToBottom();
    }

    addTypingIndicator() {
        const typing = document.createElement('div');
        typing.className = 'typing-indicator';
        typing.id = 'typingIndicator';
        typing.innerHTML = '<span></span><span></span><span></span>';
        this.messages.appendChild(typing);
        this.scrollToBottom();
    }

    removeTypingIndicator() {
        const typing = document.getElementById('typingIndicator');
        if (typing) typing.remove();
    }

    scrollToBottom() {
        this.messages.scrollTop = this.messages.scrollHeight;
    }

    async sendMessage() {
        const text = this.input.value.trim();
        if (!text || this.isLoading) return;

        // Add user message
        this.addMessage(text, true);
        this.input.value = '';

        // Show typing indicator
        this.isLoading = true;
        this.sendBtn.disabled = true;
        this.addTypingIndicator();

        try {
            const response = await API.ai.chat(text);
            this.removeTypingIndicator();
            this.addMessage(response.message, false, response.suggestions);
            this.updateMode(response.mode);
        } catch (error) {
            this.removeTypingIndicator();
            this.addMessage('Sorry, I encountered an error. Please try again.', false);
            console.error('Chat error:', error);
        } finally {
            this.isLoading = false;
            this.sendBtn.disabled = false;
        }
    }

    // Show notification badge
    showNotification() {
        if (!this.isOpen) {
            this.badge.classList.add('show');
        }
    }

    updateMode(mode) {
        if (!this.modeLabel) return;
        if (mode === 'llm') {
            this.modeLabel.textContent = 'Live AI mode';
        } else if (mode === 'kb') {
            this.modeLabel.textContent = 'Knowledge mode (set OPENAI_API_KEY for Live AI)';
        }
    }
}

// Initialize chatbot when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    // Only initialize if user is logged in and not on auth pages
    const path = window.location.pathname;
    if (!path.includes('login') && !path.includes('register') && !path.includes('ca-review')) {
        // Check if API is available
        if (typeof API !== 'undefined') {
            window.taxChatbot = new TaxChatbot();
        }
    }
});
