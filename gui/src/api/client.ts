export type RpcParams = Record<string, unknown>;
export type Notification = { method: string; params: any };
export class RpcError extends Error {
  constructor(public code: number, message: string, public data?: { code: string; hint: string; details: any }) { super(message); }
}
/** What the store needs from a backend: the local server (RpcClient) or the in-browser demo (src/demo). */
export interface Transport {
  subscribe(callback: (n: Notification) => void): () => void;
  onConnection(callback: (connected: boolean) => void): () => void;
  connect(): void;
  call<T = any>(method: string, params?: RpcParams): Promise<T>;
  close(): void;
}
export class RpcClient implements Transport {
  private socket?: WebSocket;
  private nextId = 0;
  private pending = new Map<number, { resolve: (v: any) => void; reject: (e: Error) => void; timer: ReturnType<typeof setTimeout> }>();
  private listeners = new Set<(n: Notification) => void>();
  private connections = new Set<(connected: boolean) => void>();
  private stopped = false;
  private retries = 0;
  private reconnect?: ReturnType<typeof setTimeout>;
  constructor(private token: string, private url = `${location.protocol === 'https:' ? 'wss:' : 'ws:'}//${location.host}/ws`) {}
  subscribe(callback: (n: Notification) => void) { this.listeners.add(callback); return () => { this.listeners.delete(callback); }; }
  onConnection(callback: (v: boolean) => void) { this.connections.add(callback); return () => { this.connections.delete(callback); }; }
  connect() {
    if (this.stopped) return;
    const socket = this.socket = new WebSocket(this.url, ['cybersprite', this.token]);
    socket.onopen = () => { this.retries = 0; this.connections.forEach(fn => fn(true)); };
    socket.onmessage = event => {
      const message = JSON.parse(event.data);
      if (message.method) this.listeners.forEach(fn => fn(message));
      else {
        const pending = this.pending.get(message.id);
        if (!pending) return;
        this.pending.delete(message.id); clearTimeout(pending.timer);
        if (message.error) pending.reject(new RpcError(message.error.code, message.error.message, message.error.data));
        else pending.resolve(message.result);
      }
    };
    socket.onclose = () => {
      this.connections.forEach(fn => fn(false));
      // Mutations are never silently replayed: the server may have committed.
      for (const p of this.pending.values()) { clearTimeout(p.timer); p.reject(new Error('Connection lost. Reload state before retrying the operation.')); }
      this.pending.clear();
      if (!this.stopped) this.reconnect = setTimeout(() => this.connect(), Math.min(250 * 2 ** this.retries++, 5000));
    };
  }
  call<T = any>(method: string, params: RpcParams = {}): Promise<T> {
    if (this.socket?.readyState !== WebSocket.OPEN) return Promise.reject(new Error('Server disconnected. Wait for reconnection.'));
    const id = ++this.nextId;
    return new Promise((resolve, reject) => {
      const timer = setTimeout(() => { this.pending.delete(id); reject(new Error('Request timed out. Reload state before retrying.')); }, 120000);
      this.pending.set(id, { resolve, reject, timer });
      this.socket!.send(JSON.stringify({ jsonrpc: '2.0', id, method, params }));
    });
  }
  close() { this.stopped = true; clearTimeout(this.reconnect); this.socket?.close(); }
}
