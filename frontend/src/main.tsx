import React from "react";
import ReactDOM from "react-dom/client";
import { createBrowserRouter, RouterProvider } from "react-router-dom";
import "./index.css";
import App from "./App";
import NewRun from "./pages/NewRun";
import Runs from "./pages/Runs";
import RunView from "./pages/RunView";
import Trends from "./pages/Trends";

const router = createBrowserRouter([
  {
    path: "/",
    element: <App />,
    children: [
      { index: true, element: <NewRun /> },
      { path: "runs", element: <Runs /> },
      { path: "runs/:id", element: <RunView /> },
      { path: "trends", element: <Trends /> },
    ],
  },
]);

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <RouterProvider router={router} />
  </React.StrictMode>
);
