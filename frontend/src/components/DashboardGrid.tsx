import { useEffect, useState } from "react";
import api from "../api/client";
import CreateStudentForm from "./CreateStudentForm";

type Lesson = { id:number, lesson_number:number, lesson_date:string, is_first:boolean, is_manual_override?:boolean };
type PackageType = { id:number, package_size:number, payment_status:boolean, lessons:Lesson[] };

export default function DashboardGrid() {
  const [students, setStudents] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);

  const load = async () => {
    setLoading(true);
    try {
      const res = await api.get("/students");
      setStudents(res.data);
    } finally { setLoading(false); }
  };

  useEffect(() => { load(); }, []);

   const togglePayment = async (pkgId:number, paid:boolean) => {
    try {
      // Backend exposes mark_paid / mark_unpaid under /students/packages/{id}
      const url = paid
        ? `/students/packages/${pkgId}/mark_paid`
        : `/students/packages/${pkgId}/mark_unpaid`;

      await api.post(url);
      await load(); // refresh list
    } catch (e) {
      console.error("togglePayment error", e);
      alert("Toggle payment failed");
    }
  };

  const regenerate = async (pkgId:number) => {
    if (!confirm("Regenerate lessons for this package? This will overwrite non-manual lessons.")) return;
    try {
      // If your backend has regenerate endpoint at /students/packages/{id}/regenerate
      // otherwise create it in backend or call the proper path.
      await api.post(`/students/packages/${pkgId}/regenerate`);
      await load();
      alert("Regenerated");
    } catch (e) {
      console.error("regenerate error", e);
      // helpful message if backend endpoint missing
      if (e?.response?.status === 404) {
        alert("Regenerate endpoint not found on backend. Add /students/packages/{id}/regenerate route.");
      } else {
        alert("Regeneration failed");
      }
    }
  };

  return (
    <div className="p-6">
      <h1 className="text-2xl font-semibold mb-4">Tuition Dashboard</h1>

      <CreateStudentForm onCreated={load} />

      <div className="mb-3 text-sm text-gray-600">Status: {loading ? "loading…" : "idle"}</div>

      <div className="overflow-auto bg-white border rounded">
        <table className="min-w-full text-sm">
          <thead className="bg-gray-100">
            <tr>
              <th className="border px-2">Name</th>
              <th className="border px-2">CEFR</th>
              <th className="border px-2">Group</th>
              <th className="border px-2">Lesson Days</th>
              <th className="border px-2">Package</th>
              {Array.from({ length: 8 }).map((_, i) => <th key={i} className="border px-2">{i+1}</th>)}
              <th className="border px-2">Paid</th>
              <th className="border px-2">Actions</th>
            </tr>
          </thead>
          <tbody>
            {students.map(s => {
              const pkg:PackageType | undefined = s.packages?.[0];
              const lessons = pkg?.lessons ?? [];
              return (
                <tr key={s.id}>
                  <td className="border px-2">{s.name}</td>
                  <td className="border px-2">{s.cefr}</td>
                  <td className="border px-2">{s.group_name}</td>
                  <td className="border px-2">
                    {s.lesson_day_2 !== null && s.lesson_day_2 !== undefined ? `${s.lesson_day_1}, ${s.lesson_day_2}` : `${s.lesson_day_1}`}
                  </td>
                  <td className="border px-2">{s.package_size}</td>

                  {Array.from({ length: 8 }).map((_, idx) => {
                    const lesson = lessons.find((l:any) => l.lesson_number === idx+1);
                    const color = lesson?.is_first && pkg && !pkg.payment_status ? "text-red-600 font-semibold" : "";
                    return <td key={idx} className={`border px-2 ${color}`}>{lesson ? lesson.lesson_date : ""}</td>;
                  })}

                  <td className="border px-2">{pkg ? (pkg.payment_status ? "Paid" : "Unpaid") : ""}</td>

                  <td className="border px-2 space-x-2">
                    {pkg && (
                      <>
                        <button onClick={() => togglePayment(pkg.id, !pkg.payment_status)} className="px-2 py-1 text-sm bg-indigo-600 text-white rounded">
                          {pkg.payment_status ? "Mark Unpaid" : "Mark Paid"}
                        </button>
                        <button onClick={() => regenerate(pkg.id)} className="px-2 py-1 text-sm border rounded">Regenerate</button>
                      </>
                    )}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
