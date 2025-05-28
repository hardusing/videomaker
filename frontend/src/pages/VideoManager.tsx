import React, { useEffect, useState } from 'react';
import axios from 'axios';
import { saveAs } from 'file-saver';
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
  List,
} from 'antd';
import { UploadOutlined } from '@ant-design/icons';

axios.defaults.baseURL = 'http://localhost:8000';

type ProgressInfo = {
  status: 'processing' | 'completed' | 'failed';
  total: number;
  completed: number;
  results: Array<{
    input: string;
    output?: string;
    status: string;
    error?: string;
  }>;
};

const VideoSimplePage: React.FC = () => {
  const [taskName, setTaskName] = useState<string>('');
  const [originalList, setOriginalList] = useState<string[]>([]);
  const [transcodedList, setTranscodedList] = useState<string[]>([]);
  const [selectedRowKeys, setSelectedRowKeys] = useState<React.Key[]>([]);
  const [folderSelectedKeys, setFolderSelectedKeys] = useState<React.Key[]>([]);
  const [uploading, setUploading] = useState(false);
  const [transcoding, setTranscoding] = useState(false);
  const [progressInfo, setProgressInfo] = useState<ProgressInfo | null>(null);
  const [view, setView] = useState<'task' | 'folders' | 'folder'>('task');
  const [folders, setFolders] = useState<string[]>([]);
  const [currentFolder, setCurrentFolder] = useState<string>('');

  const currentTask = taskName.trim();

  const fetchVideos = async () => {
    if (!currentTask) {
      setOriginalList([]);
      setTranscodedList([]);
      setSelectedRowKeys([]);
      return;
    }

    try {
      const res = await axios.get<{
        tasks: Record<string, string[]>;
        encoded: Record<string, string[]>;
      }>('/api/videos/');
      setOriginalList(res.data.tasks[currentTask] || []);
      setTranscodedList(res.data.encoded[currentTask] || []);
      setSelectedRowKeys([]);
    } catch {
      message.error('获取视频列表失败');
    }
  };

  const fetchFolders = async () => {
    try {
      const res = await axios.get<{ folders: string[] }>('/api/videos/all-folders');
      setFolders(res.data.folders);
      setView('folders');
    } catch {
      message.error('获取文件夹列表失败');
    }
  };

  const fetchFolderVideos = async (folder: string) => {
    try {
      const res = await axios.get<{ encoded: Record<string, string[]> }>('/api/videos/');
      setTranscodedList(res.data.encoded[folder] || []);
      setCurrentFolder(folder);
      setFolderSelectedKeys([]);
      setView('folder');
    } catch {
      message.error('获取文件列表失败');
    }
  };

  useEffect(() => {
    if (view === 'task') fetchVideos();
  }, [currentTask, view]);

  const calcPercent = () => {
    if (!progressInfo) return 0;
    return progressInfo.status === 'processing'
      ? Math.floor((progressInfo.completed / progressInfo.total) * 100)
      : 100;
  };

  const uploadProps = {
    multiple: true,
    showUploadList: false as any,
    customRequest: async ({ file, onSuccess, onError }: any) => {
      if (!currentTask) return message.warning('请先输入任务名称');

      setUploading(true);
      const form = new FormData();
      form.append('files', file as Blob);

      try {
        await axios.post('/api/videos/upload-multiple', form, {
          params: { filename: currentTask },
        });
        message.success(`${file.name} 上传成功`);
        await fetchVideos();
        onSuccess && onSuccess(null, file);
      } catch {
        message.error(`${file.name} 上传失败`);
        onError && onError(new Error(), file);
      } finally {
        setUploading(false);
      }
    },
  };

  const startTranscode = () => {
    if (!currentTask) return message.warning('请先输入任务名称');

    setProgressInfo(null);
    setTranscoding(true);
    setTranscodedList([]);
    setSelectedRowKeys([]);

    let ignoreFirst = true;
    const ws = new WebSocket(
      `ws://localhost:8000/api/videos/ws/transcode/${encodeURIComponent(currentTask)}`
    );

    ws.onopen = async () => {
      try {
        await axios.post('/api/videos/transcode', null, {
          params: { filename: currentTask },
        });
      } catch {
        message.error('无法开始转码');
        setTranscoding(false);
        ws.close();
      }
    };

    ws.onmessage = (ev) => {
      if (ignoreFirst) {
        ignoreFirst = false;
        return;
      }
      const data: ProgressInfo = JSON.parse(ev.data);
      setProgressInfo(data);

      data.results
        .filter((r) => r.status === 'success' && r.output)
        .forEach((r) => {
          const name = r.output!;
          setTranscodedList((prev) => (prev.includes(name) ? prev : [...prev, name]));
        });

      if (data.status !== 'processing') {
        ws.close();
        setTranscoding(false);
        fetchVideos();
      }
    };

    ws.onerror = () => {
      message.error('WebSocket 连接失败');
      setTranscoding(false);
      ws.close();
    };
  };

  const downloadFile = (name: string) => {
    axios
      .get(`/api/videos/download-file?filename=${currentTask}&file=${encodeURIComponent(name)}`, {
        responseType: 'blob',
      })
      .then((res) => saveAs(res.data, name))
      .catch(() => message.error(`"${name}" 下载失败`));
  };

  const downloadSelected = () => {
    const names = selectedRowKeys as string[];
    if (!names.length) return;
    if (names.length === 1) return downloadFile(names[0]);

    const param = names.map(encodeURIComponent).join(',');
    axios
      .get(`/api/videos/download?filename=${currentTask}&files=${param}`, {
        responseType: 'blob',
      })
      .then((res) => saveAs(res.data, `${currentTask}.zip`))
      .catch(() => message.error('下载失败'));
  };

  const downloadFolder = () => {
    const names = folderSelectedKeys as string[];
    if (!names.length) return;
    if (names.length === 1) return downloadFile(names[0]);

    const param = names.map(encodeURIComponent).join(',');
    axios
      .get(`/api/videos/download?filename=${currentFolder}&files=${param}`, {
        responseType: 'blob',
      })
      .then((res) => saveAs(res.data, `${currentFolder}.zip`))
      .catch(() => message.error('下载失败'));
  };

  const originalColumns = [
    { title: '文件名', dataIndex: 'name', key: 'name' },
    {
      title: '状态',
      key: 'status',
      render: (_: any, rec: { name: string }) =>
        transcodedList.some((fn) => fn.endsWith(rec.name)) ? (
          <Tag color="green">已转码</Tag>
        ) : (
          <Tag color="orange">未转码</Tag>
        ),
    },
  ];

  const doneColumns = [
    { title: '转码后文件名', dataIndex: 'name', key: 'name' },
    {
      title: '状态',
      key: 'status',
      render: () => <Tag color="green">已转码</Tag>,
    },
  ];

  const rowSelection = {
    selectedRowKeys,
    onChange: (keys: React.Key[]) => setSelectedRowKeys(keys),
  };

  const folderRowSelection = {
    selectedRowKeys: folderSelectedKeys,
    onChange: (keys: React.Key[]) => setFolderSelectedKeys(keys),
  };

  // Folders view
  if (view === 'folders') {
    return (
      <div style={{ padding: 24 }}>
        <Button onClick={() => setView('task')} style={{ marginBottom: 16 }}>
          返回任务视图
        </Button>
        <h3>转码文件夹列表</h3>
        <List
          bordered
          dataSource={folders}
          renderItem={(i) => (
            <List.Item
              onClick={() => fetchFolderVideos(i)}
              style={{ cursor: 'pointer' }}
            >
              {i}
            </List.Item>
          )}
        />
      </div>
    );
  }

  // Single folder view
  if (view === 'folder') {
    return (
      <div style={{ padding: 24 }}>
        <Button onClick={fetchFolders} style={{ marginBottom: 16 }}>
          返回文件夹列表
        </Button>
        <h3>文件夹: {currentFolder}</h3>
        <Space style={{ marginBottom: 16 }}>
          <Button onClick={downloadFolder} disabled={folderSelectedKeys.length === 0}>
            下载选中文件
          </Button>
        </Space>
        <Table
          rowSelection={folderRowSelection}
          dataSource={transcodedList.map((name) => ({ key: name, name }))}
          columns={doneColumns}
          pagination={false}
          locale={{ emptyText: '暂无已转码视频' }}
        />
      </div>
    );
  }

  // Main task view
  return (
    <div style={{ padding: 24 }}>
      <h2>视频转码工具</h2>
      <Space style={{ marginBottom: 16 }}>
        <Input
          placeholder="请输入任务名称"
          value={taskName}
          onChange={(e) => setTaskName(e.target.value)}
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

      <Space style={{ marginBottom: 16 }}>
        <Button
          type="primary"
          onClick={startTranscode}
          loading={transcoding}
          disabled={!currentTask}
        >
          开始转码
        </Button>
        <Button onClick={downloadSelected} disabled={selectedRowKeys.length === 0}>
          下载已转码
        </Button>
        <Button onClick={fetchFolders}>查看转码文件夹</Button>
      </Space>

      {originalList.length === 0 && transcodedList.length === 0 ? (
        <div
          style={{
            border: '1px dashed #d9d9d9',
            borderRadius: 4,
            padding: 48,
            textAlign: 'center',
            minHeight: 200,
          }}
        >
          <Empty description="暂无视频" />
        </div>
      ) : (
        <>
          <h3>原始文件列表</h3>
          <Table
            dataSource={originalList.map((n) => ({ key: n, name: n }))}
            columns={originalColumns}
            pagination={false}
            locale={{ emptyText: '暂无原始视频' }}
          />

          {transcodedList.length > 0 && (
            <>
              <h3>已转码文件列表</h3>
              <Table
                rowSelection={rowSelection}
                dataSource={transcodedList.map((n) => ({ key: n, name: n }))}
                columns={doneColumns}
                pagination={false}
                locale={{ emptyText: '暂无已转码视频' }}
              />
            </>
          )}

          {progressInfo && (
            <div style={{ marginTop: 32 }}>
              <h3>转码进度</h3>
              <Progress
                percent={calcPercent()}
                status={progressInfo.status === 'failed' ? 'exception' : undefined}
              />
              <ul style={{ marginTop: 16 }}>
                {progressInfo.results.map((r) => (
                  <li key={r.input}>
                    {r.input} →{' '}
                    {r.status === 'success' ? r.output : <span style={{ color: 'red' }}>{r.error}</span>}
                  </li>
                ))}
              </ul>
            </div>
          )}
        </>
      )}
    </div>
  );
};

export default VideoSimplePage;
