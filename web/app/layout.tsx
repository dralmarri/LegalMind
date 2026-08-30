import type { Metadata } from 'next';
import { Cairo } from 'next/font/google';
import './globals.css';

const cairo = Cairo({
  subsets: ['arabic', 'latin'],
  weight: ['400', '500', '600', '700', '800'],
  variable: '--font-cairo',
  display: 'swap',
});

export const metadata: Metadata = {
  title: 'صوت العدالة الذكي',
  icons: { icon: '/favicon.png', apple: '/brand-192.png' },
  description: 'منصة إدارة المعرفة القانونية الكويتية',
};

// تهيئة الوضع (فاتح/داكن) قبل الرسم لتفادي الوميض
const themeInit = `(function(){try{var t=localStorage.getItem('lm-theme');if(t==='dark'||(!t&&window.matchMedia('(prefers-color-scheme: dark)').matches)){document.documentElement.classList.add('dark');}}catch(e){}})();`;

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="ar" dir="rtl" className={cairo.variable}>
      <head>
        <script dangerouslySetInnerHTML={{ __html: themeInit }} />
      </head>
      <body>{children}</body>
    </html>
  );
}
