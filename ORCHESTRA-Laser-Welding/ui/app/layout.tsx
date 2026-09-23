import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "ORCHESTRA · China Smart Manufacturing",
  description: "Human-centred predictive maintenance dashboard for a laser welding cell.",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
