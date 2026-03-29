/**
 * Tests for useFeatureWebSocket hook
 */
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { renderHook, act } from "@testing-library/react";
import { useFeatureWebSocket } from "@/hooks/useFeatureWebSocket";

// Mock WebSocket
class MockWebSocket {
  static instances: MockWebSocket[] = [];
  url: string;
  onopen: (() => void) | null = null;
  onclose: (() => void) | null = null;
  onerror: (() => void) | null = null;
  onmessage: ((e: { data: string }) => void) | null = null;
  readyState = 0;

  constructor(url: string) {
    this.url = url;
    MockWebSocket.instances.push(this);
  }

  close() {
    this.readyState = 3;
    this.onclose?.();
  }

  simulateOpen() {
    this.readyState = 1;
    this.onopen?.();
  }

  simulateMessage(data: unknown) {
    this.onmessage?.({ data: JSON.stringify(data) });
  }

  simulateError() {
    this.onerror?.();
  }
}

vi.stubGlobal("WebSocket", MockWebSocket);

beforeEach(() => {
  MockWebSocket.instances = [];
});

describe("useFeatureWebSocket", () => {
  it("connects to correct WebSocket URL", () => {
    renderHook(() => useFeatureWebSocket("feat-001"));
    expect(MockWebSocket.instances).toHaveLength(1);
    expect(MockWebSocket.instances[0].url).toContain("feat-001");
  });

  it("starts disconnected, becomes connected on open", () => {
    const { result } = renderHook(() => useFeatureWebSocket("feat-001"));
    expect(result.current.connected).toBe(false);

    act(() => {
      MockWebSocket.instances[0].simulateOpen();
    });

    expect(result.current.connected).toBe(true);
  });

  it("appends events on message", () => {
    const { result } = renderHook(() => useFeatureWebSocket("feat-001"));

    act(() => {
      MockWebSocket.instances[0].simulateOpen();
      MockWebSocket.instances[0].simulateMessage({
        type: "status_change",
        feature_id: "feat-001",
        message: "pending → brainstorming",
      });
    });

    expect(result.current.events).toHaveLength(1);
    expect(result.current.events[0].type).toBe("status_change");
    expect(result.current.events[0].message).toBe("pending → brainstorming");
  });

  it("accumulates multiple events", () => {
    const { result } = renderHook(() => useFeatureWebSocket("feat-001"));

    act(() => {
      MockWebSocket.instances[0].simulateOpen();
      MockWebSocket.instances[0].simulateMessage({ type: "log", feature_id: "feat-001", message: "line 1" });
      MockWebSocket.instances[0].simulateMessage({ type: "log", feature_id: "feat-001", message: "line 2" });
    });

    expect(result.current.events).toHaveLength(2);
  });

  it("ignores malformed JSON messages", () => {
    const { result } = renderHook(() => useFeatureWebSocket("feat-001"));

    act(() => {
      MockWebSocket.instances[0].simulateOpen();
      MockWebSocket.instances[0].onmessage?.({ data: "not-json" });
    });

    expect(result.current.events).toHaveLength(0);
  });

  it("sets connected=false on error", () => {
    const { result } = renderHook(() => useFeatureWebSocket("feat-001"));

    act(() => {
      MockWebSocket.instances[0].simulateOpen();
    });
    expect(result.current.connected).toBe(true);

    act(() => {
      MockWebSocket.instances[0].simulateError();
    });
    expect(result.current.connected).toBe(false);
  });

  it("closes WebSocket on unmount", () => {
    const { unmount } = renderHook(() => useFeatureWebSocket("feat-001"));
    const ws = MockWebSocket.instances[0];

    unmount();

    expect(ws.readyState).toBe(3);
  });
});
