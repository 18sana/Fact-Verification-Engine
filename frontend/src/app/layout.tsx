import type { Metadata } from 'next';
import './globals.css';

export const metadata: Metadata = {
  title: 'Fact-Verification Engine',
  description: 'Autonomous multi-agent fact verification with adversarial debate',
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="font-sans min-h-screen">{children}</body>
    </html>
  );
}
