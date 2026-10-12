import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { Client } from "@stomp/stompjs";
import { HttpClient } from "@angular/common/http";
import { ChatService } from "./chat.service";

describe("chat transport", () => {
  let service: ChatService;
  let client: Client;
  beforeEach(() => {
    vi.spyOn(Client.prototype, "activate").mockImplementation(() => {});
    vi.spyOn(Client.prototype, "deactivate").mockResolvedValue();
    service = new ChatService({} as HttpClient);
    service.connect();
    client = (service as unknown as { client: Client }).client;
  });
  afterEach(() => vi.restoreAllMocks());

  it("only accepts a message when the connected transport publishes it", () => {
    const connected = vi.spyOn(Client.prototype, "connected", "get").mockReturnValue(false);
    const publish = vi.spyOn(Client.prototype, "publish").mockImplementation(() => {});
    expect(service.sendMessage("room", "user", "hello")).toBe(false);
    expect(publish).not.toHaveBeenCalled();
    connected.mockReturnValue(true);
    expect(service.sendMessage("room", "user", "hello")).toBe(true);
    expect(publish).toHaveBeenCalledWith({
      destination: "/app/rooms/room/send",
      body: JSON.stringify({ sender: "user", content: "hello" })
    });
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
