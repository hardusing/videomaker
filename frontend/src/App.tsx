import React from 'react'
import { Routes, Route } from 'react-router-dom'
import { Layout } from 'antd'
import Navbar from './components/Navbar'
import ProjectList from './pages/ProjectList'
import TTSPage from './pages/TTSPage'

import UploadPage from './pages/UploadPage'

const { Header, Content } = Layout

function App() {
  return (
    <Layout className="min-h-screen">
      <Header>
        <Navbar />
      </Header>
      <Content className="p-6">
        <Routes>
          <Route path="/" element={<ProjectList />} />
          <Route path="/tts" element={<TTSPage />} />

          <Route path="/pdf" element={<UploadPage/>} />

          {/* 添加更多路由 */}
        </Routes>
      </Content>
    </Layout>
  )
}

export default App 