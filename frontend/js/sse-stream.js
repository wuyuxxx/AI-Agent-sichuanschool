/**
 * SSE 流式事件处理器
 * 处理后端 Server-Sent Events 并渲染到聊天界面
 */

class SSEStream {
    constructor(url = '/api/v1/chat') {
        this.url = url;
        this.abortController = null;
    }

    /**
     * 发送消息并流式处理回复
     * @param {string} sessionId
     * @param {string} message
     * @param {object} callbacks - { onStatus, onChunk, onCrisis, onDone, onError }
     * @returns {Promise<string>} 完整回复文本
     */
    async send(sessionId, message, callbacks = {}) {
        this.abortController = new AbortController();

        const response = await fetch(this.url, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ session_id: sessionId, message }),
            signal: this.abortController.signal,
        });

        if (!response.ok) {
            throw new Error(`HTTP ${response.status}: ${response.statusText}`);
        }

        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let buffer = '';
        let fullText = '';

        try {
            while (true) {
                const { done, value } = await reader.read();
                if (done) break;

                buffer += decoder.decode(value, { stream: true });
                const lines = buffer.split('\n');
                buffer = lines.pop() || ''; // 保留不完整的行

                for (const line of lines) {
                    if (!line.startsWith('data: ')) continue;
                    const dataStr = line.slice(6).trim();
                    if (!dataStr) continue;

                    try {
                        const data = JSON.parse(dataStr);
                        switch (data.type) {
                            case 'status':
                                callbacks.onStatus?.(data.content);
                                break;
                            case 'intent':
                                // 静默忽略，不显示后端状态
                                break;
                            case 'chunk':
                                fullText += data.content;
                                callbacks.onChunk?.(data.content);
                                break;
                            case 'crisis':
                                fullText = data.content;
                                callbacks.onCrisis?.(data.content);
                                break;
                            case 'error':
                                callbacks.onError?.(data.content);
                                break;
                            case 'done':
                                callbacks.onDone?.(fullText);
                                break;
                        }
                    } catch (e) {
                        // 跳过非 JSON 行
                    }
                }
            }
        } catch (err) {
            if (err.name !== 'AbortError') {
                callbacks.onError?.(err.message);
                throw err;
            }
        }

        return fullText;
    }

    abort() {
        this.abortController?.abort();
    }
}
