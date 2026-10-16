import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { Client } from "@stomp/stompjs";
import { HttpClient, provideHttpClient } from "@angular/common/http";
import { HttpTestingController, provideHttpClientTesting } from "@angular/common/http/testing";
import { TestBed } from "@angular/core/testing";
import { environment } from "../environments/environment";
import { ChatService } from "./chat.service";

describe("chat transport", () => {
  let service: ChatService;
  let client: Client;
  beforeEach(() => {
    vi.spyOn(Client.prototype, "activate").mockImplementation(() => {});
    vi.spyOn(Client.prototype, "deactivate").mockResolvedValue();
    vi.spyOn(Client.prototype, "subscribe").mockReturnValue({ id: "sub", unsubscribe: vi.fn() });
    vi.spyOn(Client.prototype, "publish").mockImplementation(() => {});
    service = new ChatService({} as HttpClient);
    service.connect();
    client = (service as unknown as { client: Client }).client;
  });
  afterEach(() => { service.disconnect(); vi.useRealTimers(); vi.restoreAllMocks(); });

  it("only accepts a message when the connected transport publishes it", () => {
    const connected = vi.spyOn(Client.prototype, "connected", "get").mockReturnValue(false);
    const publish = vi.spyOn(Client.prototype, "publish").mockImplementation(() => {});
    expect(service.sendMessage("room", "user", "hello")).toBe(false);
    expect(publish).not.toHaveBeenCalled();
    connected.mockReturnValue(true);
    expect(service.sendMessage("room", "user", "hello")).toBe(true);
    expect(publish.mock.calls[0][0].destination).toBe("/app/rooms/room/send");
    expect(JSON.parse(publish.mock.calls[0][0].body!)).toEqual({ sender: "user", content: "hello", requestId: expect.any(String) });
  });

  it("resends unacknowledged messages with the same ID and restores a rejected draft", () => {
    vi.spyOn(Client.prototype, "connected", "get").mockReturnValue(true);
    const callbacks = new Map<string, (frame: any) => void>();
    vi.mocked(client.subscribe).mockImplementation((destination, callback) => {
      callbacks.set(destination, callback); return { id: destination, unsubscribe: vi.fn() };
    });
    const errors = vi.fn();
    service.errors$.subscribe(errors);
    client.onConnect({} as any);
    service.sendMessage("room", "user", "keep me");
    const original = vi.mocked(client.publish).mock.calls.at(-1)![0];
    client.onWebSocketClose(new CloseEvent("close"));
    client.onConnect({} as any);
    expect(vi.mocked(client.publish).mock.calls.at(-1)![0]).toEqual(original);
    callbacks.get("/user/queue/receipts")!({body: JSON.stringify({requestId: JSON.parse(original.body!).requestId,
      accepted: false, error: "Rate limit exceeded"})});
    expect(errors).toHaveBeenCalledWith({content: "keep me", error: "Rate limit exceeded"});
    vi.mocked(client.publish).mockClear();
    client.onConnect({} as any);
    expect(client.publish).not.toHaveBeenCalled();
  });

  it("expires typing and presence using server-relative time", () => {
    vi.useFakeTimers(); vi.setSystemTime(100000);
    vi.spyOn(Client.prototype, "connected", "get").mockReturnValue(true);
    let receive!: (message: any) => void;
    vi.mocked(client.subscribe).mockImplementation((destination, callback) => {
      if (destination.endsWith("/presence")) receive = callback;
      return {id: destination, unsubscribe: vi.fn()};
    });
    let current: any[] = [];
    service.presence$.subscribe((members) => current = members);
    service.subscribeToRoom("room");
    receive({body: JSON.stringify({serverTime: 5000, members: [{sessionId: "s", name: "Alice", expiresAt: 10000, typingUntil: 7000}]})});
    expect(current[0].name).toBe("Alice"); expect(current[0].typingUntil).toBe(102000);
    vi.advanceTimersByTime(2000); expect(current[0].typingUntil).toBe(0);
    vi.advanceTimersByTime(3000); expect(current).toEqual([]);
  });

  it("reports a failed publication without accepting the draft", () => {
    vi.spyOn(Client.prototype, "connected", "get").mockReturnValue(true);
    vi.spyOn(Client.prototype, "publish").mockImplementation(() => { throw new Error("closed"); });
    const states: boolean[] = [];
    service.connected$.subscribe((state) => states.push(state));
    client.onConnect({} as any);
    expect(service.sendMessage("room", "user", "hello")).toBe(false);
    expect(states).toEqual([false, true, false]);
  });

  it("marks socket loss disconnected and cleans up without sending on the closed socket", () => {
    const connected = vi.spyOn(Client.prototype, "connected", "get").mockReturnValue(true);
    const unsubscribe = vi.fn(() => { throw new Error("closed connection"); });
    vi.spyOn(Client.prototype, "subscribe").mockReturnValue({ id: "sub", unsubscribe });
    service.subscribeToRoom("room");
    connected.mockReturnValue(false);
    const states: boolean[] = [];
    service.connected$.subscribe((state) => states.push(state));
    client.onWebSocketClose(new CloseEvent("close"));
    expect(() => service.disconnect()).not.toThrow();
    expect(unsubscribe).not.toHaveBeenCalled();
    expect(client.deactivate).toHaveBeenCalledOnce();
    expect(states.at(-1)).toBe(false);
  });
});


