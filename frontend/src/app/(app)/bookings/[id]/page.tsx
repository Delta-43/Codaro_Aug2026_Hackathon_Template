// Booking detail — deep-linkable at /bookings/:id. Full detail (price
// breakdown, cutoff countdown, change history, actions) lands in Phase 7.
import Link from "next/link";
import { cn } from "@/lib/utils";
import { buttonVariants } from "@/components/ui/button";

export default function BookingDetailPage({ params }: { params: { id: string } }) {
  return (
    <section className="py-6">
      <Link
        href="/bookings"
        className={cn(buttonVariants({ variant: "ghost", size: "sm" }), "-ml-2 mb-4")}
      >
        ← Bookings
      </Link>
      <h1 className="text-lg font-semibold tracking-tight">Booking</h1>
      <p className="mt-1 font-mono text-sm text-muted-foreground">{params.id}</p>
      <p className="mt-6 rounded-lg border border-dashed border-border p-4 text-sm text-muted-foreground">
        Full booking detail arrives in Phase 7.
      </p>
    </section>
  );
}
