import { BrowserRouter, Routes, Route } from "react-router-dom";
import Layout from "./components/Layout";
import Dashboard from "./pages/Dashboard";
import HotTopics from "./pages/HotTopics";
import Keywords from "./pages/Keywords";
import History from "./pages/History";
import Accounts from "./pages/Accounts";
import CheckIdentity from "./pages/CheckIdentity";

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route element={<Layout />}>
          <Route path="/" element={<Dashboard />} />
          <Route path="/topics" element={<HotTopics />} />
          <Route path="/keywords" element={<Keywords />} />
          <Route path="/history" element={<History />} />
          <Route path="/identity" element={<CheckIdentity />} />
          <Route path="/accounts" element={<Accounts />} />
        </Route>
      </Routes>
    </BrowserRouter>
  );
}
