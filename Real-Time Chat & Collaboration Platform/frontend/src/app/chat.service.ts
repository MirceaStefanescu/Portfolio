import { Injectable, OnDestroy } from "@angular/core";
import { HttpClient } from "@angular/common/http";
import { BehaviorSubject, firstValueFrom, Observable, Subject, switchMap } from "rxjs";
import { Client, StompSubscription } from "@stomp/stompjs";
import SockJS from "sockjs-client";
import { environment } from "../environments/environment";
import { ChatMessage, ChatRoom, PresenceMember } from "./models";

interface CsrfToken { headerName: string; token: string; }

@Injectable({
  providedIn: "root"
})
export class ChatService implements OnDestroy {
  private client?: Client;
  private roomSubscription?: StompSubscription;
  private currentRoomId?: string;
  private presenceSubscription?: StompSubscription;
  private receiptSubscription?: StompSubscription;
  private heartbeat?: ReturnType<typeof setInterval>;
  private presenceClock?: ReturnType<typeof setInterval>;
  private displayName = "anonymous";
  private lastTyping = 0;
  private members: PresenceMember[] = [];
  private readonly pending = new Map<string, {roomId: string; sender: string | null; content: string}>();
  private readonly presenceSubject = new BehaviorSubject<PresenceMember[]>([]);
  private readonly errorsSubject = new Subject<{content: string; error: string}>();
  private readonly savedSubject = new Subject<string>();
  readonly saved$ = this.savedSubject.asObservable();
  readonly presence$ = this.presenceSubject.asObservable();
  readonly errors$ = this.errorsSubject.asObservable();

  private readonly messagesSubject = new Subject<ChatMessage>();
  private readonly connectedSubject = new BehaviorSubject<boolean>(false);

  readonly messages$ = this.messagesSubject.asObservable();
  readonly connected$ = this.connectedSubject.asObservable();

  constructor(private http: HttpClient) {}

  connect(): void {
    if (this.client?.active) {
      return;
    }

    this.client = new Client({
      webSocketFactory: () => new SockJS(`${environment.wsBaseUrl}/ws`),
      reconnectDelay: 3000,
      heartbeatIncoming: 10000,
      heartbeatOutgoing: 10000,
      debug: environment.production ? () => {} : (message) => console.log(message)
    });

    const client = this.client;
    client.beforeConnect = async () => {
      try {
        const csrf = await firstValueFrom(this.csrfToken());
        client.connectHeaders = { [csrf.headerName]: csrf.token };
      } catch {
        if (this.client === client) this.connectedSubject.next(false);
        await client.deactivate();
      }
    };

    this.client.onConnect = () => {
      if (this.client !== client) return;
      this.receiptSubscription = client.subscribe("/user/queue/receipts", (message) => {
        const receipt = JSON.parse(message.body);
        const pending = this.pending.get(receipt.requestId);
        if (pending) {
          this.pending.delete(receipt.requestId);
          if (!receipt.accepted) this.errorsSubject.next({content: pending.content, error: receipt.error});
          else this.savedSubject.next(pending.roomId);
        }
      });
      this.connectedSubject.next(true);
      if (this.currentRoomId) {
        this.subscribeToRoom(this.currentRoomId);
      }
      for (const [requestId, pending] of this.pending) {
        try { this.publishPending(requestId, pending); }
        catch { this.connectedSubject.next(false); break; }
      }
    };

    this.client.onWebSocketClose = () => {
      if (this.client !== client) return;
      this.roomSubscription = undefined;
      this.presenceSubscription = undefined;
      this.receiptSubscription = undefined;
      this.clearPresenceTimers();
      this.presenceSubject.next([]);
      this.connectedSubject.next(false);
    };

    this.client.onDisconnect = () => {
      if (this.client !== client) return;
      this.connectedSubject.next(false);
    };

    this.client.activate();
  }

  disconnect(): void {
    if (this.client?.connected) {
      this.activity(false, true);
      this.roomSubscription?.unsubscribe();
      this.presenceSubscription?.unsubscribe();
      this.receiptSubscription?.unsubscribe();
    }
    this.roomSubscription = undefined;
    this.presenceSubscription = undefined;
    this.receiptSubscription = undefined;
    this.clearPresenceTimers();
    this.presenceSubject.next([]);
    void this.client?.deactivate();
    this.connectedSubject.next(false);
  }

