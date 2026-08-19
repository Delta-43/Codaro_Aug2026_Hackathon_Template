import { describe, expect, it, vi, beforeEach, afterEach } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { NavBar } from "@/components/landing/nav-bar";

/**
 * jsdom has no native ResizeObserver, and NavBar observes the link strip
 * unconditionally on mount (see embed/layout.test.tsx for the same stub).
 */
class MockResizeObserver {
  observe = vi.fn();
  unobserve = vi.fn();
  disconnect = vi.fn();
  constructor(_callback: ResizeObserverCallback) {}
}

describe("NavBar — plugin widget routing", () => {
  beforeEach(() => {
    vi.stubGlobal("ResizeObserver", MockResizeObserver);
  });

  afterEach(() => {
    delete (window as { Arbor?: unknown }).Arbor;
    vi.unstubAllGlobals();
  });

  it("opens the widget modal instead of navigating when window.Arbor is present and logged out", async () => {
    const open = vi.fn();
    window.Arbor = { open, close: vi.fn() };
    const user = userEvent.setup();

    render(<NavBar authed={false} />);
    const link = screen.getByRole("link", { name: "Login" });
    expect(link).toHaveAttribute("href", "/login");

    await user.click(link);
    expect(open).toHaveBeenCalledTimes(1);
  });

  it("falls back to the real /login href when window.Arbor is absent and logged out", async () => {
    delete (window as { Arbor?: unknown }).Arbor;
    const user = userEvent.setup();

    render(<NavBar authed={false} />);
    const link = screen.getByRole("link", { name: "Login" });
    expect(link).toHaveAttribute("href", "/login");

    await user.click(link);
    expect(window.Arbor).toBeUndefined();
  });

  it("shows 'Open app' linking to /search when authed, and never opens the widget even if window.Arbor exists", async () => {
    const open = vi.fn();
    window.Arbor = { open, close: vi.fn() };
    const user = userEvent.setup();

    render(<NavBar authed={true} />);
    const link = screen.getByRole("link", { name: "Open app" });
    expect(link).toHaveAttribute("href", "/search");
    expect(screen.queryByRole("link", { name: "Login" })).not.toBeInTheDocument();

    await user.click(link);
    expect(open).not.toHaveBeenCalled();
  });
});
