import React from "react";
import { Route, Routes } from "react-router-dom";
import SettingsEditor from "./components/pages/SettingsEditor";
import Test from "./components/pages/Test";

function App() {
  return (
    <Routes>
      <Route path="/" element={<SettingsEditor />} />
      <Route path="/:open" element={<SettingsEditor />} />
      <Route path="/test" element={<Test />} />
    </Routes>
  );
}

export default App;
