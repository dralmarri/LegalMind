import type { Metadata } from 'next';
import './globals.css';

export const metadata: Metadata = {
  title: 'LegalMind | صوت العدالة',
  description: 'منصة إدارة المعرفة القانونية الكويتية',
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="ar" dir="rtl">
      <body>{children}</body>
    </html>
  );
}
