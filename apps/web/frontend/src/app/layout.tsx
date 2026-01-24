import './globals.css'

export const metadata = {
  title: 'JobForge AI',
  description: 'Intelligent job application agent',
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  )
}
