import { describe, expect, it, vi, afterEach } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Footer } from "@/components/landing/footer";

describe("Footer — plugin widget routing", () => {
  afterEach(() => {
    delete (window as { Arbor?: unknown }).Arbor;
  });

  it("opens the widget modal instead of navigating when window.Arbor is present and logged out", async () => {
    const open = vi.fn();
    window.Arbor = { open, close: vi.fn() };
    const user = userEvent.setup();

    render(<Footer authed={false} />);
    const link = screen.getByRole("link", { name: "Login" });
    expect(link).toHaveAttribute("href", "/login");

    await user.click(link);
    expect(open).toHaveBeenCalledTimes(1);
  });

  it("falls back to the real /login href when window.Arbor is absent and logged out", async () => {
    delete (window as { Arbor?: unknown }).Arbor;
    const user = userEvent.setup();

    render(<Footer authed={false} />);
    const link = screen.getByRole("link", { name: "Login" });
    expect(link).toHaveAttribute("href", "/login");

    await user.click(link);
    expect(window.Arbor).toBeUndefined();
  });

  it("shows 'Open app' linking to /search when authed, and never opens the widget even if window.Arbor exists", async () => {
    const open = vi.fn();
    window.Arbor = { open, close: vi.fn() };
    const user = userEvent.setup();

    render(<Footer authed={true} />);
    const link = screen.getByRole("link", { name: "Open app" });
    expect(link).toHaveAttribute("href", "/search");
    expect(screen.queryByRole("link", { name: "Login" })).not.toBeInTheDocument();

    await user.click(link);
    expect(open).not.toHaveBeenCalled();
  });
});
