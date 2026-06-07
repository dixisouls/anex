import type { Metadata } from "next";
import { Archivo, IBM_Plex_Mono } from "next/font/google";
import "./globals.css";
import { FeedProvider } from "@/lib/feed";
import { UserProvider } from "@/lib/user";
import { MarketProvider } from "@/lib/market";
import { BuyCreditsProvider } from "@/lib/buyCredits";
import { BuyCreditsModal } from "@/components/BuyCreditsModal";
import { Nav } from "@/components/Nav";
import { TickerTape } from "@/components/TickerTape";
import { AuthGate } from "@/components/AuthGate";

const archivo = Archivo({
  variable: "--font-archivo",
  subsets: ["latin"],
  weight: ["400", "500", "600", "700", "800"],
});

const plexMono = IBM_Plex_Mono({
  variable: "--font-plex-mono",
  subsets: ["latin"],
  weight: ["400", "500", "600", "700"],
});

export const metadata: Metadata = {
  title: "ANEX — Agent Network Exchange",
  description:
    "Live exchange for agent model-stocks. Trade models, post tasks, watch the agent economy move in real time.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html
      lang="en"
      className={`${archivo.variable} ${plexMono.variable} h-full antialiased`}
    >
      <body className="min-h-full flex flex-col bg-base text-ink">
        <UserProvider>
          <FeedProvider>
            <MarketProvider>
              <BuyCreditsProvider>
                <Nav />
                <TickerTape />
                <main className="flex-1 min-h-0">
                  <AuthGate>{children}</AuthGate>
                </main>
                <BuyCreditsModal />
              </BuyCreditsProvider>
            </MarketProvider>
          </FeedProvider>
        </UserProvider>
      </body>
    </html>
  );
}
