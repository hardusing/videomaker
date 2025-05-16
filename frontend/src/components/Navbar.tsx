import React from 'react'
import { Menu } from 'antd'
import { Link, useLocation } from 'react-router-dom'

const Navbar: React.FC = () => {
  const location = useLocation()

  const items = [
    {
      key: '/',
      label: <Link to="/">PPT笔记提取</Link>,
    },
    {
        key: '/tts',
        label: <Link to="/tts">文本转音频</Link>,  
      },
      {
        key: '/video-manager',
        label: <Link to="/video-manager">视频管理</Link>,
      }
  ]

  return (
    <Menu
      theme="dark"
      mode="horizontal"
      selectedKeys={[location.pathname]}
      items={items}
    />
  )
}

export default Navbar 