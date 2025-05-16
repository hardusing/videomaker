import React, { useState, useEffect } from "react";
import axios from "axios";
import { Routes, Route } from 'react-router-dom';
import Navbar from './components/Navbar';
import ProjectList from './pages/ProjectList';
import TTSPage from './pages/TTSPage';
import VideoManager from './pages/video-manager';

const App: React.FC = () => {
  return (
    <div className="min-h-screen bg-gray-100">
      <Navbar />
      <div className="container mx-auto py-6">
        <Routes>
          <Route path="/" element={<ProjectList />} />
          <Route path="/tts" element={<TTSPage />} />
          <Route path="/video-manager" element={<VideoManager />} />
        </Routes>
      </div>
    </div>
  );
};

export default App;