  subscribeToRoom(roomId: string): void {
    if (this.currentRoomId && this.currentRoomId !== roomId) this.activity(false, true);
    this.currentRoomId = roomId;
    this.members = [];
    this.presenceSubject.next([]);

    if (!this.client || !this.client.connected) {
      return;
    }

    this.roomSubscription?.unsubscribe();
    this.presenceSubscription?.unsubscribe();
    this.clearPresenceTimers();
    this.roomSubscription = this.client.subscribe(`/topic/rooms/${roomId}`, (message) => {
      const payload = JSON.parse(message.body) as ChatMessage;
      this.messagesSubject.next(payload);
    });
    this.presenceSubscription = this.client.subscribe(`/topic/rooms/${roomId}/presence`, (message) => {
      const snapshot = JSON.parse(message.body);
      const offset = Date.now() - snapshot.serverTime;
      this.members = snapshot.members.map((member: PresenceMember) => ({...member,
        expiresAt: member.expiresAt + offset, typingUntil: member.typingUntil ? member.typingUntil + offset : 0}));
      this.emitPresence();
    });
    this.activity(false);
    this.heartbeat = setInterval(() => this.activity(false), 15000);
    this.presenceClock = setInterval(() => this.emitPresence(), 1000);
  }

  sendMessage(roomId: string, sender: string | null, content: string): boolean {
    if (!this.client || !this.client.connected) {
      return false;
    }

    const requestId = crypto.randomUUID();
    try {
      const pending = {roomId, sender, content};
      this.pending.set(requestId, pending);
      this.publishPending(requestId, pending);
      return true;
    } catch {
      this.pending.delete(requestId);
      this.connectedSubject.next(false);
      return false;
    }
  }

  private publishPending(requestId: string, pending: {roomId: string; sender: string | null; content: string}): void {
    this.client!.publish({destination: `/app/rooms/${pending.roomId}/send`,
      body: JSON.stringify({sender: pending.sender, content: pending.content, requestId})});
  }

  setDisplayName(name: string): void { this.displayName = name; this.activity(false); }
  notifyTyping(): void {
    if (Date.now() - this.lastTyping >= 1000) { this.lastTyping = Date.now(); this.activity(true); }
  }
  private activity(typing: boolean, leave = false): void {
    if (!this.client?.connected || !this.currentRoomId) return;
    try {
      this.client.publish({destination: `/app/rooms/${this.currentRoomId}/presence`,
        body: JSON.stringify({sender: this.displayName, typing, leave})});
    } catch { this.connectedSubject.next(false); }
  }
  private emitPresence(): void {
    const now = Date.now();
    this.presenceSubject.next(this.members.filter((member) => member.expiresAt > now)
      .map((member) => ({...member, typingUntil: member.typingUntil > now ? member.typingUntil : 0})));
  }
  private clearPresenceTimers(): void {
    if (this.heartbeat) clearInterval(this.heartbeat);
    if (this.presenceClock) clearInterval(this.presenceClock);
    this.heartbeat = undefined; this.presenceClock = undefined;
  }

  listRooms(): Observable<ChatRoom[]> {
    return this.http.get<ChatRoom[]>(`${environment.apiBaseUrl}/api/rooms`, {
      withCredentials: true
    });
  }

  createRoom(name: string): Observable<ChatRoom> {
    return this.csrfToken().pipe(
      switchMap((csrf) => this.http.post<ChatRoom>(
        `${environment.apiBaseUrl}/api/rooms`,
        { name },
        { withCredentials: true, headers: { [csrf.headerName]: csrf.token } }
      ))
    );
  }

  private csrfToken(): Observable<CsrfToken> {
    return this.http.get<CsrfToken>(`${environment.apiBaseUrl}/api/csrf`, {
      withCredentials: true
    });
  }

  getMessages(roomId: string, limit = 50, query = ""): Observable<ChatMessage[]> {
    return this.http.get<ChatMessage[]>(
      `${environment.apiBaseUrl}/api/rooms/${roomId}/messages`,
      {
        params: { limit, query },
        withCredentials: true
      }
    );
  }

  ngOnDestroy(): void {
    this.disconnect();
  }
}
