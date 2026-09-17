import type { Metadata } from "next";
import "./globals.css";
export const metadata: Metadata = {
  title: "ShopPilot AI — Find your next favorite",
  description:
    "A thoughtful shopping assistant. Discover, compare, and shop with confidence.",
};
export default function Layout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
