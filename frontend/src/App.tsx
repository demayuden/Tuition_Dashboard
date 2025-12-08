import { BrowserRouter, Routes, Route } from "react-router-dom";
import Welcome from "./components/Welcome";
import DashboardGrid from "./components/DashboardGrid";

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Welcome />} />
        <Route path="/dashboard" element={<DashboardGrid />} />
      </Routes>
    </BrowserRouter>
  );
}
