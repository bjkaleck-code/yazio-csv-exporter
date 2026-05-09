import type { Metadata } from "next";
import { Sidebar } from "../components/Sidebar";
import "./globals.css";

export const metadata: Metadata = {
  title: "Fitness Dashboard",
  description: "Lokales Fitness- und Ernaehrungs-Dashboard",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="de">
      <body>
        <Sidebar />
        <div className="app-content">{children}</div>
      </body>
    </html>
  );
}
