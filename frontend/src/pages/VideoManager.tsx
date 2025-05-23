import React, { useEffect, useState } from 'react'
import axios from 'axios'
import { saveAs } from 'file-saver'
import {
  Table,
  Button,
  Upload,
  message,
  Progress,
  Tag,
  Space,
  Input,
  Empty,
} from 'antd'
import { UploadOutlined } from '@ant-design/icons'

axios.defaults.baseURL = 'http://localhost:8000'

interface ProgressInfo {
  status: 'processing' | 'completed' | 'failed'
  total: number
  completed: number
  results: Array<{
    input: string
    output?: string
    status: string
    error?: string
  }>
}

const VideoSimplePage: React.FC = () => {
  const [taskName, setTaskName] = useState<string>('')
  const [originalList, setOriginalList] = useState<string[]>([])
  const [transcodedList, setTranscodedList] = useState<string[]>([])
  const [selectedRowKeys, setSelectedRowKeys] = useState<React.Key[]>([])
  const [uploading, setUploading] = useState(false)
  const [transcoding, setTranscoding] = useState(false)
  const [progressInfo, setProgressInfo] = useState<ProgressInfo | null>(null)

  const currentTask = taskName.trim()

  const fetchVideos = async () => {
    if (!currentTask) {
      setOriginalList([])
      setTranscodedList([])
      setSelectedRowKeys([])
      return
    }
    try {
      const res = await axios.get<{
        tasks: Record<string, string[]>
        encoded: Record<string, string[]>
      }>('/api/videos/')

      // 原始列表
      setOriginalList(res.data.tasks[currentTask] || [])

      // 直接使用后端返回的 encoded 文件名数组
      setTranscodedList(res.data.encoded[currentTask] || [])

      setSelectedRowKeys([])
    } catch {
      message.error('获取视频列表失败')
    }
  }

  useEffect(() => {
    fetchVideos()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [currentTask])

  const uploadProps = {
    multiple: true,
    showUploadList: false as any,
    customRequest: async ({ file, onSuccess, onError }: any) => {
      if (!currentTask) {
        message.warning('请先输入任务名称')
        return
      }
      setUploading(true)
      const form = new FormData()
      form.append('files', file as Blob)
      try {
        await axios.post('/api/videos/upload-multiple', form, {
          params: { filename: currentTask },
        })
        message.success(`${file.name} 上传成功`)
        await fetchVideos()
        onSuccess && onSuccess(null, file)
      } catch {
        message.error(`${file.name} 上传失败`)
        onError && onError(new Error(), file)
      } finally {
        setUploading(false)
      }
    },
  }

  const calcPercent = () => {
    if (!progressInfo) return 0
    if (progressInfo.status === 'processing') {
      return Math.floor((progressInfo.completed / progressInfo.total) * 100)
    }
    return 100
  }

  const startTranscode = () => {
    if (!currentTask) {
      message.warning('请先输入任务名称')
      return
    }
    setProgressInfo(null)
    setTranscoding(true)
    setTranscodedList([])
    setSelectedRowKeys([])

    let ignoreFirst = true
    const ws = new WebSocket(
      `ws://localhost:8000/api/videos/ws/transcode/${encodeURIComponent(
        currentTask
      )}`
    )
    ws.onopen = async () => {
      try {
        await axios.post('/api/videos/transcode', null, {
          params: { filename: currentTask },
        })
      } catch {
        message.error('无法开始转码')
        setTranscoding(false)
        ws.close()
      }
    }
    ws.onmessage = (ev) => {
      if (ignoreFirst) {
        ignoreFirst = false
        return
      }
      const data: ProgressInfo = JSON.parse(ev.data)
      setProgressInfo(data)

      // 成功后把 r.output（真实文件名）加入列表
      data.results
        .filter(r => r.status === 'success' && r.output)
        .forEach(r => {
          const encodedName = r.output!  // e.g. "encoded_0519(1).mp4"
          setTranscodedList(prev =>
            prev.includes(encodedName) ? prev : [...prev, encodedName]
          )
        })

      if (data.status !== 'processing') {
        ws.close()
        setTranscoding(false)
        fetchVideos()
      }
    }
    ws.onerror = () => {
      message.error('WebSocket 连接失败')
      setTranscoding(false)
      ws.close()
    }
  }

  const downloadFile = (name: string) => {
    axios
      .get(
        `/api/videos/download-file?filename=${currentTask}&file=${encodeURIComponent(
          name
        )}`,
        { responseType: 'blob' }
      )
      .then(res => saveAs(res.data, name))
      .catch(() => message.error(`"${name}" 下载失败`))
  }

  const downloadSelected = () => {
    const names = selectedRowKeys as string[]
    if (!names.length) return
    if (names.length === 1) {
      downloadFile(names[0])
    } else {
      const filesParam = names.map(encodeURIComponent).join(',')
      axios
        .get(`/api/videos/download?filename=${currentTask}&files=${filesParam}`, {
          responseType: 'blob',
        })
        .then(res =>
          saveAs(res.data, `${currentTask}.zip`)
        )
        .catch(() => message.error('下载失败'))
    }
  }

  const originalColumns = [
    { title: '文件名', dataIndex: 'name', key: 'name' },
    {
      title: '状态',
      key: 'status',
      render: (_: any, record: { name: string }) =>
        // 如果有任意一个转码后文件以原名结尾，就判定该文件已转码
        transcodedList.some(fn => fn.endsWith(record.name)) ? (
          <Tag color="green">已转码</Tag>
        ) : (
          <Tag color="orange">未转码</Tag>
        ),
    },
  ]

  const doneColumns = [
    { title: '转码后文件名', dataIndex: 'name', key: 'name' },
    {
      title: '状态',
      key: 'status',
      render: () => <Tag color="green">已转码</Tag>,
    },
  ]

  const rowSelection = {
    selectedRowKeys,
    onChange: (keys: React.Key[]) => setSelectedRowKeys(keys),
  }

  return (
    <div style={{ padding: 24 }}>
      <h2>视频转码工具</h2>

      {/* 上传行 */}
      <Space style={{ marginBottom: 16 }}>
        <Input
          placeholder="请输入任务名称"
          value={taskName}
          onChange={e => setTaskName(e.target.value)}
          style={{ width: 200 }}
        />
        <Upload {...uploadProps}>
          <Button
            icon={<UploadOutlined />}
            loading={uploading}
            disabled={!currentTask}
          >
            上传视频
          </Button>
        </Upload>
      </Space>

      {/* 空状态盒子 */}
      {originalList.length === 0 && transcodedList.length === 0 ? (
        <div
          style={{
            border: '1px dashed #d9d9d9',
            borderRadius: 4,
            padding: 48,
            textAlign: 'center',
            position: 'relative',
            minHeight: 200,
          }}
        >
          <div
            style={{
              position: 'absolute',
              top: 16,
              left: 16,
              display: 'flex',
              gap: 8,
            }}
          >
            <Button
              type="primary"
              onClick={startTranscode}
              loading={transcoding}
              disabled={!currentTask}
            >
              开始转码
            </Button>
            <Button
              onClick={downloadSelected}
              disabled={selectedRowKeys.length === 0}
            >
              下载已转码
            </Button>
          </div>
          <Empty description="暂无视频" />
        </div>
      ) : (
        <>
          {/* 有数据时的按钮行 */}
          <div style={{ marginBottom: 16, display: 'flex', gap: 8 }}>
            <Button
              type="primary"
              onClick={startTranscode}
              loading={transcoding}
              disabled={!currentTask}
            >
              开始转码
            </Button>
            <Button
              onClick={downloadSelected}
              disabled={selectedRowKeys.length === 0}
            >
              下载已转码
            </Button>
          </div>

          {/* 原始文件列表 */}
          <h3>原始文件列表</h3>
          <Table
            dataSource={originalList.map(name => ({ key: name, name }))}
            columns={originalColumns}
            pagination={false}
            locale={{ emptyText: '暂无原始视频' }}
          />

          {/* 已转码文件列表 */}
          {transcodedList.length > 0 && (
            <>
              <h3>已转码文件列表</h3>
              <Table
                rowSelection={rowSelection}
                dataSource={transcodedList.map(name => ({ key: name, name }))}
                columns={doneColumns}
                pagination={false}
                locale={{ emptyText: '暂无已转码视频' }}
              />
            </>
          )}

          {/* 转码进度 */}
          {progressInfo && (
            <div style={{ marginTop: 32 }}>
              <h3>转码进度</h3>
              <Progress
                percent={calcPercent()}
                status={progressInfo.status === 'failed' ? 'exception' : undefined}
              />
              <ul style={{ marginTop: 16 }}>
                {progressInfo.results.map(r => (
                  <li key={r.input}>
                    {r.input} →{' '}
                    {r.status === 'success' ? r.output : (
                      <span style={{ color: 'red' }}>{r.error}</span>
                    )}
                  </li>
                ))}
              </ul>
            </div>
          )}
        </>
      )}
    </div>
  )
}

export default VideoSimplePage
