## Project Notes

#### Description
&nbsp;&nbsp;&nbsp;&nbsp;The idea is to create a template for the Codaro Hackathon which should be adaptable and easy to alter for multiple use cases.

---

&nbsp;&nbsp;&nbsp;&nbsp;For Track B: **Booking and Resource scheduling**

The minimum requirements are :-

- Resource and Slot
- Booking and Confirmation
- Change and Cancellation
- Availability View

As per our discussions and Alban's advice we'll be using a simple Tech Stack -

for the *Frontend* -> \
 `Next.js` + `Tailwind` + `shadcn/ui`
 > For the UI and interface. I would implement the UI to also work as a PWA for a more universal use case, as an app if required

for the *Backend* -> \
 `Python FastAPI`
> To implement the Booking program and user handling and SQL interface. Also to be able to asynchronous processing of simultaneous user interactions

for the *Database* -> \
`Supabase` (PostgresSQL)
> To manage Resources, Slots & Bookings along with User tokens essentially just emails/phones