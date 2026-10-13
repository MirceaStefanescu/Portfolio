import { ChangeDetectorRef, provideZonelessChangeDetection } from "@angular/core";
import { Subject, of } from "rxjs";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { AppComponent } from "./app.component";
import { AppModule } from "./app.module";
import { TestBed } from "@angular/core/testing";
import { ChatService } from "./chat.service";
import { AuthService } from "./auth.service";
import { ChatMessage, ChatRoom } from "./models";

const room = (id: string): ChatRoom => ({ id, name: id, createdAt: "2026-01-01T00:00:00Z" });
const message = (id: string, roomId: string): ChatMessage => ({
  id, roomId, roomName: roomId, sender: "demo", content: id, createdAt: "2026-01-01T00:00:00Z"
});

describe("room timeline and composer", () => {
  let component: AppComponent;
  let incoming: Subject<ChatMessage>;
  let histories: Map<string, Subject<ChatMessage[]>>;
  let service: { [key: string]: any };

  beforeEach(() => {
    TestBed.configureTestingModule({ imports: [AppModule] });
    incoming = new Subject();
    histories = new Map([["a", new Subject()], ["b", new Subject()]]);
    service = {
      connect: vi.fn(), disconnect: vi.fn(), subscribeToRoom: vi.fn(),
      connected$: of(false), messages$: incoming,
      listRooms: () => of([]),
      getMessages: (id: string) => histories.get(id)!,
      sendMessage: vi.fn().mockReturnValue(false)
    };
    component = new AppComponent(service as unknown as ChatService, {
      user$: of(null), loadProfile: () => of(null)
    } as unknown as AuthService, { markForCheck: vi.fn() } as unknown as ChangeDetectorRef);
    component.ngOnInit();
  });

  it("keeps the selected room when an older history request returns late", () => {
    component.selectRoom(room("a"));
    component.selectRoom(room("b"));
    histories.get("b")!.next([message("new", "b")]);
    histories.get("a")!.next([message("old", "a")]);
    expect(component.messages.map((m) => m.id)).toEqual(["new"]);
    component.ngOnDestroy();
  });

  it("retains live messages while history loads and removes duplicate ids", () => {
    component.selectRoom(room("a"));
    incoming.next(message("live", "a"));
    histories.get("a")!.next([message("old", "a")]);
    expect(component.messages.map((m) => m.id)).toEqual(["old", "live"]);
    incoming.next(message("live", "a"));
    expect(component.messages.map((m) => m.id)).toEqual(["old", "live"]);
    component.ngOnDestroy();
  });

  it("keeps live messages when history fails", () => {
    component.selectRoom(room("a"));
    incoming.next(message("live", "a"));
    histories.get("a")!.error(new Error("offline"));
    expect(component.messages.map((m) => m.id)).toEqual(["live"]);
    component.ngOnDestroy();
  });

  it("preserves the draft when the transport cannot send it", () => {
    component.selectRoom(room("a"));
    component.newMessage = " draft ";
    component.sendMessage();
    expect(component.newMessage).toBe(" draft ");
    component.ngOnDestroy();
  });

  it("clears the draft only after the transport accepts it", () => {
    component.selectRoom(room("a"));
    service["sendMessage"].mockReturnValue(true);
    component.newMessage = " hello ";
    component.sendMessage();
    expect(service["sendMessage"]).toHaveBeenCalledWith("a", "anonymous", "hello");
    expect(component.newMessage).toBe("");
    component.ngOnDestroy();
  });

  it("cancels pending history when the component is destroyed", () => {
    component.selectRoom(room("a"));
    component.ngOnDestroy();
    histories.get("a")!.next([message("late", "a")]);
    expect(component.messages).toEqual([]);
    expect(service["disconnect"]).toHaveBeenCalledOnce();
  });
});


describe("asynchronous rendering with zoneless Angular", () => {
  it("renders profile, connection, rooms and incoming messages without a user event", async () => {
    const connected = new Subject<boolean>();
    const rooms = new Subject<ChatRoom[]>();
    const incoming = new Subject<ChatMessage>();
    const profile = new Subject<any>();
    await TestBed.configureTestingModule({
      imports: [AppModule],
      providers: [provideZonelessChangeDetection(),
        { provide: ChatService, useValue: {
          connect: vi.fn(), disconnect: vi.fn(), subscribeToRoom: vi.fn(),
          connected$: connected, messages$: incoming,
          listRooms: () => rooms, getMessages: () => of([])
        } },
        { provide: AuthService, useValue: { user$: profile, loadProfile: () => of(null) } }
      ]
    }).compileComponents();
    const fixture = TestBed.createComponent(AppComponent);
    fixture.autoDetectChanges();
    await fixture.whenStable();
    connected.next(true);
    profile.next({ username: "demo", displayName: "Demo User" });
    rooms.next([room("rendered-room")]);
    await fixture.whenStable();
    expect(fixture.nativeElement.textContent).toContain("Connected");
    expect(fixture.nativeElement.textContent).toContain("Demo User");
    expect(fixture.nativeElement.textContent).toContain("rendered-room");
    incoming.next(message("received-without-click", "rendered-room"));
    await fixture.whenStable();
    expect(fixture.nativeElement.textContent).toContain("received-without-click");
  });
});
