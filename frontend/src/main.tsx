import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import { Toaster } from "sonner";
import "@fontsource/plus-jakarta-sans/latin-400.css";
import "@fontsource/plus-jakarta-sans/latin-500.css";
import "@fontsource/plus-jakarta-sans/latin-600.css";
import "@fontsource/plus-jakarta-sans/latin-700.css";
import "@fontsource/plus-jakarta-sans/latin-800.css";
import App from "./App";
import { ThemeProvider } from "./hooks/use-theme";
import "./index.css";

// Dark-first default before paint
if (localStorage.getItem("bahidesk-theme") !== "light") {
  document.documentElement.classList.add("dark");
}

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <ThemeProvider>
      <BrowserRouter basename="/dashboard">
        <App />
        <Toaster
          theme="system"
          position="bottom-right"
          richColors
          closeButton
          toastOptions={{
            className: "font-sans",
          }}
        />
      </BrowserRouter>
    </ThemeProvider>
  </React.StrictMode>
);
