import React from 'react'
import { Routes, Route } from 'react-router-dom'
import { Layout } from 'antd'
import Navbar from './components/Navbar'
import TTSPage from './pages/TTSPage'
import VideoManager from "./pages/VideoManager"; 
import UploadPage from './pages/UploadPage'
import ManualScreen from './pages/ManualScreen'
import VideoEditor from './pages/VideoEditor'
import WorkflowPage from './pages/WorkflowPage'

const { Header, Content } = Layout

function App() {
  return (
    <Layout className="min-h-screen">
      <Header>
        <Navbar />
      </Header>
      <Content className="p-6">
        <Routes>
          <Route path="/" element={<TTSPage />} />
          <Route path="/tts" element={<TTSPage />} />
          <Route path="/videos" element={<VideoManager />} />
          <Route path="/pdf" element={<UploadPage/>} />
          <Route path="/manual" element={<ManualScreen/>} />
          <Route path="/video-editor" element={<VideoEditor/>} />
          <Route path="/workflow" element={<WorkflowPage/>} />

          {/* 添加更多路由 */}
        </Routes>
      </Content>
    </Layout>
  )
}

export default App 