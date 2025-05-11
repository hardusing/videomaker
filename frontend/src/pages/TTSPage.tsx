import React, { useEffect, useState } from 'react'
import { Table, Button, message } from 'antd'
import axios from 'axios'

const TTSPage: React.FC = () => {
  const [txtFiles, setTxtFiles] = useState<string[]>([])
  const [audioFiles, setAudioFiles] = useState<string[]>([])
  const [subtitleFiles, setSubtitleFiles] = useState<string[]>([])
  const [loading, setLoading] = useState(false)

  const fetchTxtFiles = async () => {
    try {
      const res = await axios.get('http://localhost:8000/api/tts/texts')
      setTxtFiles(res.data)
    } catch {
      message.error('获取 TXT 文件失败')
    }
  }

  const handleGenerate = async () => {
    setLoading(true)
    try {
      const res = await axios.post('http://localhost:8000/api/tts/generate')
      setAudioFiles(res.data.audio_files)
      setSubtitleFiles(res.data.subtitle_files)
      message.success('音频和字幕生成成功')
    } catch {
      message.error('生成失败')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchTxtFiles()
  }, [])

  const txtColumns = [
    {
      title: '文件名',
      dataIndex: 'name',
      key: 'name',
    },
  ]

  const audioColumns = [
    {
      title: '音频文件',
      dataIndex: 'name',
      key: 'name',
      render: (text: string) => (
        <audio controls src={`http://localhost:8000/static/output2/${text}`} />
      ),
    },
  ]

  const srtColumns = [
    {
      title: '字幕文件',
      dataIndex: 'name',
      key: 'name',
      render: (text: string) => (
        <a
          href={`http://localhost:8000/static/output2/${text}`}
          download
          target="_blank"
          rel="noreferrer"
        >
          {text}
        </a>
      ),
    },
  ]

  return (
    <div style={{ padding: 24 }}>
      <h2>文本转音频与字幕</h2>

      <Button type="primary" onClick={handleGenerate} loading={loading} style={{ marginBottom: 16 }}>
        生成全部音频和字幕
      </Button>

      <h3>原始 TXT 文件</h3>
      <Table
        dataSource={txtFiles.map((f) => ({ key: f, name: f }))}
        columns={txtColumns}
        pagination={false}
      />

      <h3 style={{ marginTop: 32 }}>生成的音频</h3>
      <Table
        dataSource={audioFiles.map((f) => ({ key: f, name: f }))}
        columns={audioColumns}
        pagination={false}
      />

      <h3 style={{ marginTop: 32 }}>生成的字幕</h3>
      <Table
        dataSource={subtitleFiles.map((f) => ({ key: f, name: f }))}
        columns={srtColumns}
        pagination={false}
      />
    </div>
  )
}

export default TTSPage
