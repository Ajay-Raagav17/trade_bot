import type { Metadata } from "next";
// Removed Inter import from here as it's handled in RootClientLayout
import "./globals.css";
import RootClientLayout from "@/components/layout/RootClientLayout";

export const metadata: Metadata = {
  title: "Trading Bot Dashboard",
  description: "Frontend for the Binance Trading Bot",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className="bg-gray-900 text-gray-100">
      {/* Removed inter.className from body as it's applied in RootClientLayout */}
      <body>
        <RootClientLayout>{children}</RootClientLayout>
      </body>
    </html>
  );
}
