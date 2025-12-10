// frontend/src/components/ClosuresManager.tsx
import { useEffect, useState } from "react";
import api from "../api/client";

type Closure = {
  id: number;
  start_date: string;
  end_date: string;
  reason?: string;
  type?: string;
};

export default function ClosuresManager() {
  const [closures, setClosures] = useState<Closure[]>([]);
  const [loading, setLoading] = useState(false);

  // form state
  const [startDate, setStartDate] = useState("");
  const [endDate, setEndDate] = useState("");
  const [reason, setReason] = useState("");
  const [ctype, setCtype] = useState("");

  const load = async () => {
    setLoading(true);
    try {
      const res = await api.get("/closures/");
      setClosures(res.data);
    } catch (e) {
      console.error("load closures", e);
      alert("Failed to load closures");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(); }, []);

  const create = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!startDate || !endDate) return alert("Start and end date required");
    try {
      await api.post("/closures/", {
        start_date: startDate,
        end_date: endDate,
        reason: reason || null,
        type: ctype || null
      });
      setStartDate(""); setEndDate(""); setReason(""); setCtype("");
      await load();
    } catch (err: any) {
      console.error("create closure", err);
      alert("Create failed: " + (err?.response?.data?.detail || err?.message || ""));
    }
  };

  const remove = async (id: number) => {
    if (!confirm("Delete this closure?")) return;
    try {
      await api.delete(`/closures/${id}`);
      await load();
    } catch (err) {
      console.error("delete closure", err);
      alert("Delete failed");
    }
  };

  return (
    <div className="p-6">
      {/* Back Button */}
      <div className="mb-4">
         <button
          onClick={() => window.location.href = "/"}
          className="text-blue-600 hover:text-blue-800 transition-transform duration-200 hover:-translate-x-1"
        >
          <span className="text-4xl">←</span>
         </button>
      </div>
      <h2 className="text-xl font-semibold mb-3">Closures (Holidays / Breaks)</h2>

      <form onSubmit={create} className="mb-4 grid grid-cols-4 gap-2 items-end">
        <div>
          <label className="text-xs block mb-1">Start</label>
          <input type="date" value={startDate} onChange={e=>setStartDate(e.target.value)} className="p-2 border w-full" />
        </div>
        <div>
          <label className="text-xs block mb-1">End</label>
          <input type="date" value={endDate} onChange={e=>setEndDate(e.target.value)} className="p-2 border w-full" />
        </div>
        <div>
          <label className="text-xs block mb-1">Reason</label>
          <input placeholder="Optional" value={reason} onChange={e=>setReason(e.target.value)} className="p-2 border w-full" />
        </div>
        <div>
          <label className="text-xs block mb-1">Type</label>
          <input placeholder="holiday/term" value={ctype} onChange={e=>setCtype(e.target.value)} className="p-2 border w-full" />
        </div>

        <div className="col-span-4 mt-2">
          <button
            type="submit"
            className="px-3 py-2 bg-green-600 text-white rounded mr-2 
                      hover:bg-green-700 hover:scale-[1.03] transition-all"
          >
            Add Closure
          </button>
          <button
            type="button"
            onClick={() => { setStartDate(""); setEndDate(""); setReason(""); setCtype(""); }}
            className="px-3 py-2 border rounded
                      hover:bg-gray-100 hover:scale-[1.03] transition-all"
          >
            Clear
          </button>
        </div>
      </form>
      <div className="mb-2 text-sm text-gray-600">Status: {loading ? "loading…" : `Loaded ${closures.length}`}</div>

      <div className="bg-white border rounded overflow-auto">
        <table className="min-w-full text-sm">
          <thead className="bg-gray-100">
            <tr>
              <th className="border px-2">ID</th>
              <th className="border px-2">Start</th>
              <th className="border px-2">End</th>
              <th className="border px-2">Reason</th>
              <th className="border px-2">Type</th>
              <th className="border px-2">Actions</th>
            </tr>
          </thead>
          <tbody>
            {closures.map(c => (
              <tr key={c.id}>
                <td className="border px-2">{c.id}</td>
                <td className="border px-2">{c.start_date}</td>
                <td className="border px-2">{c.end_date}</td>
                <td className="border px-2">{c.reason}</td>
                <td className="border px-2">{c.type}</td>
                <td className="border px-2">
                  <button onClick={() => remove(c.id)} className="px-2 py-1 text-sm border rounded">Delete</button>
                </td>
              </tr>
            ))}
            {closures.length === 0 && (
              <tr><td className="p-4" colSpan={6}>No closures defined.</td></tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
