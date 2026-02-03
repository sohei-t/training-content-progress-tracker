/**
 * WebSocket接続管理サービス
 * パフォーマンス最適化: 自動再接続、exponential backoff、メッセージキュー
 */

class WebSocketService {
    constructor(url = null) {
        this.url = url || `ws://${window.location.host}/ws`;
        this.ws = null;
        this.isConnected = false;
        this.reconnectAttempts = 0;
        this.maxReconnectAttempts = 5;
        this.baseReconnectDelay = 1000; // 1秒
        this.maxReconnectDelay = 30000; // 30秒
        this.handlers = new Map();
        this.messageQueue = [];
        this.pingInterval = null;
        this.pingTimeout = null;
    }

    /**
     * WebSocket接続を確立
     */
    connect() {
        if (this.ws && this.ws.readyState === WebSocket.OPEN) {
            console.log('WebSocket already connected');
            return;
        }

        try {
            this.ws = new WebSocket(this.url);

            this.ws.onopen = () => {
                console.log('WebSocket connected');
                this.isConnected = true;
                this.reconnectAttempts = 0;
                this.emit('connected');

                // 接続中に溜まったメッセージを送信
                this.flushMessageQueue();

                // Pingインターバル開始
                this.startPing();
            };

            this.ws.onmessage = (event) => {
                try {
                    const message = JSON.parse(event.data);
                    const { event: eventType, data, timestamp } = message;

                    // console.log('WebSocket message:', eventType, data);
                    this.emit(eventType, data, timestamp);
                } catch (error) {
                    console.error('WebSocket message parse error:', error);
                }
            };

            this.ws.onclose = (event) => {
                console.log('WebSocket disconnected:', event.code, event.reason);
                this.isConnected = false;
                this.stopPing();
                this.emit('disconnected', { code: event.code, reason: event.reason });

                // 自動再接続
                if (event.code !== 1000) { // 正常終了以外
                    this.attemptReconnect();
                }
            };

            this.ws.onerror = (error) => {
                console.error('WebSocket error:', error);
                this.emit('error', { error });
            };

        } catch (error) {
            console.error('WebSocket connection error:', error);
            this.attemptReconnect();
        }
    }

    /**
     * 再接続を試行（exponential backoff）
     */
    attemptReconnect() {
        if (this.reconnectAttempts >= this.maxReconnectAttempts) {
            console.log('Max reconnect attempts reached');
            this.emit('maxReconnectAttemptsReached');
            return;
        }

        this.reconnectAttempts++;
        const delay = Math.min(
            this.baseReconnectDelay * Math.pow(2, this.reconnectAttempts - 1),
            this.maxReconnectDelay
        );

        console.log(`Reconnecting in ${delay}ms (attempt ${this.reconnectAttempts}/${this.maxReconnectAttempts})`);
        this.emit('reconnecting', { attempt: this.reconnectAttempts, delay });

        setTimeout(() => {
            this.connect();
        }, delay);
    }

    /**
     * 接続を切断
     */
    disconnect() {
        this.stopPing();

        if (this.ws) {
            this.ws.close(1000, 'Client disconnect');
            this.ws = null;
        }

        this.isConnected = false;
    }

    /**
     * メッセージ送信
     */
    send(message) {
        if (this.isConnected && this.ws && this.ws.readyState === WebSocket.OPEN) {
            this.ws.send(typeof message === 'string' ? message : JSON.stringify(message));
        } else {
            // 接続中はキューに追加
            this.messageQueue.push(message);
        }
    }

    /**
     * メッセージキューをフラッシュ
     */
    flushMessageQueue() {
        while (this.messageQueue.length > 0) {
            const message = this.messageQueue.shift();
            this.send(message);
        }
    }

    /**
     * Pingを開始（接続維持）
     */
    startPing() {
        this.stopPing();

        this.pingInterval = setInterval(() => {
            if (this.isConnected) {
                this.send('ping');

                // Pongタイムアウト
                this.pingTimeout = setTimeout(() => {
                    console.log('Ping timeout, reconnecting...');
                    this.ws.close();
                }, 5000);
            }
        }, 30000); // 30秒間隔
    }

    /**
     * Pingを停止
     */
    stopPing() {
        if (this.pingInterval) {
            clearInterval(this.pingInterval);
            this.pingInterval = null;
        }
        if (this.pingTimeout) {
            clearTimeout(this.pingTimeout);
            this.pingTimeout = null;
        }
    }

    /**
     * イベントハンドラー登録
     */
    on(event, handler) {
        if (!this.handlers.has(event)) {
            this.handlers.set(event, new Set());
        }
        this.handlers.get(event).add(handler);
        return () => this.off(event, handler); // unsubscribe関数を返す
    }

    /**
     * イベントハンドラー解除
     */
    off(event, handler) {
        if (this.handlers.has(event)) {
            this.handlers.get(event).delete(handler);
        }
    }

    /**
     * イベント発火
     */
    emit(event, data, timestamp) {
        // pongレスポンス処理
        if (event === 'pong') {
            if (this.pingTimeout) {
                clearTimeout(this.pingTimeout);
                this.pingTimeout = null;
            }
            return;
        }

        const handlers = this.handlers.get(event);
        if (handlers) {
            handlers.forEach(handler => {
                try {
                    handler(data, timestamp);
                } catch (error) {
                    console.error(`WebSocket handler error for ${event}:`, error);
                }
            });
        }
    }

    /**
     * 接続状態を取得
     */
    getConnectionState() {
        if (!this.ws) return 'CLOSED';

        switch (this.ws.readyState) {
            case WebSocket.CONNECTING: return 'CONNECTING';
            case WebSocket.OPEN: return 'OPEN';
            case WebSocket.CLOSING: return 'CLOSING';
            case WebSocket.CLOSED: return 'CLOSED';
            default: return 'UNKNOWN';
        }
    }
}

// シングルトンインスタンス
const wsService = new WebSocketService();

// グローバルエクスポート
window.wsService = wsService;
window.WebSocketService = WebSocketService;
