import { Injectable, OnDestroy } from "@angular/core";
import { HttpClient } from "@angular/common/http";
import { BehaviorSubject, Observable, Subject } from "rxjs";
import { Client, StompSubscription } from "@stomp/stompjs";
import SockJS from "sockjs-client";
import { environment } from "../environments/environment";
import { ChatMessage, ChatRoom } from "./models";

@Injectable({
  providedIn: "root"
})
export class ChatService implements OnDestroy {
  private client?: Client;
  private roomSubscription?: StompSubscription;
  private currentRoomId?: string;

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

    this.client.onConnect = () => {
      this.connectedSubject.next(true);
      if (this.currentRoomId) {
        this.subscribeToRoom(this.currentRoomId);
      }
    };

    this.client.onWebSocketClose = () => {
      this.roomSubscription = undefined;
      this.connectedSubject.next(false);
    };

    this.client.onDisconnect = () => {
      this.connectedSubject.next(false);
    };

    this.client.activate();
  }

  disconnect(): void {
    if (this.client?.connected) this.roomSubscription?.unsubscribe();
    this.roomSubscription = undefined;
    void this.client?.deactivate();
    this.connectedSubject.next(false);
  }

  subscribeToRoom(roomId: string): void {
    this.currentRoomId = roomId;

    if (!this.client || !this.client.connected) {
      return;
    }

    this.roomSubscription?.unsubscribe();
    this.roomSubscription = this.client.subscribe(`/topic/rooms/${roomId}`, (message) => {
      const payload = JSON.parse(message.body) as ChatMessage;
      this.messagesSubject.next(payload);
    });
  }

  sendMessage(roomId: string, sender: string | null, content: string): boolean {
    if (!this.client || !this.client.connected) {
      return false;
    }

    try {
      this.client.publish({
        destination: `/app/rooms/${roomId}/send`,
        body: JSON.stringify({ sender, content })
      });
      return true;
    } catch {
      this.connectedSubject.next(false);
      return false;
    }
  }

  listRooms(): Observable<ChatRoom[]> {
    return this.http.get<ChatRoom[]>(`${environment.apiBaseUrl}/api/rooms`, {
      withCredentials: true
    });
  }

  createRoom(name: string): Observable<ChatRoom> {
    return this.http.post<ChatRoom>(
      `${environment.apiBaseUrl}/api/rooms`,
      { name },
      { withCredentials: true }
    );
  }

  getMessages(roomId: string, limit = 50): Observable<ChatMessage[]> {
    return this.http.get<ChatMessage[]>(
      `${environment.apiBaseUrl}/api/rooms/${roomId}/messages`,
      {
        params: { limit },
        withCredentials: true
      }
    );
  }

  ngOnDestroy(): void {
    this.disconnect();
  }
}
