import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { App } from "./app/App";
import "@fontsource/oswald/500.css";
import "@fontsource/oswald/600.css";
import "./styles.css";
import "./season.css";
import "./game.css";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
