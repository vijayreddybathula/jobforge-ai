export default function Home() {
  return (
    <main className="min-h-screen p-8">
      <h1 className="text-4xl font-bold mb-4">JobForge AI</h1>
      <p className="text-lg mb-8">Intelligent job application agent</p>
      <div className="space-y-4">
        <a href="/dashboard" className="block text-blue-600 hover:underline">
          Go to Dashboard
        </a>
        <a href="/resume" className="block text-blue-600 hover:underline">
          Upload Resume
        </a>
        <a href="/preferences" className="block text-blue-600 hover:underline">
          Configure Preferences
        </a>
      </div>
    </main>
  )
}
