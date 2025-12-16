// frontend/src/components/EditLessonModal.tsx
import { useEffect, useState } from "react";
import api from "../api/client";

type Lesson = {
  lesson_id: number;
  lesson_number: number;
  lesson_date: string;
  status?: "scheduled" | "attended" | "leave";
  is_first: boolean;
  is_manual_override?: boolean;
};

type Props = {
  open: boolean;
  onClose: () => void;
  lesson: Lesson | null;
  onSaved?: () => void;
};

export default function EditLessonModal({ open, onClose, lesson, onSaved }: Props) {
  const [date, setDate] = useState<string>("");
  const [isManual, setIsManual] = useState<boolean>(false);
  const [saving, setSaving] = useState(false);
  const [status, setStatus] = useState<"scheduled" | "attended" | "leave">("scheduled");

  useEffect(() => {
    if (lesson) {
      setDate(lesson.lesson_date ?? "");
      setIsManual(!!lesson.is_manual_override);
      setStatus(lesson.status ?? "scheduled");
      setSaving(false);
    }
  }, [lesson]);


  if (!open || !lesson) return null;

  const save = async () => {
    setSaving(true);
    try {
      // 1️⃣ update date + manual override
      const payload: any = {};
      if (date) payload.lesson_date = date;
      payload.is_manual_override = isManual;

      await api.patch(`/lessons/${lesson.lesson_id}`, payload);

      // 2️⃣ update status (SEPARATE endpoint)
      await api.patch(`/lessons/${lesson.lesson_id}/status`, {
        status,
      });

      onSaved?.();
      onClose();
    } catch (err: any) {
      console.error("Edit lesson failed", err?.response ?? err);
      alert("Save failed: " + (err?.response?.data?.detail || err?.message || ""));
    } finally {
      setSaving(false);
    }
  };
  
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
      <div className="bg-white p-4 rounded w-[420px] max-w-full">
        <h3 className="text-lg font-semibold mb-3">Edit Lesson #{lesson.lesson_number}</h3>

        <label className="text-sm block mb-1">Date</label>
        <input type="date" value={date} onChange={e=>setDate(e.target.value)} className="p-2 border w-full mb-3" />

        <label className="inline-flex items-center gap-2 mb-3">
          <input type="checkbox" checked={isManual} onChange={e=>setIsManual(e.target.checked)} />
          <span className="text-sm">Manual override (preserve on regenerate)</span>
        </label>

            <select
              value={status}
              onChange={(e) => setStatus(e.target.value)}
              className="border p-2 rounded w-full"
            >
              <option value="scheduled">Scheduled</option>
              <option value="attended">Attended</option>
              <option value="leave">Leave</option>
            </select>

        <div className="flex justify-end gap-2 mt-4">
          <button onClick={onClose} disabled={saving} className="px-3 py-2 border rounded">Cancel</button>
          <button onClick={save} disabled={saving} className="px-3 py-2 bg-green-600 text-white rounded">
            {saving ? "Saving..." : "Save"}
          </button>
        </div>
      </div>
    </div>
  );
}
