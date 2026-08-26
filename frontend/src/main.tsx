import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import App from "./App";
import { AuthProvider } from "./auth";
import "antd/dist/reset.css";
import "./styles.css";
import "./operations.css";
import "./theme.css";
import "./admin.css";
import "./analytics.css";
import "./trend.css";
import "./publishing.css";
import "./users.css";
import "./task-list.css";
import "./models.css";
import "./prompts.css";
import "./streaming.css";
import "./responsive-admin.css";

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <BrowserRouter>
      <AuthProvider>
        <App />
      </AuthProvider>
    </BrowserRouter>
  </React.StrictMode>,
);
