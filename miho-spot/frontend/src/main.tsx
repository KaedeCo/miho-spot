// MUST be first: TDesign React 19 compatibility adapter
import "tdesign-react/es/_util/react-19-adapter";

import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import App from "./App";
import "./index.css";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <App />
  </StrictMode>
);