describe("chat CSRF integration", () => {
  let service: ChatService;
  let http: HttpTestingController;
  beforeEach(() => {
    vi.spyOn(Client.prototype, "activate").mockImplementation(() => {});
    vi.spyOn(Client.prototype, "deactivate").mockResolvedValue();
    vi.spyOn(Client.prototype, "subscribe").mockReturnValue({ id: "sub", unsubscribe: vi.fn() });
    TestBed.configureTestingModule({
      providers: [provideHttpClient(), provideHttpClientTesting(), ChatService]
    });
    service = TestBed.inject(ChatService);
    http = TestBed.inject(HttpTestingController);
  });
  afterEach(() => {
    http.verify();
    service.disconnect();
    TestBed.resetTestingModule();
    vi.restoreAllMocks();
  });

  it("fetches the session token before posting a room with the token header", () => {
    const received = vi.fn();
    service.createRoom("Room").subscribe(received);
    const csrf = http.expectOne(environment.apiBaseUrl + "/api/csrf");
    expect(csrf.request.withCredentials).toBe(true);
    http.expectNone(environment.apiBaseUrl + "/api/rooms");
    csrf.flush({ headerName: "X-CSRF-TOKEN", token: "session-token" });
    const room = http.expectOne(environment.apiBaseUrl + "/api/rooms");
    expect(room.request.method).toBe("POST");
    expect(room.request.withCredentials).toBe(true);
    expect(room.request.headers.get("X-CSRF-TOKEN")).toBe("session-token");
    expect(room.request.body).toEqual({ name: "Room" });
    room.flush({ id: "room", name: "Room" });
    expect(received).toHaveBeenCalledWith({ id: "room", name: "Room" });
  });

  it("does not submit a mutation when the CSRF endpoint fails", () => {
    const failed = vi.fn();
    service.createRoom("Room").subscribe({ error: failed });
    http.expectOne(environment.apiBaseUrl + "/api/csrf")
      .flush("unavailable", { status: 503, statusText: "Unavailable" });
    http.expectNone(environment.apiBaseUrl + "/api/rooms");
    expect(failed).toHaveBeenCalledOnce();
  });

  it("refreshes the token for every STOMP connection including reconnects", async () => {
    service.connect();
    const client = (service as unknown as { client: Client }).client;
    for (const token of ["first-session", "new-session"]) {
      const prepared = client.beforeConnect(client);
      const request = http.expectOne(environment.apiBaseUrl + "/api/csrf");
      expect(request.request.withCredentials).toBe(true);
      request.flush({ headerName: "X-CSRF-TOKEN", token });
      await prepared;
      expect(client.connectHeaders).toEqual({ "X-CSRF-TOKEN": token });
    }
  });

  it("deactivates STOMP if token preparation fails", async () => {
    service.connect();
    const client = (service as unknown as { client: Client }).client;
    const prepared = client.beforeConnect(client);
    http.expectOne(environment.apiBaseUrl + "/api/csrf")
      .flush("unavailable", { status: 503, statusText: "Unavailable" });
    await expect(Promise.resolve(prepared)).resolves.toBeUndefined();
    expect(client.deactivate).toHaveBeenCalledOnce();
  });
  it("does not let a late token failure disconnect a newer client", async () => {
    service.connect();
    const previous = (service as unknown as { client: Client }).client;
    const prepared = previous.beforeConnect(previous);
    const request = http.expectOne(environment.apiBaseUrl + "/api/csrf");
    service.disconnect();
    service.connect();
    const current = (service as unknown as { client: Client }).client;
    const states: boolean[] = [];
    service.connected$.subscribe((state) => states.push(state));
    current.onConnect({} as any);
    request.flush("unavailable", { status: 503, statusText: "Unavailable" });
    await prepared;
    expect(states.at(-1)).toBe(true);
  });

});
