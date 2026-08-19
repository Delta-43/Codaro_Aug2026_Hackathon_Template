import { describe, expect, it, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import EmbedLayout from "@/app/embed/layout";
import { getPivotConfig } from "@/api";

vi.mock("@/api", () => ({ getPivotConfig: vi.fn() }));
vi.mock("@/components/auth-gate", () => ({
  AuthGate: ({ children }: { children: React.ReactNode }) => <>{children}</>,
}));
vi.mock("@/context/app-context", () => ({
  AppProvider: ({ children }: { children: React.ReactNode }) => <>{children}</>,
}));

const mockGetPivotConfig = vi.mocked(getPivotConfig);

/**
 * jsdom has no native ResizeObserver. This stub captures the constructor
 * callback so a test can invoke it manually to simulate a real resize.
 */
class MockResizeObserver {
  static instances: MockResizeObserver[] = [];
  callback: ResizeObserverCallback;
  observe = vi.fn();
  unobserve = vi.fn();
  disconnect = vi.fn();
  constructor(callback: ResizeObserverCallback) {
    this.callback = callback;
    MockResizeObserver.instances.push(this);
  }
}

describe("EmbedLayout — postMessage resize wiring", () => {
  beforeEach(() => {
    MockResizeObserver.instances = [];
    vi.stubGlobal("ResizeObserver", MockResizeObserver);
    mockGetPivotConfig.mockResolvedValue({
      tenancy: { mode: "single", providerCode: "VISTULA-4471" },
      location: { origin: null, distanceUnit: "km", timezone: "UTC" },
      capabilities: {},
      theme: { primaryColor: "#4f46e5", radius: "0.5rem", logoUrl: null, fontFamily: null },
    });
    // jsdom defaults window.parent to window itself (i.e. "not framed").
    Object.defineProperty(window, "parent", { value: window, configurable: true });
  });

  it("does nothing when not actually framed (window.parent === window)", () => {
    render(
      <EmbedLayout>
        <div>booking content</div>
      </EmbedLayout>,
    );
    expect(MockResizeObserver.instances).toHaveLength(0);
  });

  it("observes the AuthGate wrapper and posts resize messages when framed", () => {
    const postMessage = vi.fn();
    Object.defineProperty(window, "parent", {
      value: { postMessage },
      configurable: true,
    });

    render(
      <EmbedLayout>
        <div>booking content</div>
      </EmbedLayout>,
    );

    expect(screen.getByText("booking content")).toBeInTheDocument();

    // One observer, observing the ref'd wrapper (not something inside
    // `children`, which wouldn't exist while AuthGate's fallback is showing).
    expect(MockResizeObserver.instances).toHaveLength(1);
    const observer = MockResizeObserver.instances[0];
    expect(observer.observe).toHaveBeenCalledTimes(1);

    // Posted once immediately on mount.
    expect(postMessage).toHaveBeenCalledWith(
      { type: "codaro:resize", height: expect.any(Number) },
      "*",
    );
    expect(postMessage).toHaveBeenCalledTimes(1);

    // Simulate a real resize by invoking the captured callback.
    observer.callback([] as unknown as ResizeObserverEntry[], observer as unknown as ResizeObserver);
    expect(postMessage).toHaveBeenCalledTimes(2);
  });

  it("disconnects the observer on unmount", () => {
    Object.defineProperty(window, "parent", {
      value: { postMessage: vi.fn() },
      configurable: true,
    });

    const { unmount } = render(
      <EmbedLayout>
        <div>booking content</div>
      </EmbedLayout>,
    );
    const observer = MockResizeObserver.instances[0];

    unmount();
    expect(observer.disconnect).toHaveBeenCalledTimes(1);
  });
});
