import "@/App.css";
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { Show } from "@clerk/react";
import { Toaster } from "@/components/ui/sonner";
import ClerkAuthProvider from "@/components/auth/ClerkAuthProvider";
import { Layout } from "@/components/Layout";
import AuthPage from "@/pages/AuthPage";
import Studio from "@/pages/Studio";
import NewProject from "@/pages/NewProject";
import Projects from "@/pages/Projects";
import ProjectDetail from "@/pages/ProjectDetail";
import ReviewQueue from "@/pages/ReviewQueue";
import BrandKit from "@/pages/BrandKit";
import Publish from "@/pages/Publish";

const Protected = ({ children }) => (
  <>
    <Show when="signed-in"><Layout>{children}</Layout></Show>
    <Show when="signed-out"><Navigate to="/sign-in" replace /></Show>
  </>
);

function App() {
  return (
    <div className="App">
      <BrowserRouter>
        <ClerkAuthProvider>
          <Routes>
            <Route path="/sign-in/*" element={<AuthPage mode="in" />} />
            <Route path="/sign-up/*" element={<AuthPage mode="up" />} />
            <Route path="/" element={<Protected><Studio /></Protected>} />
            <Route path="/baru/:mode" element={<Protected><NewProject /></Protected>} />
            <Route path="/proyek" element={<Protected><Projects /></Protected>} />
            <Route path="/proyek/:id" element={<Protected><ProjectDetail /></Protected>} />
            <Route path="/review" element={<Protected><ReviewQueue /></Protected>} />
            <Route path="/brand-kit" element={<Protected><BrandKit /></Protected>} />
            <Route path="/publikasi" element={<Protected><Publish /></Protected>} />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </ClerkAuthProvider>
        <Toaster theme="dark" position="top-right" />
      </BrowserRouter>
    </div>
  );
}

export default App;
