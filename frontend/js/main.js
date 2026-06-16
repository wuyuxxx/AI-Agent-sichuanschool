/**
 * NEURAL CAMPUS — 主应用逻辑
 * 聊天界面交互 · 会话管理 · 快捷操作
 */

(function () {
    'use strict';

    // ================================================================
    // DOM 引用
    // ================================================================
    const chatMessages = document.getElementById('chat-messages');
    const chatInput = document.getElementById('chat-input');
    const sendBtn = document.getElementById('send-btn');
    const crisisOverlay = document.getElementById('crisis-overlay');
    const crisisText = document.getElementById('crisis-text');
    const crisisCloseBtn = document.getElementById('crisis-close-btn');
    const resetBtn = document.getElementById('reset-chat-btn');

    // ================================================================
    // 状态
    // ================================================================
    const STORAGE_KEY = 'campus_agent_session';
    let sessionId = localStorage.getItem(STORAGE_KEY);
    if (!sessionId) {
        sessionId = 'session_' + Date.now() + '_' + Math.random().toString(36).slice(2, 8);
        localStorage.setItem(STORAGE_KEY, sessionId);
    }

    let isProcessing = false;
    let currentStream = null;
    let assistantMsgElem = null;

    // ================================================================
    // 初始化动画
    // ================================================================
    let cleanupAnim = null;
    if (typeof initAnimations === 'function') {
        cleanupAnim = initAnimations();
    }

    // ================================================================
    // 加载历史会话
    // ================================================================
    async function loadSessionHistory() {
        try {
            const resp = await fetch(`/api/v1/history/${sessionId}`);
            if (!resp.ok) return;
            const data = await resp.json();
            const history = data.history || [];
            if (history.length > 0) {
                chatMessages.innerHTML = '';
                for (const msg of history) {
                    if (msg.role === 'user') {
                        const div = document.createElement('div');
                        div.className = 'message user';
                        div.innerHTML = `
                            <div class="msg-avatar">U</div>
                            <div class="msg-content"><p>${escapeHtml(msg.content)}</p></div>
                        `;
                        chatMessages.appendChild(div);
                    } else if (msg.role === 'assistant') {
                        const div = document.createElement('div');
                        div.className = 'message assistant';
                        div.innerHTML = `
                            <div class="msg-avatar">AI</div>
                            <div class="msg-content"><p>${escapeHtml(msg.content)}</p></div>
                        `;
                        chatMessages.appendChild(div);
                    }
                }
                scrollToBottom();
            }
        } catch (err) {
            // silent
        }
    }
    loadSessionHistory();

    // ================================================================
    // 工具函数
    // ================================================================
    function autoResize(textarea) {
        textarea.style.height = 'auto';
        textarea.style.height = Math.min(textarea.scrollHeight, 120) + 'px';
    }

    function scrollToBottom() {
        if (typeof smoothScrollToBottom === 'function') {
            smoothScrollToBottom();
        } else {
            chatMessages.scrollTop = chatMessages.scrollHeight;
        }
    }

    // ================================================================
    // 消息渲染
    // ================================================================
    function addUserMessage(text) {
        const div = document.createElement('div');
        div.className = 'message user';
        div.innerHTML = `
            <div class="msg-avatar">U</div>
            <div class="msg-content"><p>${escapeHtml(text)}</p></div>
        `;
        chatMessages.appendChild(div);
        if (typeof animateMessageIn === 'function') animateMessageIn(div);
        scrollToBottom();
    }

    function createAssistantMessage() {
        const div = document.createElement('div');
        div.className = 'message assistant';
        div.innerHTML = `
            <div class="msg-avatar">AI</div>
            <div class="msg-content" id="assistant-msg"></div>
        `;
        chatMessages.appendChild(div);
        if (typeof animateMessageIn === 'function') animateMessageIn(div);
        assistantMsgElem = div.querySelector('.msg-content');
        scrollToBottom();
        return assistantMsgElem;
    }

    function appendToAssistant(text) {
        if (!assistantMsgElem) return;
        const statusEl = assistantMsgElem.querySelector('.msg-status');
        if (statusEl) statusEl.remove();
        assistantMsgElem.innerHTML += escapeHtml(text);
        scrollToBottom();
    }

    function setAssistantStatus(text) {
        if (!assistantMsgElem) createAssistantMessage();
        let statusEl = assistantMsgElem.querySelector('.msg-status');
        if (!statusEl) {
            statusEl = document.createElement('div');
            statusEl.className = 'msg-status';
            assistantMsgElem.appendChild(statusEl);
        }
        statusEl.textContent = text;
        scrollToBottom();
    }

    function escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    // ================================================================
    // 危机拦截
    // ================================================================
    function handleCrisis(text) {
        crisisText.textContent = text;
        crisisOverlay.classList.remove('hidden');
        chatInput.disabled = true;
        sendBtn.disabled = true;
    }

    crisisCloseBtn.addEventListener('click', () => {
        crisisOverlay.classList.add('hidden');
        chatInput.disabled = false;
        updateSendButton();
        chatInput.focus();
    });

    // ================================================================
    // 重置会话
    // ================================================================
    resetBtn.addEventListener('click', async () => {
        if (isProcessing) return;
        // 生成新会话
        sessionId = 'session_' + Date.now() + '_' + Math.random().toString(36).slice(2, 8);
        localStorage.setItem(STORAGE_KEY, sessionId);
        // 清空聊天
        chatMessages.innerHTML = `
            <div class="message assistant">
                <div class="msg-avatar">AI</div>
                <div class="msg-content">
                    <p>会话已重置。你好，有什么可以帮你？</p>
                </div>
            </div>
        `;
        // 重置欢迎消息动画
        requestAnimationFrame(() => {
            if (typeof animateWelcomeMessage === 'function') animateWelcomeMessage();
        });
    });

    // ================================================================
    // 发送逻辑
    // ================================================================
    function updateSendButton() {
        const hasText = chatInput.value.trim().length > 0;
        sendBtn.disabled = !hasText || isProcessing || chatInput.disabled;
    }

    async function sendMessage() {
        const text = chatInput.value.trim();
        if (!text || isProcessing) return;

        isProcessing = true;
        sendBtn.disabled = true;
        chatInput.disabled = true;

        // 显示用户消息
        addUserMessage(text);
        chatInput.value = '';
        autoResize(chatInput);

        // 创建助手消息容器
        createAssistantMessage();
        let typingIndicator = null;
        if (typeof showTypingIndicator === 'function') {
            typingIndicator = showTypingIndicator(assistantMsgElem);
        }

        currentStream = new SSEStream('/api/v1/chat');

        try {
            await currentStream.send(sessionId, text, {
                onChunk: (chunk) => {
                    if (typingIndicator) {
                        hideTypingIndicator(typingIndicator);
                        typingIndicator = null;
                    }
                    appendToAssistant(chunk);
                },
                onCrisis: (text) => {
                    if (typingIndicator) {
                        hideTypingIndicator(typingIndicator);
                        typingIndicator = null;
                    }
                    handleCrisis(text);
                },
                onError: (err) => {
                    if (typingIndicator) {
                        hideTypingIndicator(typingIndicator);
                        typingIndicator = null;
                    }
                    setAssistantStatus('⚠ ' + err);
                },
                onDone: () => {
                    const statusEl = assistantMsgElem?.querySelector('.msg-status');
                    if (statusEl) statusEl.remove();
                },
            });
        } catch (err) {
            if (typingIndicator) {
                hideTypingIndicator(typingIndicator);
                typingIndicator = null;
            }
            setAssistantStatus('⚠ 网络错误，请稍后重试');
        } finally {
            isProcessing = false;
            currentStream = null;
            const wasCrisis = !crisisOverlay.classList.contains('hidden');
            chatInput.disabled = wasCrisis;
            updateSendButton();
            if (!wasCrisis) chatInput.focus();
        }
    }

    // ================================================================
    // 事件绑定
    // ================================================================
    chatInput.addEventListener('input', () => {
        autoResize(chatInput);
        updateSendButton();
    });

    chatInput.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            sendMessage();
        }
    });

    sendBtn.addEventListener('click', sendMessage);

    // ================================================================
    // 页面关闭清理
    // ================================================================
    window.addEventListener('beforeunload', () => {
        if (currentStream) currentStream.abort();
        if (cleanupAnim) cleanupAnim();
    });
})();
