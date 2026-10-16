import { ChangeDetectorRef, Component, OnDestroy, OnInit } from "@angular/core";
import { Subscription } from "rxjs";
import { AuthService } from "./auth.service";
import { ChatService } from "./chat.service";
import { ChatMessage, ChatRoom, UserProfile } from "./models";

@Component({
  selector: "app-root",
  standalone: false,
  templateUrl: "./app.component.html",
  styleUrls: ["./app.component.css"]
})
export class AppComponent implements OnInit, OnDestroy {
  rooms: ChatRoom[] = [];
  selectedRoom: ChatRoom | null = null;
  messages: ChatMessage[] = [];
  newRoomName = "";
  newMessage = "";
  user: UserProfile | null = null;
  connected = false;
  roomError = "";
  messageError = "";
  searchQuery = "";
  searchResults: ChatMessage[] | null = null;
  onlineUsers: string[] = [];
  typingUsers: string[] = [];
  private searchSubscription?: Subscription;

  private readonly subscriptions: Subscription[] = [];
  private historySubscription?: Subscription;

  constructor(private chatService: ChatService, private authService: AuthService, private changes: ChangeDetectorRef) {}

  ngOnInit(): void {
    this.chatService.connect();
    this.subscriptions.push(this.chatService.saved$.subscribe((roomId) => {
      if (this.selectedRoom?.id === roomId) this.loadHistory(roomId);
    }));
    this.subscriptions.push(this.chatService.presence$.subscribe((members) => {
      this.onlineUsers = [...new Set(members.map((member) => member.name))];
      this.typingUsers = [...new Set(members.filter((member) => member.typingUntil > 0).map((member) => member.name))];
      this.changes.markForCheck();
    }));
    this.subscriptions.push(this.chatService.errors$.subscribe((failure) => {
      this.messageError = `${failure.error}. Unsent text: ${failure.content}`;
      if (!this.newMessage) this.newMessage = failure.content;
      this.changes.markForCheck();
    }));

    this.subscriptions.push(
      this.chatService.connected$.subscribe((connected) => {
        const reconnected = connected && !this.connected;
        this.connected = connected;
        if (reconnected && this.selectedRoom) this.selectRoom(this.selectedRoom);
        this.changes.markForCheck();
      })
    );

    this.subscriptions.push(
      this.chatService.messages$.subscribe((message) => {
        if (this.selectedRoom && message.roomId === this.selectedRoom.id
            && !this.messages.some((existing) => existing.id === message.id)) {
          this.messages = [...this.messages, message];
        this.changes.markForCheck();
        }
      })
    );

    this.subscriptions.push(
      this.authService.user$.subscribe((user) => {
        this.user = user;
        this.chatService.setDisplayName(user?.displayName || user?.username || "anonymous");
        this.changes.markForCheck();
      })
    );

    this.authService.loadProfile().subscribe();
    this.refreshRooms();
  }

  refreshRooms(): void {
    this.chatService.listRooms().subscribe({
      next: (rooms) => {
        this.rooms = rooms;
        this.changes.markForCheck();
        if (!this.selectedRoom && rooms.length > 0) {
          this.selectRoom(rooms[0]);
        }
      },
      error: () => {
        this.rooms = [];
        this.changes.markForCheck();
      }
    });
  }

  selectRoom(room: ChatRoom): void {
    this.searchSubscription?.unsubscribe();
    this.searchQuery = ""; this.searchResults = null;
    this.historySubscription?.unsubscribe();
    this.selectedRoom = room;
    this.messages = [];
    this.chatService.subscribeToRoom(room.id);
    this.loadHistory(room.id);
  }

  private loadHistory(roomId: string): void {
    this.historySubscription?.unsubscribe();
    this.historySubscription = this.chatService.getMessages(roomId).subscribe({
      next: (messages) => {
        const merged = new Map([...messages, ...this.messages].map((message) => [message.id, message]));
        this.messages = [...merged.values()];
        this.changes.markForCheck();
      },
      error: () => { /* Keep messages already received over the live connection. */ }
    });
  }

  createRoom(): void {
    const name = this.newRoomName.trim();
    if (!name) {
      return;
    }

    this.chatService.createRoom(name).subscribe({
      next: (room) => {
        this.roomError = "";
        this.newRoomName = "";
        this.rooms = [...this.rooms.filter((existing) => existing.id !== room.id), room];
        this.changes.markForCheck();
        this.selectRoom(room);
      },
      error: () => {
        this.roomError = "Could not create the room. Your name was kept; please retry.";
        this.changes.markForCheck();
      }
    });
  }

  sendMessage(): void {
    if (!this.selectedRoom) {
      return;
    }

    const content = this.newMessage.trim();
    if (!content) {
      return;
    }

    const sender = this.user?.displayName || this.user?.username || "anonymous";
    if (this.chatService.sendMessage(this.selectedRoom.id, sender, content)) {
      this.messageError = "";
      this.newMessage = "";
    }
  }

  search(): void {
    this.searchSubscription?.unsubscribe();
    if (!this.selectedRoom || !this.searchQuery.trim()) { this.searchResults = null; return; }
    this.searchSubscription = this.chatService.getMessages(this.selectedRoom.id, 100, this.searchQuery.trim())
      .subscribe({next: (messages) => { this.searchResults = messages; this.changes.markForCheck(); },
        error: () => { this.messageError = "Search failed. Please retry."; this.changes.markForCheck(); }});
  }
  notifyTyping(): void { this.chatService.notifyTyping(); }

  login(): void {
    this.authService.login();
  }

  logout(): void {
    this.authService.logout();
  }

  ngOnDestroy(): void {
    this.searchSubscription?.unsubscribe();
    this.historySubscription?.unsubscribe();
    this.subscriptions.forEach((subscription) => subscription.unsubscribe());
    this.chatService.disconnect();
  }
}
