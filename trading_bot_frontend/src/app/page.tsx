import Link from 'next/link';

export default function HomePage() {
  return (
    <div className="text-center py-10"> {/* Added some padding */}
      <h1 className="text-4xl font-bold mb-6">Welcome to the Trading Bot</h1>
      <p className="text-lg mb-8 text-gray-300"> {/* Adjusted text color */}
        Manage your automated trading strategies with ease.
      </p>
      <div className="space-x-4"> {/* Added space-x for button spacing */}
        <Link href="/dashboard" className="bg-blue-600 hover:bg-blue-700 text-white font-bold py-3 px-6 rounded-lg text-lg">
          Go to Dashboard
        </Link>
        <Link href="/login" className="bg-gray-600 hover:bg-gray-700 text-white font-bold py-3 px-6 rounded-lg text-lg">
          Login
        </Link>
      </div>
    </div>
  );
}
