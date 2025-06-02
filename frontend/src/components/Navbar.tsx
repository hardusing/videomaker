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
        key: '/videos',
        label: <Link to="/videos">视频转码</Link>,  
      }
      ,
    {
        key: '/pdf',
        label: <Link to="/pdf">PDFから写真生成</Link>,  
      },
       {
        key: '/manual',
        label: <Link to="/manual">マニュアル</Link>,  
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