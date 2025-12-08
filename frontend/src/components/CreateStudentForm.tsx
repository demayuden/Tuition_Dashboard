import { useState } from "react";
import api from "../api/client";

type Props = { onCreated?: () => void };

export default function CreateStudentForm({ onCreated }: Props) {
  const [name, setName] = useState("");
  const [cefr, setCefr] = useState("");
  const [groupName, setGroupName] = useState("");
  const [lessonDay1, setLessonDay1] = useState<number>(0);
  const [lessonDay2, setLessonDay2] = useState<number | "">("");
  const [packageSize, setPackageSize] = useState<number>(4);
  const [startDate, setStartDate] = useState<string>("");

  const clear = () => {
    setName(""); setCefr(""); setGroupName(""); setLessonDay1(0); setLessonDay2(""); setPackageSize(4); setStartDate("");
  };

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    const payload: any = {
      name,
      cefr,
      group_name: groupName,
      lesson_day_1: Number(lessonDay1),
      package_size: Number(packageSize),
      start_date: startDate,
    };
    if (lessonDay2 !== "") payload.lesson_day_2 = Number(lessonDay2);

    try {
      await api.post("/students/", payload);
      clear();
      onCreated?.();
      alert("Student created");
    } catch (err: any) {
      console.error("CREATE STUDENT ERROR (full):", err);
      // axios provides .response, .request, .message
      console.error("err.message:", err.message);
      console.error("err.code:", err.code);
      console.error("err.response:", err?.response);
      console.error("err.request:", err?.request);
      alert("Create failed: " + (err?.response?.data?.detail || err.message || JSON.stringify(err)));
    }
  };

  return (
    <form onSubmit={submit} className="p-4 border rounded bg-white mb-4">
      <div className="grid grid-cols-2 gap-2">
        <input required placeholder="Name" value={name} onChange={e=>setName(e.target.value)} className="p-2 border" />
        <input placeholder="CEFR" value={cefr} onChange={e=>setCefr(e.target.value)} className="p-2 border" />
        <input placeholder="Group" value={groupName} onChange={e=>setGroupName(e.target.value)} className="p-2 border" />
        <select value={lessonDay1} onChange={e=>setLessonDay1(Number(e.target.value))} className="p-2 border">
          <option value={0}>Mon</option>
          <option value={1}>Tue</option>
          <option value={2}>Wed</option>
          <option value={3}>Thu</option>
          <option value={4}>Fri</option>
          <option value={5}>Sat</option>
          <option value={6}>Sun</option>
        </select>
        <select value={lessonDay2} onChange={e=>setLessonDay2(e.target.value === "" ? "" : Number(e.target.value))} className="p-2 border">
          <option value="">(none)</option>
          <option value={0}>Mon</option>
          <option value={1}>Tue</option>
          <option value={2}>Wed</option>
          <option value={3}>Thu</option>
          <option value={4}>Fri</option>
          <option value={5}>Sat</option>
          <option value={6}>Sun</option>
        </select>
        <select value={packageSize} onChange={e=>setPackageSize(Number(e.target.value))} className="p-2 border">
          <option value={4}>4 lessons</option>
          <option value={8}>8 lessons</option>
        </select>
        <input required type="date" value={startDate} onChange={e=>setStartDate(e.target.value)} className="p-2 border" />
      </div>

      <div className="mt-3 flex gap-2">
        <button type="submit" className="px-3 py-2 bg-blue-600 text-white rounded">Create student</button>
        <button type="button" onClick={clear} className="px-3 py-2 border rounded">Clear</button>
      </div>
    </form>
  );
}
