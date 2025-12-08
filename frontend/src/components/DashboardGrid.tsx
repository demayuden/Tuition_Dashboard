import { useEffect, useState } from "react";
import api from "../api/client";
import CreateStudentForm from "./CreateStudentForm";
import EditStudentModal from "./EditStudentModal";
import EditLessonModal from "./EditLessonModal";
import RegeneratePreviewModal from "./RegeneratePreviewModal";

type Lesson = { lesson_id:number, lesson_number:number, lesson_date:string, is_first:boolean, is_manual_override?:boolean };
type PackageType = { package_id:number, package_size:number, payment_status:boolean, lessons:Lesson[] };

export default function DashboardGrid() {
  const [students, setStudents] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);
  const [editingStudent, setEditingStudent] = useState<any | null>(null);
  const [editOpen, setEditOpen] = useState(false);
  const [editingLesson, setEditingLesson] = useState<any | null>(null);
  const [lessonModalOpen, setLessonModalOpen] = useState(false);
  const [previewPkgId, setPreviewPkgId] = useState<number | null>(null);
  const [previewOpen, setPreviewOpen] = useState(false);
  const [previewCurrentLessons, setPreviewCurrentLessons] = useState<any[]>([]);


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
      await api.post(`/students/packages/${pkgId}/regenerate`);
      await load();
      alert("Regenerated");
    } catch (e:any) {
      console.error("regenerate error", e);
      if (e?.response?.status === 404) {
        alert("Regenerate endpoint not found on backend. Add /students/packages/{id}/regenerate route.");
      } else {
        alert("Regeneration failed");
      }
    }
  };
  const createPackage = async (studentId: number, size: number) => {
  try {
    await api.post(`/students/${studentId}/packages?package_size=${size}`);
    await load(); // refresh list after creation
    alert(`Created ${size}-lesson package`);
  } catch (err:any) {
    console.error("createPackage error", err);
    alert("Create package failed: " + (err?.response?.data?.detail || err?.message || ""));
  }
};
  const openPreview = (pkg: any) => {
    if (!pkg) return;
    // prepare current lessons array from pkg.lessons
    const current = (pkg.lessons ?? []).map((l:any) => ({
      lesson_number: l.lesson_number,
      lesson_date: l.lesson_date,
      is_manual_override: l.is_manual_override,
      is_first: l.is_first
    }));
    setPreviewCurrentLessons(current);
    setPreviewPkgId(pkg.package_id);
    setPreviewOpen(true);
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
              // BE CAREFUL: backend returns student.student_id, packages[].package_id etc.
              const studentKey = s.student_id ?? s.id;
              const pkg:PackageType | undefined = s.packages?.[0];
              const lessons = pkg?.lessons ?? [];
              return (
                <tr key={studentKey}>
                  <td className="border px-2">{s.name}</td>
                  <td className="border px-2">{s.cefr}</td>
                  <td className="border px-2">{s.group_name}</td>
                  <td className="border px-2">
                    {s.lesson_day_2 !== null && s.lesson_day_2 !== undefined ? `${s.lesson_day_1}, ${s.lesson_day_2}` : `${s.lesson_day_1}`}
                  </td>
                  <td className="border px-2">{s.package_size}</td>

                  {Array.from({ length: 8 }).map((_, idx) => {
                  const lesson = lessons.find((l:any) => l.lesson_number === idx+1);
                  const isManual = !!lesson?.is_manual_override;
                  const color = lesson?.is_first && pkg && !pkg.payment_status ? "text-red-600 font-semibold" : "";
                  return (
                    <td
                      key={idx}
                      className={`border px-2 ${color} ${lesson ? "cursor-pointer hover:bg-gray-50" : ""} relative`}
                      onClick={() => {
                        if (lesson) {
                          setEditingLesson(lesson);
                          setLessonModalOpen(true);
                        }
                      }}
                      title={lesson ? (isManual ? "Manual override — preserved on regenerate" : `Lesson date: ${lesson.lesson_date}`) : ""}
                    >
                      <div className="flex items-center justify-between">
                        <div>{lesson ? lesson.lesson_date : ""}</div>
                        {isManual && (
                          <div className="ml-2 text-xs px-1 py-[2px] rounded bg-yellow-100 text-yellow-800 border border-yellow-200" style={{ lineHeight: 1 }}>
                            M
                          </div>
                        )}
                      </div>
                    </td>
                  );
                })}

                  <td className="border px-2">{pkg ? (pkg.payment_status ? "Paid" : "Unpaid") : ""}</td>

                  <td className="border px-2 space-x-2">
                    {pkg && (
                      <>
                        <button onClick={() => togglePayment(pkg.package_id, !pkg.payment_status)} className="px-2 py-1 text-sm bg-indigo-600 text-white rounded">
                          {pkg.payment_status ? "Mark Unpaid" : "Mark Paid"}
                        </button>
                        <button onClick={() => openPreview(pkg)} className="px-2 py-1 text-sm border rounded">Regenerate</button>
                      </>
                    )}

                    {/* EDIT button (opens modal) */}
                    <button
                      onClick={() => { setEditingStudent(s); setEditOpen(true); }}
                      className="ml-2 px-2 py-1 text-sm border rounded"
                    >
                      Edit
                    </button>
                    
                    {/* Add Package buttons */}
                    <button onClick={() => createPackage(s.student_id, 4)} className="ml-2 px-2 py-1 text-sm border rounded">Add 4</button>
                    <button onClick={() => createPackage(s.student_id, 8)} className="ml-2 px-2 py-1 text-sm border rounded">Add 8</button>

                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      {/* Edit modal */}
      <EditStudentModal
        open={editOpen}
        onClose={() => { setEditOpen(false); setEditingStudent(null); }}
        student={editingStudent}
        onSaved={() => load()}
      />
      <EditLessonModal
        open={lessonModalOpen}
        onClose={() => { setLessonModalOpen(false); setEditingLesson(null); }}
        lesson={editingLesson}
        onSaved={() => load()}
      />
      <RegeneratePreviewModal
        open={previewOpen}
        onClose={() => { setPreviewOpen(false); setPreviewPkgId(null); setPreviewCurrentLessons([]); }}
        packageId={previewPkgId}
        currentLessons={previewCurrentLessons}
        onCommitted={() => { load(); }}
      />
    </div>
  );
}
