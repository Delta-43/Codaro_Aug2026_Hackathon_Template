import { describe, expect, it, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { GuestOtpForm } from "@/components/embed/guest-otp-form";
import { useAuth } from "@/lib/auth";

vi.mock("@/lib/auth", () => ({ useAuth: vi.fn() }));

const mockUseAuth = vi.mocked(useAuth);

function baseAuth(overrides: Partial<ReturnType<typeof useAuth>> = {}) {
  return {
    configured: true,
    sendOtp: vi.fn(),
    verifyOtp: vi.fn(),
    ...overrides,
  } as unknown as ReturnType<typeof useAuth>;
}

describe("GuestOtpForm", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("sends a code and advances to the code step", async () => {
    const sendOtp = vi.fn().mockResolvedValue(undefined);
    mockUseAuth.mockReturnValue(baseAuth({ sendOtp }));
    const user = userEvent.setup();

    render(<GuestOtpForm />);
    await user.type(screen.getByLabelText("Email"), "guest@codaro.app");
    await user.click(screen.getByRole("button", { name: "Send code" }));

    await waitFor(() => expect(sendOtp).toHaveBeenCalledWith("guest@codaro.app"));
    expect(await screen.findByText(/we sent a code to/i)).toBeInTheDocument();
    expect(screen.getByText("guest@codaro.app")).toBeInTheDocument();
  });

  it("shows an error and stays on the email step when sendOtp rejects", async () => {
    const sendOtp = vi.fn().mockRejectedValue(new Error("email rate limit exceeded"));
    mockUseAuth.mockReturnValue(baseAuth({ sendOtp }));
    const user = userEvent.setup();

    render(<GuestOtpForm />);
    await user.type(screen.getByLabelText("Email"), "guest@codaro.app");
    await user.click(screen.getByRole("button", { name: "Send code" }));

    expect(await screen.findByText("email rate limit exceeded")).toBeInTheDocument();
    expect(screen.getByLabelText("Email")).toBeInTheDocument(); // still on the email step
  });

  it("verifies the code with the email it was sent to", async () => {
    const sendOtp = vi.fn().mockResolvedValue(undefined);
    const verifyOtp = vi.fn().mockResolvedValue(undefined);
    mockUseAuth.mockReturnValue(baseAuth({ sendOtp, verifyOtp }));
    const user = userEvent.setup();

    render(<GuestOtpForm />);
    await user.type(screen.getByLabelText("Email"), "guest@codaro.app");
    await user.click(screen.getByRole("button", { name: "Send code" }));
    await screen.findByLabelText("Code");

    await user.type(screen.getByLabelText("Code"), "123456");
    await user.click(screen.getByRole("button", { name: "Confirm" }));

    await waitFor(() =>
      expect(verifyOtp).toHaveBeenCalledWith("guest@codaro.app", "123456"),
    );
  });

  it("shows an error on a bad code without losing the email", async () => {
    const sendOtp = vi.fn().mockResolvedValue(undefined);
    const verifyOtp = vi.fn().mockRejectedValue(new Error("Token has expired or is invalid"));
    mockUseAuth.mockReturnValue(baseAuth({ sendOtp, verifyOtp }));
    const user = userEvent.setup();

    render(<GuestOtpForm />);
    await user.type(screen.getByLabelText("Email"), "guest@codaro.app");
    await user.click(screen.getByRole("button", { name: "Send code" }));
    await user.type(await screen.findByLabelText("Code"), "000000");
    await user.click(screen.getByRole("button", { name: "Confirm" }));

    expect(await screen.findByText("Token has expired or is invalid")).toBeInTheDocument();
  });

  it("'Use a different email' resets back to the email step", async () => {
    const sendOtp = vi.fn().mockResolvedValue(undefined);
    mockUseAuth.mockReturnValue(baseAuth({ sendOtp }));
    const user = userEvent.setup();

    render(<GuestOtpForm />);
    await user.type(screen.getByLabelText("Email"), "guest@codaro.app");
    await user.click(screen.getByRole("button", { name: "Send code" }));
    await screen.findByLabelText("Code");

    await user.click(screen.getByRole("button", { name: "Use a different email" }));

    expect(screen.getByLabelText("Email")).toBeInTheDocument();
    expect(screen.queryByLabelText("Code")).not.toBeInTheDocument();
  });
});
