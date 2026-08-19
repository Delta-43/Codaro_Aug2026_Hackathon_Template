import { describe, expect, it, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import { AuthGate } from "@/components/auth-gate";
import { useAuth } from "@/lib/auth";
import { usePathname, useRouter } from "next/navigation";

vi.mock("@/lib/auth", () => ({ useAuth: vi.fn() }));
vi.mock("next/navigation", () => ({
  useRouter: vi.fn(),
  usePathname: vi.fn(),
}));

const mockUseAuth = vi.mocked(useAuth);
const mockUseRouter = vi.mocked(useRouter);
const mockUsePathname = vi.mocked(usePathname);

describe("AuthGate", () => {
  const replace = vi.fn();

  beforeEach(() => {
    replace.mockClear();
    mockUseRouter.mockReturnValue({ replace } as unknown as ReturnType<typeof useRouter>);
    mockUsePathname.mockReturnValue("/provider");
  });

  it("shows a loading placeholder while the session is still resolving", () => {
    mockUseAuth.mockReturnValue({ session: null, loading: true } as ReturnType<typeof useAuth>);
    render(
      <AuthGate>
        <div>secret</div>
      </AuthGate>,
    );
    expect(screen.getByText("Loading…")).toBeInTheDocument();
    expect(screen.queryByText("secret")).not.toBeInTheDocument();
  });

  it("redirects to /login with ?next= when unauthenticated and no fallback is given", () => {
    mockUseAuth.mockReturnValue({ session: null, loading: false } as ReturnType<typeof useAuth>);
    render(
      <AuthGate>
        <div>secret</div>
      </AuthGate>,
    );
    expect(replace).toHaveBeenCalledWith("/login?next=%2Fprovider");
    expect(screen.queryByText("secret")).not.toBeInTheDocument();
  });

  it("renders fallback in place, without redirecting, when a fallback is given (the embed case)", () => {
    mockUseAuth.mockReturnValue({ session: null, loading: false } as ReturnType<typeof useAuth>);
    render(
      <AuthGate fallback={<div>sign in here</div>}>
        <div>secret</div>
      </AuthGate>,
    );
    expect(screen.getByText("sign in here")).toBeInTheDocument();
    expect(screen.queryByText("secret")).not.toBeInTheDocument();
    expect(replace).not.toHaveBeenCalled();
  });

  it("renders children once a session exists", () => {
    mockUseAuth.mockReturnValue({
      session: { user: { id: "u1" } },
      loading: false,
    } as unknown as ReturnType<typeof useAuth>);
    render(
      <AuthGate>
        <div>secret</div>
      </AuthGate>,
    );
    expect(screen.getByText("secret")).toBeInTheDocument();
    expect(replace).not.toHaveBeenCalled();
  });
});
