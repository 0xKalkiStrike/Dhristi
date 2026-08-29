import { Route, Routes } from "react-router-dom";
import { AppLayout } from "./layouts/AppLayout";
import { Dashboard } from "./pages/Dashboard";
import { Search } from "./pages/Search";
import { SpeedAnalytics } from "./pages/SpeedAnalytics";
import { Calibration } from "./pages/Calibration";
import { Cameras } from "./pages/Cameras";
import { VehicleDetail } from "./pages/VehicleDetail";

export default function App() {
  return (
    <Routes>
      <Route element={<AppLayout />}>
        <Route index element={<Dashboard />} />
        <Route path="search" element={<Search />} />
        <Route path="vehicle/:uid" element={<VehicleDetail />} />
        <Route path="speed" element={<SpeedAnalytics />} />
        <Route path="calibration" element={<Calibration />} />
        <Route path="cameras" element={<Cameras />} />
      </Route>
    </Routes>
  );
}
