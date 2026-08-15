"use client";

/**
 * Booking detail — deep-linkable at /bookings/:id. Loads the booking and the
 * entities it references (bookings carry only ids), then hands off to
 * BookingDetail for the full view + lifecycle actions.
 */
import Link from "next/link";
import { ArrowLeft } from "lucide-react";
import type { Booking, Provider, Service } from "@/types/domain";
import { getBooking, getProvider, getResources, getService } from "@/api";
import { useApp } from "@/context/app-context";
import { useAsync } from "@/hooks/use-async";
import { cn } from "@/lib/utils";
import { Button, buttonVariants } from "@/components/ui/button";
import { Skeleton } from "@/components/skeleton";
import { BookingDetail } from "@/components/booking/booking-detail";

interface Loaded {
  booking: Booking;
  service: Service;
  provider: Provider;
  resourceName: string;
}

export default function BookingDetailPage({ params }: { params: { id: string } }) {
  const { user } = useApp();
  const tz = user?.timezone ?? "UTC";

  const data = useAsync<Loaded>(async () => {
    const booking = await getBooking(params.id);
    const [service, provider, resources] = await Promise.all([
      getService(booking.serviceId),
      getProvider(booking.providerId),
      getResources(booking.serviceId),
    ]);
    const resourceName = resources.find((r) => r.id === booking.resourceId)?.name ?? "";
    return { booking, service, provider, resourceName };
  }, [params.id]);

  if (data.loading && !data.data) {
    return (
      <section className="py-4">
        <Skeleton className="mb-4 h-7 w-24" />
        <Skeleton className="h-6 w-1/2" />
        <Skeleton className="mt-4 h-20 w-full" />
        <Skeleton className="mt-3 h-40 w-full" />
      </section>
    );
  }

  if (data.error || !data.data) {
    return (
      <section className="py-6">
        <Link
          href="/bookings"
          className={cn(buttonVariants({ variant: "ghost", size: "sm" }), "-ml-2 mb-4")}
        >
          <ArrowLeft className="size-4" aria-hidden /> Bookings
        </Link>
        <div className="rounded-lg border border-dashed border-border p-4 text-sm text-muted-foreground">
          <p>That booking could not be found.</p>
          <Button className="mt-3" onPress={data.reload}>
            Try again
          </Button>
        </div>
      </section>
    );
  }

  return (
    <BookingDetail
      booking={data.data.booking}
      service={data.data.service}
      provider={data.data.provider}
      resourceName={data.data.resourceName}
      tz={tz}
    />
  );
}
