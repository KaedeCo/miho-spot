import { BrowserRouter, Routes, Route } from "react-router-dom";
import Layout from "./components/Layout";
import Dashboard from "./pages/Dashboard";
import HotTopics from "./pages/HotTopics";
import Keywords from "./pages/Keywords";
import History from "./pages/History";
import Accounts from "./pages/Accounts";
import CheckIdentity from "./pages/CheckIdentity";
import Spectrum2D from "./pages/Spectrum2D";
import VideoAnalysis from "./pages/VideoAnalysis";
import WordCloud from "./pages/WordCloud";
import DeepAnalysisPage from "./pages/DeepAnalysis";
import OpinionTimeline from "./pages/OpinionTimeline";
import ClusterAnalysis from "./pages/ClusterAnalysis";
import DebateHall from "./pages/DebateHall";
import DebateReplay from "./pages/DebateReplay";

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
          <Route path="/spectrum" element={<Spectrum2D />} />
          <Route path="/video-analysis" element={<VideoAnalysis />} />
          <Route path="/opinion-timeline" element={<OpinionTimeline />} />
          <Route path="/cluster-analysis" element={<ClusterAnalysis />} />
          <Route path="/word-cloud" element={<WordCloud />} />
          <Route path="/deep-analysis" element={<DeepAnalysisPage />} />
          <Route path="/accounts" element={<Accounts />} />
          <Route path="/debate-hall" element={<DebateHall />} />
          <Route path="/debate-replay" element={<DebateReplay />} />
        </Route>
      </Routes>
    </BrowserRouter>
  );
}
