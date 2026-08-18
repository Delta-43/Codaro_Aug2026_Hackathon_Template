/**
 * Footer reduced to a single pink line at the very bottom. Not a snap point —
 * it trails the last plate so it shows at the foot of that snap screen.
 */
export function Footer() {
  return (
    <footer className="pb-8 pt-2 text-center">
      <p className="text-sm font-medium text-primary">© {new Date().getFullYear()} Service.com</p>
    </footer>
  );
}
