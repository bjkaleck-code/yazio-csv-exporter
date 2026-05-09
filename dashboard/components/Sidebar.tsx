import Link from "next/link";

const NAV_ITEMS = [
  { href: "/", label: "Analyse" },
  { href: "/import-log", label: "Import-Log" },
  { href: "/source-data", label: "Quelldaten" },
];

export function Sidebar() {
  return (
    <>
      <aside className="sidebar">
        <Link className="brand" href="/">
          Fitness Dashboard
        </Link>
        <nav aria-label="Dashboard Navigation">
          {NAV_ITEMS.map((item) => (
            <Link href={item.href} key={item.href}>
              {item.label}
            </Link>
          ))}
        </nav>
      </aside>
      <details className="mobile-nav">
        <summary aria-label="Menü öffnen">
          <span />
          <span />
          <span />
        </summary>
        <nav aria-label="Mobile Dashboard Navigation">
          {NAV_ITEMS.map((item) => (
            <Link href={item.href} key={item.href}>
              {item.label}
            </Link>
          ))}
        </nav>
      </details>
    </>
  );
}
