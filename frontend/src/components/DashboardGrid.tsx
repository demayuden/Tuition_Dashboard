// frontend/src/components/Dashboard.tsx
import { useEffect, useMemo, useState } from "react";
import api from "../api/client";
import CreateStudentForm from "./CreateStudentForm";
import EditStudentModal from "./EditStudentModal";
import EditLessonModal from "./EditLessonModal";
import RegeneratePreviewModal from "./RegeneratePreviewModal";

type Lesson = {
  lesson_id: number;
  lesson_number: number;
  lesson_date: string;
  is_first: boolean;
  is_manual_override?: boolean;
};

type PackageType = {
  package_id: number;
  package_size: number;
  payment_status: boolean;
  first_lesson_date?: string | null;
  lessons?: Lesson[];
};

type StudentType = {
  student_id: number;
  name: string;
  cefr?: string;
  group_name?: string;
  lesson_day_1: number;
  lesson_day_2?: number | null;
  package_size: number;
  start_date?: string | null;
  end_date?: string | null;
  status?: string;
  packages?: PackageType[];
};

function ConfirmModal({
  open,
  title,
  message,
  onCancel,
  onConfirm,
}: {
  open: boolean;
  title: string;
  message: string;
  onCancel: () => void;
  onConfirm: () => void;
}) {
  if (!open) return null;
  return (
    <div className="fixed inset-0 bg-black/40 z-50 flex items-center justify-center p-4">
      <div className="bg-white rounded-lg shadow-lg p-6 w-[420px]">
        <h2 className="text-xl font-semibold mb-3">{title}</h2>
        <p className="mb-6 text-gray-700">{message}</p>

        <div className="flex justify-end gap-3">
          <button
            onClick={onCancel}
            className="px-4 py-2 rounded border border-gray-300 hover:bg-gray-100"
          >
            Cancel
          </button>

          <button
            onClick={onConfirm}
            className="px-4 py-2 rounded bg-red-600 text-white hover:bg-red-700"
          >
            Confirm
          </button>
        </div>
      </div>
    </div>
  );
}

