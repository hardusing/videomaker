import React from 'react'
import { Menu } from 'antd'
import { Link, useLocation } from 'react-router-dom'

const Navbar: React.FC = () => {
  const location = useLocation()

  const items = [
    {
        key: '/',
        label: <Link to="/">テキスト音声変換</Link>,  
      },
    {
        key: '/videos',
        label: <Link to="/videos">動画変換</Link>,  
      }
      ,
    {
        key: '/pdf',
        label: <Link to="/pdf">PDFから写真生成</Link>,  
      },
       {
        key: '/manual',
        label: <Link to="/manual">マニュアル</Link>,  
      },
      {
        key: '/video-editor',
        label: <Link to="/video-editor">视频编辑器</Link>,  
      },
      {
        key: '/workflow',
        label: <Link to="/workflow">PPT工作流</Link>,  
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