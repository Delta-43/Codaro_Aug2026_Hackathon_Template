import { describe, expect, it, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { AuthForm } from "@/components/auth-form";
import { useAuth } from "@/lib/auth";

vi.mock("@/lib/auth", () => ({ useAuth: vi.fn() }));

const mockUseAuth = vi.mocked(useAuth);

function baseAuth(overrides: Partial<ReturnType<typeof useAuth>> = {}) {
  return {
    configured: true,
    signIn: vi.fn(),
    signUp: vi.fn(),
    ...overrides,
  } as unknown as ReturnType<typeof useAuth>;
}

describe("AuthForm", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("calls signIn with the entered credentials on submit (default sign-in mode)", async () => {
    const signIn = vi.fn().mockResolvedValue({ role: "client" });
    mockUseAuth.mockReturnValue(baseAuth({ signIn }));
    const user = userEvent.setup();

    render(<AuthForm />);
    await user.type(screen.getByLabelText("Email"), "demo@codaro.app");
    await user.type(screen.getByLabelText("Password"), "hunter2");
    await user.click(screen.getByRole("button", { name: "Sign in" }));

    await waitFor(() => expect(signIn).toHaveBeenCalledWith("demo@codaro.app", "hunter2"));
  });

  it("shows the returned error message when signIn rejects", async () => {
    const signIn = vi.fn().mockRejectedValue(new Error("Invalid credentials"));
    mockUseAuth.mockReturnValue(baseAuth({ signIn }));
    const user = userEvent.setup();

    render(<AuthForm />);
    await user.type(screen.getByLabelText("Email"), "demo@codaro.app");
    await user.type(screen.getByLabelText("Password"), "wrong");
    await user.click(screen.getByRole("button", { name: "Sign in" }));

    expect(await screen.findByText("Invalid credentials")).toBeInTheDocument();
  });

  it("switches to sign-up mode, requires the consent checkbox, and calls signUp", async () => {
    const signUp = vi.fn().mockResolvedValue({ needsConfirmation: false, role: "client" });
    mockUseAuth.mockReturnValue(baseAuth({ signUp }));
    const user = userEvent.setup();

    render(<AuthForm />);
    await user.click(screen.getByRole("button", { name: "Create an account" }));

    const submit = screen.getByRole("button", { name: "Create account" });
    expect(submit).toBeDisabled(); // consent not yet agreed

    await user.type(screen.getByLabelText("Email"), "new@codaro.app");
    await user.type(screen.getByLabelText("Password"), "hunter2");
    await user.click(screen.getByRole("checkbox"));
    expect(submit).not.toBeDisabled();

    await user.click(submit);
    await waitFor(() =>
      expect(signUp).toHaveBeenCalledWith("new@codaro.app", "hunter2", "client", true),
    );
  });

  it("shows a confirmation notice and returns to sign-in mode when signUp needs email confirmation", async () => {
    const signUp = vi.fn().mockResolvedValue({ needsConfirmation: true, role: "client" });
    mockUseAuth.mockReturnValue(baseAuth({ signUp }));
    const user = userEvent.setup();

    render(<AuthForm />);
    await user.click(screen.getByRole("button", { name: "Create an account" }));
    await user.type(screen.getByLabelText("Email"), "new@codaro.app");
    await user.type(screen.getByLabelText("Password"), "hunter2");
    await user.click(screen.getByRole("checkbox"));
    await user.click(screen.getByRole("button", { name: "Create account" }));

    expect(await screen.findByText(/check your inbox/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Sign in" })).toBeInTheDocument();
  });

  it("disables submit and shows a warning when auth isn't configured", () => {
    mockUseAuth.mockReturnValue(baseAuth({ configured: false }));
    render(<AuthForm />);
    expect(screen.getByText(/auth is not configured/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Sign in" })).toBeDisabled();
  });
});
