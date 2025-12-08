import { Link } from "react-router-dom";

export default function Welcome() {
  return (
    <div className="flex flex-col items-center justify-center h-screen bg-gray-100">
      <h1 className="text-4xl font-bold mb-6">WELCOME</h1>

      <Link
        to="/dashboard"
        className="px-6 py-3 bg-blue-600 text-white rounded text-lg shadow hover:bg-blue-700 transition"
      >
        Click here to continue
      </Link>
      <Link to="/closures" className="mt-4 px-6 py-3 bg-gray-600 text-white rounded text-lg shadow hover:bg-gray-700 transition">
        Manage Closures
      </Link>
    </div>
  );
}
