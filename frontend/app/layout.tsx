import type { ReactNode } from "react";

import { auth } from "@/auth";
import { Nav } from "@/components/nav";
import { Providers } from "@/components/providers";

import "./globals.css";

export default async function RootLayout({ children }: { children: ReactNode }) {
  const session = await auth();

  return (
    <html lang="en">
      <body>
        <Providers session={session}>
          <div className="shell">
            <Nav session={session} />
            <main className="content">{children}</main>
          </div>
        </Providers>
      </body>
    </html>
  );
}
