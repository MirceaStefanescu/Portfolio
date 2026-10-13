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

  private readonly subscriptions: Subscription[] = [];
  private historySubscription?: Subscription;

  constructor(private chatService: ChatService, private authService: AuthService, private changes: ChangeDetectorRef) {}

  ngOnInit(): void {
    this.chatService.connect();

    this.subscriptions.push(
      this.chatService.connected$.subscribe((connected) => {
        this.connected = connected;
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
    this.historySubscription?.unsubscribe();
    this.selectedRoom = room;
    this.messages = [];
    this.chatService.subscribeToRoom(room.id);
    this.historySubscription = this.chatService.getMessages(room.id).subscribe({
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
        this.newRoomName = "";
        this.rooms = [...this.rooms, room];
        this.changes.markForCheck();
        this.selectRoom(room);
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
      this.newMessage = "";
    }
  }

  login(): void {
    this.authService.login();
  }

  logout(): void {
    this.authService.logout();
  }

  ngOnDestroy(): void {
    this.historySubscription?.unsubscribe();
    this.subscriptions.forEach((subscription) => subscription.unsubscribe());
    this.chatService.disconnect();
  }
}