export default function Dashboard() {
  const [students, setStudents] = useState<StudentType[]>([]);
  const [loading, setLoading] = useState(false);

  // Modals / editing
  const [editingStudent, setEditingStudent] = useState<StudentType | null>(null);
  const [editOpen, setEditOpen] = useState(false);

  const [editingLesson, setEditingLesson] = useState<Lesson | null>(null);
  const [lessonModalOpen, setLessonModalOpen] = useState(false);

  const [previewPkgId, setPreviewPkgId] = useState<number | null>(null);
  const [previewOpen, setPreviewOpen] = useState(false);
  const [previewCurrentLessons, setPreviewCurrentLessons] = useState<Lesson[]>([]);

  // Delete student modal
  const [confirmOpen, setConfirmOpen] = useState(false);
  const [studentToDelete, setStudentToDelete] = useState<StudentType | null>(null);
  const [deletingId, setDeletingId] = useState<number | null>(null);

  // Filters
  const [tab, setTab] = useState<"all" | "4" | "8">("all");
  const [groupFilter, setGroupFilter] = useState<string>("all");
  const [dayFilter, setDayFilter] = useState<string>("all");

  const load = async () => {
    setLoading(true);
    try {
      const res = await api.get("/students/");
      setStudents(res.data || []);
    } catch (err) {
      console.error("Failed to load students", err);
      alert("Failed to load students");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
  }, []);

  // compute groups list
  const groups = useMemo(() => {
    const setGroups = new Set<string>();
    for (const s of students) if (s.group_name) setGroups.add(s.group_name);
    return Array.from(setGroups).sort();
  }, [students]);

  const dayLabel = (n: number) =>
    ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"][n] ?? `${n}`;

  const studentMatchesFilters = (s: StudentType) => {
    if (groupFilter !== "all" && s.group_name !== groupFilter) return false;

    if (dayFilter !== "all") {
      const dayNum = Number(dayFilter);
      const d1 = Number(s.lesson_day_1);
      const d2 =
        s.lesson_day_2 !== null && s.lesson_day_2 !== undefined
          ? Number(s.lesson_day_2)
          : null;
      if (d1 !== dayNum && d2 !== dayNum) return false;
    }
    return true;
  };

  // Build flat rows (one row per package). Keep order stable: students by name, packages by first_lesson_date
  const rows = useMemo(() => {
    const flat: Array<{ key: string; student: StudentType; pkg: PackageType | null; isFirstForStudent: boolean }> = [];

    const filtered = students.filter(s => {
      // student-level filters
      return studentMatchesFilters(s);
    });

    // order students by name
    filtered.sort((a, b) => (a.name || "").localeCompare(b.name || ""));

    for (const s of filtered) {
      const pkgs = (s.packages ?? []).slice(); // copy
      // sort packages by first_lesson_date if present, otherwise by package_id
      pkgs.sort((a, b) => {
        const da = a.first_lesson_date ?? "";
        const db = b.first_lesson_date ?? "";
        if (da !== db) return da.localeCompare(db);
        return (a.package_id ?? 0) - (b.package_id ?? 0);
      });

      if (pkgs.length === 0) {
        // no packages - show a blank package row (pkg null)
        flat.push({
          key: `s-${s.student_id}-nopkg`,
          student: s,
          pkg: null,
          isFirstForStudent: true,
        });
        continue;
      }

      pkgs.forEach((pkg, idx) => {
        // apply tab filters (4 / 8)
        const sz = Number(pkg.package_size);
        if (tab === "4" && sz !== 4) return;
        if (tab === "8" && sz !== 8) return;

        flat.push({
          key: `s-${s.student_id}-p-${pkg.package_id}`,
          student: s,
          pkg,
          isFirstForStudent: idx === 0,
        });
      });
    }

    return flat;
  }, [students, tab, groupFilter, dayFilter]);

  // Actions
  const togglePayment = async (pkgId: number, paid: boolean) => {
    try {
      const url = paid
        ? `/students/packages/${pkgId}/mark_paid`
        : `/students/packages/${pkgId}/mark_unpaid`;
      await api.post(url);
      await load();
    } catch (err) {
      console.error("togglePayment error", err);
      alert("Toggle payment failed");
    }
  };

  const openPreview = (pkg: PackageType | null) => {
    if (!pkg) return;
    const current = (pkg.lessons ?? []).map((l: any) => ({
      lesson_number: l.lesson_number,
      lesson_date: l.lesson_date,
      is_manual_override: l.is_manual_override,
      is_first: l.is_first,
    }));

    setPreviewCurrentLessons(current);
    setPreviewPkgId(pkg.package_id);
    setPreviewOpen(true);
  };

  const exportExcel = async () => {
    try {
      const params = new URLSearchParams();
      params.append("tab", tab);

      if (groupFilter !== "all") params.append("group", groupFilter);
      if (dayFilter !== "all") params.append("day", dayFilter);

      const url = `/export/dashboard.xlsx?${params.toString()}`;
      const res = await api.get(url, { responseType: "blob" });

      const blobUrl = window.URL.createObjectURL(new Blob([res.data]));
      const a = document.createElement("a");
      a.href = blobUrl;

      const fileSuffix =
        tab === "4" ? "4-lesson" : tab === "8" ? "8-lesson" : "all";

      a.download = `tuition_dashboard_${fileSuffix}.xlsx`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      window.URL.revokeObjectURL(blobUrl);
    } catch (err: any) {
      console.error("Export failed", err);
      alert("Export failed: " + (err?.response?.data?.detail || err.message));
    }
  };

  // Delete student flow (modal)
  const deleteStudentConfirmed = async () => {
    if (!studentToDelete) return;
    const sid = studentToDelete.student_id;
    try {
      setDeletingId(sid);
      await api.delete(`/students/${sid}`);
      await load();
    } catch (err: any) {
      console.error("Delete student failed", err);
      alert("Delete failed: " + (err?.response?.data?.detail || err?.message || ""));
    } finally {
      setDeletingId(null);
      setConfirmOpen(false);
      setStudentToDelete(null);
    }
  };

  // helper to render lesson map for a package
  const lessonMapFor = (pkg: PackageType | null) => {
    const map: Record<number, string> = {};
    if (!pkg) return map;
    for (const l of pkg.lessons ?? []) {
      map[l.lesson_number] = l.lesson_date;
    }
    return map;
  };

  // UI
  const maxCols = tab === "4" ? 4 : tab === "8" ? 8 : 8;
  const totalCols = 5 + maxCols + 2; // name, cefr, group, day, package, lessons..., paid, actions

  return (
    <div className="p-6">
      {/* Back Button */}
      <div className="mb-4">
        <button
          onClick={() => (window.location.href = "/")}
          className="text-blue-600 hover:text-blue-800 transition-transform duration-200 hover:-translate-x-1"
        >
          <span className="text-4xl">←</span>
        </button>
      </div>

      <div className="flex items-center justify-between mb-4">
        <h1 className="text-2xl font-semibold">Tuition Dashboard</h1>

        <button
          onClick={exportExcel}
          className="px-3 py-2 bg-blue-600 text-white rounded hover:bg-blue-700 hover:scale-[1.03] transition-all"
        >
          Export Excel
        </button>
      </div>

      <CreateStudentForm onCreated={load} />

      {/* Filters */}
      <div className="mt-4 mb-3 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
        <div className="flex items-center gap-2">
          <div className="flex items-center bg-gray-50 rounded p-1">
            <button
              onClick={() => setTab("all")}
              className={`px-3 py-1 rounded ${tab === "all" ? "bg-white shadow" : "text-gray-600"}`}
            >
              All
            </button>
            <button
              onClick={() => setTab("4")}
              className={`px-3 py-1 rounded ${tab === "4" ? "bg-white shadow" : "text-gray-600"}`}
            >
              4-lesson
            </button>
            <button
              onClick={() => setTab("8")}
              className={`px-3 py-1 rounded ${tab === "8" ? "bg-white shadow" : "text-gray-600"}`}
            >
              8-lesson
            </button>
          </div>

          <div className="ml-4">
            <label className="text-xs block mb-1">Group</label>
            <select value={groupFilter} onChange={(e) => setGroupFilter(e.target.value)} className="p-2 border rounded">
              <option value="all">All groups</option>
              {groups.map((g) => (
                <option key={g} value={g}>{g}</option>
              ))}
            </select>
          </div>

          <div className="ml-4">
            <label className="text-xs block mb-1">Day</label>
            <select value={dayFilter} onChange={(e) => setDayFilter(e.target.value)} className="p-2 border rounded">
              <option value="all">All days</option>
              <option value="0">Mon</option>
              <option value="1">Tue</option>
              <option value="2">Wed</option>
              <option value="3">Thu</option>
              <option value="4">Fri</option>
              <option value="5">Sat</option>
              <option value="6">Sun</option>
            </select>
          </div>
        </div>

        <div className="text-sm text-gray-600">
          Showing {rows.length} rows • Students: {students.length}
        </div>
      </div>

      {/* TABLE */}
      <div className="overflow-auto bg-white border rounded">
        <table className="min-w-full text-sm">
          <thead className="bg-gray-100">
            <tr>
              <th className="border px-2">Name</th>
              <th className="border px-2">CEFR</th>
              <th className="border px-2">Group</th>
              <th className="border px-2">Lesson Days</th>
              <th className="border px-2">Package</th>

              {Array.from({ length: maxCols }).map((_, i) => (
                <th key={i} className="border px-2">{i + 1}</th>
              ))}

              <th className="border px-2">Paid</th>
              <th className="border px-2">Actions</th>
            </tr>
          </thead>

          <tbody>
            {rows.map((row) => {
              const s = row.student;
              const pkg = row.pkg;
              const lessonsMap = lessonMapFor(pkg);
              const sid = s.student_id;

              return (
                <tr key={row.key}>
                  <td className="border px-2">{row.isFirstForStudent ? s.name : ""}</td>
                  <td className="border px-2">{row.isFirstForStudent ? s.cefr : ""}</td>
                  <td className="border px-2">{row.isFirstForStudent ? s.group_name : ""}</td>
                  <td className="border px-2">
                    {row.isFirstForStudent
                      ? s.lesson_day_2 !== null && s.lesson_day_2 !== undefined
                        ? `${dayLabel(s.lesson_day_1)}, ${dayLabel(s.lesson_day_2)}`
                        : `${dayLabel(s.lesson_day_1)}`
                      : ""}
                  </td>

                  <td className="border px-2">{pkg ? pkg.package_size : ""}</td>

                  {Array.from({ length: maxCols }).map((_, idx) => {
                    const lesson = pkg?.lessons?.find(l => l.lesson_number === idx + 1);
                    const isManual = !!lesson?.is_manual_override;
                    const color = lesson?.is_first && pkg && !pkg.payment_status ? "text-red-600 font-semibold" : "";

                    return (
                      <td
                        key={idx}
                        className={`border px-2 ${lesson ? "cursor-pointer" : ""} ${color}`}
                        onClick={() => {
                          if (lesson) {
                            setEditingLesson(lesson);
                            setLessonModalOpen(true);
                          }
                        }}
                      >
                        <div className="flex items-center justify-between">
                          <div>{lesson ? lesson.lesson_date : ""}</div>
                          {isManual && (
                            <div className="text-xs px-1 py-[1px] bg-yellow-100 border border-yellow-200 text-yellow-700 rounded">
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
                        <button
                          onClick={() => togglePayment(pkg.package_id, !pkg.payment_status)}
                          disabled={deletingId === sid}
                          className="px-2 py-1 text-sm bg-indigo-600 text-white rounded hover:bg-indigo-700"
                        >
                          {pkg.payment_status ? "Mark Unpaid" : "Mark Paid"}
                        </button>

                        <button
                          onClick={() => openPreview(pkg)}
                          disabled={deletingId === sid}
                          className="px-2 py-1 text-sm border rounded hover:bg-gray-50"
                        >
                          Regenerate
                        </button>
                      </>
                    )}

                    {row.isFirstForStudent && (
                      <>
                        <button
                          onClick={() => {
                            setEditingStudent(s);
                            setEditOpen(true);
                          }}
                          disabled={deletingId === sid}
                          className="px-2 py-1 text-sm border rounded hover:bg-blue-50"
                        >
                          Edit
                        </button>

                        <button
                          onClick={() => {
                            setStudentToDelete(s);
                            setConfirmOpen(true);
                          }}
                          disabled={deletingId === sid}
                          className="px-2 py-1 text-sm bg-red-600 text-white rounded hover:bg-red-700"
                        >
                          {deletingId === sid ? "Deleting..." : "Delete"}
                        </button>
                      </>
                    )}
                  </td>
                </tr>
              );
            })}

            {rows.length === 0 && (
              <tr>
                <td className="p-4" colSpan={totalCols}>
                  No rows match the current filters.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      {/* Edit student modal */}
      <EditStudentModal
        open={editOpen}
        onClose={() => {
          setEditOpen(false);
          setEditingStudent(null);
        }}
        student={editingStudent}
        onSaved={() => load()}
      />

      {/* Edit lesson modal */}
      <EditLessonModal
        open={lessonModalOpen}
        onClose={() => {
          setLessonModalOpen(false);
          setEditingLesson(null);
        }}
        lesson={editingLesson}
        onSaved={() => load()}
      />

      {/* Regenerate preview modal */}
      <RegeneratePreviewModal
        open={previewOpen}
        onClose={() => {
          setPreviewOpen(false);
          setPreviewPkgId(null);
          setPreviewCurrentLessons([]);
        }}
        packageId={previewPkgId}
        currentLessons={previewCurrentLessons}
        onCommitted={() => load()}
      />

      {/* Delete student confirm modal */}
      <ConfirmModal
        open={confirmOpen}
        title="Delete Student?"
        message={`Are you sure you want to delete "${studentToDelete?.name}"? This action cannot be undone.`}
        onCancel={() => {
          setConfirmOpen(false);
          setStudentToDelete(null);
        }}
        onConfirm={deleteStudentConfirmed}
      />
    </div>
  );
}
