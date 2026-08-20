# Pivot library

100 complete `domain.config.json` files — 55 single-tenant, 45 marketplace — generated from the pivot definitions in
`scripts/check_pivots.py` and `scripts/pivots_extended.py`.

Regenerate with `python3 scripts/generate_pivots.py`. Load one with
`python3 scripts/use_pivot.py <n>`. See [CLAUDE.md](CLAUDE.md).

| # | Business | Tenancy | Bookable unit | Pricing | Currency | Capabilities on | Note |
|---|----------|---------|---------------|---------|----------|-----------------|------|
| 1 | [Alpine Ski & Board Hire](001-alpine-ski-and-board-hire.json) | single | asset | per_unit | EUR | inventory, payments, prerequisites |  |
| 2 | [Dr. Halina's Dental Practice](002-dr-halina-s-dental-practice.json) | single | staff | fixed | EUR | payments, prerequisites |  |
| 3 | [Kraków Escape Rooms](003-krakow-escape-rooms.json) | single | room | tiered | EUR | payments |  |
| 4 | [Vinyasa Yoga Studio](004-vinyasa-yoga-studio.json) | single | class_capacity | subscription | EUR | entitlements, payments, prerequisites, waitlist |  |
| 5 | [Mobile Car Valeting](005-mobile-car-valeting.json) | single | time_slot | tiered | EUR | payments |  |
| 6 | [The Barbers on Floriańska](006-the-barbers-on-florianska.json) | single | staff | fixed | EUR | payments | E1 |
| 7 | [Community Allotment Plots](007-community-allotment-plots.json) | single | subscription_slot | subscription | EUR | inventory, payments, prerequisites, recurrence, waitlist | E2 |
| 8 | [Farm Shop Veg Boxes](008-farm-shop-veg-boxes.json) | single | stock_item | subscription | EUR | inventory, payments, recurrence |  |
| 9 | [Blood Donation Centre](009-blood-donation-centre.json) | single | time_slot | free | EUR | prerequisites |  |
| 10 | [City Tennis Courts](010-city-tennis-courts.json) | single | asset | per_hour | EUR | entitlements, inventory, payments |  |
| 11 | [Hilltop Boutique Hotel](011-hilltop-boutique-hotel.json) | single | room | per_person | EUR | inventory, payments, prerequisites |  |
| 12 | [Private Chef at Home](012-private-chef-at-home.json) | single | time_slot | quote | EUR | payments, prerequisites, quotes |  |
| 13 | [University Lab Equipment](013-university-lab-equipment.json) | single | asset | free | EUR | inventory, prerequisites |  |
| 14 | [Aqua Park Day Sessions](014-aqua-park-day-sessions.json) | single | class_capacity | per_person | EUR | payments |  |
| 15 | [Driving School](015-driving-school.json) | single | staff | per_hour | EUR | entitlements, payments, prerequisites |  |
| 16 | [Recording Studio](016-recording-studio.json) | single | room | per_hour | EUR | payments |  |
| 17 | [Vaccination Course (2-dose)](017-vaccination-course-2-dose.json) | single | time_slot | free | EUR | inventory, prerequisites | E6 |
| 18 | [Dog Grooming Salon](018-dog-grooming-salon.json) | single | staff | tiered | EUR | payments, prerequisites |  |
| 19 | [Self-Storage Units](019-self-storage-units.json) | single | subscription_slot | subscription | EUR | inventory, payments, prerequisites, recurrence | E2 |
| 20 | [Theatre Reserved Seating](020-theatre-reserved-seating.json) | single | seat | tiered | EUR | inventory, payments | E3 |
| 21 | [Physiotherapy (insurer-billed)](021-physiotherapy-insurer-billed.json) | single | staff | fixed | EUR | payments, prerequisites |  |
| 22 | [Van Hire, driver optional](022-van-hire-driver-optional.json) | single | asset | per_unit | EUR | inventory, payments, prerequisites |  |
| 23 | [Online Language Tutor](023-online-language-tutor.json) | single | time_slot | per_hour | EUR | payments |  |
| 24 | [Charity Gala](024-charity-gala.json) | single | seat | free | EUR | inventory, prerequisites, waitlist |  |
| 25 | [Community Tool Library](025-community-tool-library.json) | single | asset | free | EUR | entitlements, inventory, payments, prerequisites | E7 |
| 26 | [TradieNow (plumbers/sparks)](026-tradienow-plumbers-sparks.json) | multi | time_slot | quote | EUR | payments, prerequisites, quotes |  |
| 27 | [Fitness Class Marketplace](027-fitness-class-marketplace.json) | multi | class_capacity | subscription | EUR | entitlements, payments, waitlist |  |
| 28 | [Peer-to-Peer Car Sharing](028-peer-to-peer-car-sharing.json) | multi | asset | per_hour | EUR | inventory, payments, prerequisites |  |
| 29 | [Coworking Desk Marketplace](029-coworking-desk-marketplace.json) | multi | seat | per_unit | EUR | inventory, payments |  |
| 30 | [Wedding Venue Marketplace](030-wedding-venue-marketplace.json) | multi | room | quote | EUR | inventory, payments, prerequisites, quotes | E2 |
| 31 | [Home Cleaning (recurring)](031-home-cleaning-recurring.json) | multi | subscription_slot | per_hour | EUR | payments, recurrence | E6 |
| 32 | [Local Farmers Market](032-local-farmers-market.json) | multi | stock_item | per_unit | EUR | cart, inventory, payments |  |
| 33 | [Specialist Marketplace (insurer)](033-specialist-marketplace-insurer.json) | multi | staff | fixed | EUR | payments, prerequisites |  |
| 34 | [Event Ticketing Marketplace](034-event-ticketing-marketplace.json) | multi | class_capacity | tiered | EUR | inventory, payments, waitlist |  |
| 35 | [Construction Plant Rental](035-construction-plant-rental.json) | multi | asset | per_unit | EUR | inventory, payments, prerequisites |  |
| 36 | [Online Therapy Marketplace](036-online-therapy-marketplace.json) | multi | time_slot | tiered | EUR | payments, prerequisites |  |
| 37 | [Boat Charter Marketplace](037-boat-charter-marketplace.json) | multi | asset | per_unit | EUR | inventory, payments, prerequisites |  |
| 38 | [Tutoring Marketplace](038-tutoring-marketplace.json) | multi | class_capacity | per_person | EUR | payments | E10 |
| 39 | [Salon Marketplace](039-salon-marketplace.json) | multi | staff | fixed | EUR | payments |  |
| 40 | [Restaurant Reservations](040-restaurant-reservations.json) | multi | asset | free | EUR | inventory, waitlist | E3 |
| 41 | [Warehouse Pallet Space](041-warehouse-pallet-space.json) | multi | stock_item | per_unit | EUR | inventory, payments, prerequisites | schema gap |
| 42 | [Photographer Marketplace](042-photographer-marketplace.json) | multi | time_slot | tiered | EUR | payments |  |
| 43 | [Nursery / Childcare](043-nursery-childcare.json) | multi | class_capacity | subscription | EUR | inventory, payments, prerequisites, recurrence, waitlist |  |
| 44 | [Parking Space Marketplace](044-parking-space-marketplace.json) | multi | asset | per_hour | EUR | inventory, payments |  |
| 45 | [Freelance Design Marketplace](045-freelance-design-marketplace.json) | multi | project | quote | EUR | payments, prerequisites, quotes | E4 |
| 46 | [Fishing Beat Permits](046-fishing-beat-permits.json) | multi | seat | per_person | EUR | inventory, payments, prerequisites |  |
| 47 | [Community Events Board](047-community-events-board.json) | multi | class_capacity | free | EUR | — |  |
| 48 | [Removals Reverse Auction](048-removals-reverse-auction.json) | multi | time_slot | quote | EUR | payments, prerequisites, quotes | E5 |
| 49 | [Pharmacy Click & Collect](049-pharmacy-click-and-collect.json) | multi | stock_item | per_unit | EUR | inventory, payments, prerequisites |  |
| 50 | [Shared Kitchen Marketplace](050-shared-kitchen-marketplace.json) | multi | room | tiered | EUR | entitlements, inventory, payments, prerequisites, recurrence |  |
| 51 | [Shinjuku Capsule Hotel](051-shinjuku-capsule-hotel.json) | single | room | per_unit | JPY | inventory, payments |  |
| 52 | [Kuwait City Dental](052-kuwait-city-dental.json) | single | staff | fixed | KWD | payments |  |
| 53 | [Percent fee stacked on a cap](053-percent-fee-stacked-on-a-cap.json) | single | time_slot | per_hour | EUR | payments |  |
| 54 | [Odd-percent rounding probe](054-odd-percent-rounding-probe.json) | single | time_slot | fixed | EUR | payments |  |
| 55 | [Prepayment deposit above the total](055-prepayment-deposit-above-the-total.json) | single | time_slot | fixed | EUR | payments |  |
| 56 | [Two tiers both matching](056-two-tiers-both-matching.json) | single | class_capacity | tiered | EUR | payments |  |
| 57 | [Free class with a booking fee](057-free-class-with-a-booking-fee.json) | single | class_capacity | free | EUR | payments |  |
| 58 | [Sliding VAT-inclusive salon](058-sliding-vat-inclusive-salon.json) | single | staff | fixed | EUR | payments | schema gap |
| 59 | [B2B Training (VAT exclusive)](059-b2b-training-vat-exclusive.json) | multi | time_slot | fixed | EUR | payments, prerequisites | schema gap |
| 60 | [Tiered cancellation refunds](060-tiered-cancellation-refunds.json) | single | room | per_unit | EUR | inventory, payments | schema gap |
| 61 | [Reschedule-fee physiotherapy](061-reschedule-fee-physiotherapy.json) | single | staff | fixed | EUR | payments | schema gap |
| 62 | [Gift voucher florist](062-gift-voucher-florist.json) | single | class_capacity | fixed | EUR | entitlements, payments | schema gap |
| 63 | [Split-the-bill supper club](063-split-the-bill-supper-club.json) | single | seat | per_person | EUR | inventory, payments | schema gap |
| 64 | [Deposit forfeited on no-show](064-deposit-forfeited-on-no-show.json) | multi | staff | fixed | EUR | payments, prerequisites |  |
| 65 | [Commission on the net, not the gross](065-commission-on-the-net-not-the-gross.json) | multi | class_capacity | per_person | EUR | payments, prerequisites | schema gap |
| 66 | [Payout schedule to the tenant](066-payout-schedule-to-the-tenant.json) | multi | room | per_unit | EUR | inventory, payments, prerequisites | schema gap |
| 67 | [18+ Wine Tasting](067-18-wine-tasting.json) | single | seat | per_person | EUR | inventory, payments, prerequisites | schema gap |
| 68 | [Senior stylist premium](068-senior-stylist-premium.json) | multi | staff | tiered | EUR | payments | schema gap |
| 69 | [Members-only squash court](069-members-only-squash-court.json) | single | asset | tiered | EUR | entitlements, inventory, payments, prerequisites | schema gap |
| 70 | [Expiring credential kitesurf school](070-expiring-credential-kitesurf-school.json) | single | staff | per_hour | EUR | payments, prerequisites |  |
| 71 | [Language-specific tour guide](071-language-specific-tour-guide.json) | multi | class_capacity | per_person | EUR | payments | schema gap |
| 72 | [Accessible-only bookings](072-accessible-only-bookings.json) | multi | room | fixed | EUR | inventory, payments, prerequisites | schema gap |
| 73 | [Household account (one payer, many users)](073-household-account-one-payer-many-users.json) | single | class_capacity | per_person | EUR | inventory, payments, prerequisites | schema gap |
| 74 | [Corporate account with negotiated rate](074-corporate-account-with-negotiated-rate.json) | multi | seat | tiered | EUR | inventory, payments, prerequisites | schema gap |
| 75 | [Spa Day Package](075-spa-day-package.json) | single | time_slot | tiered | EUR | payments, prerequisites | schema gap |
| 76 | [Room requiring a projector](076-room-requiring-a-projector.json) | multi | room | per_hour | EUR | inventory, payments | schema gap |
| 77 | [Two-person massage (paired staff)](077-two-person-massage-paired-staff.json) | single | staff | per_person | EUR | payments | schema gap |
| 78 | [Airport transfer (A to B)](078-airport-transfer-a-to-b.json) | multi | time_slot | per_unit | EUR | payments | schema gap |
| 79 | [Multi-day festival pass](079-multi-day-festival-pass.json) | multi | seat | tiered | EUR | inventory, payments |  |
| 80 | [Sequential course (8 weeks, one enrolment)](080-sequential-course-8-weeks-one-enrolment.json) | single | class_capacity | fixed | EUR | inventory, payments, recurrence |  |
| 81 | [Waiting-list-only allotment of scarce slots](081-waiting-list-only-allotment-of-scarce-slots.json) | single | time_slot | free | EUR | inventory, prerequisites, waitlist | schema gap |
| 82 | [Overnight shift rota](082-overnight-shift-rota.json) | multi | staff | tiered | EUR | payments, prerequisites |  |
| 83 | [Happy-hour crossing the boundary](083-happy-hour-crossing-the-boundary.json) | single | asset | tiered | EUR | payments | schema gap |
| 84 | [Resource swap mid-booking](084-resource-swap-mid-booking.json) | multi | asset | per_unit | EUR | inventory, payments, prerequisites | schema gap |
| 85 | [Ferry with vehicle decks](085-ferry-with-vehicle-decks.json) | multi | seat | per_person | EUR | inventory, payments, prerequisites | schema gap |
| 86 | [Restaurant turn times by daypart](086-restaurant-turn-times-by-daypart.json) | single | asset | free | EUR | inventory | schema gap |
| 87 | [Cleaner's travel time between jobs](087-cleaner-s-travel-time-between-jobs.json) | multi | staff | per_hour | EUR | payments | schema gap |
| 88 | [Peak-season capacity increase](088-peak-season-capacity-increase.json) | single | class_capacity | per_person | EUR | inventory, payments | schema gap |
| 89 | [Last-minute discount](089-last-minute-discount.json) | multi | time_slot | tiered | EUR | payments | schema gap |
| 90 | [Overbooking-tolerant clinic](090-overbooking-tolerant-clinic.json) | single | staff | fixed | EUR | payments, prerequisites | schema gap |
| 91 | [Opening hours per weekday](091-opening-hours-per-weekday.json) | single | staff | fixed | EUR | payments | schema gap |
| 92 | [Two-week notice with a hard horizon](092-two-week-notice-with-a-hard-horizon.json) | single | staff | fixed | EUR | payments, prerequisites |  |
| 93 | [Per-tenant commission override](093-per-tenant-commission-override.json) | multi | time_slot | fixed | EUR | payments | schema gap |
| 94 | [Tenant-set cancellation policy](094-tenant-set-cancellation-policy.json) | multi | room | per_hour | EUR | inventory, payments |  |
| 95 | [Zero-duration instant service](095-zero-duration-instant-service.json) | single | time_slot | fixed | EUR | payments |  |
| 96 | [Very large party buyout](096-very-large-party-buyout.json) | multi | class_capacity | per_person | EUR | inventory, payments, prerequisites |  |
| 97 | [Free cancellation, paid rebooking](097-free-cancellation-paid-rebooking.json) | single | seat | fixed | EUR | inventory, payments | schema gap |
| 98 | [Deposit that is not part of the price](098-deposit-that-is-not-part-of-the-price.json) | single | asset | per_unit | EUR | inventory, payments, prerequisites |  |
| 99 | [Cross-border marketplace, mixed currencies](099-cross-border-marketplace-mixed-currencies.json) | multi | time_slot | fixed | CHF | payments | schema gap |
| 100 | [Same-day pivot: config swap under load](100-same-day-pivot-config-swap-under-load.json) | single | time_slot | fixed | EUR | payments |  |
