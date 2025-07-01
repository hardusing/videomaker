import React, { useEffect, useState, useRef } from 'react';
import {
  Table, Button, message, Space, Input, Tag, Card, Select, Progress, Modal
} from 'antd';
import axios from 'axios';

const { Option } = Select;

const TTSPage: React.FC = () => {
  const [txtFiles, setTxtFiles] = useState<string[]>([]);
  const [audioFiles, setAudioFiles] = useState<string[]>([]);
  const [subtitleFiles, setSubtitleFiles] = useState<string[]>([]);
  const [taskList, setTaskList] = useState<{ id: string; name: string }[]>([]);
  const [selectedTaskId, setSelectedTaskId] = useState<string>('');
  const [speechKey, setSpeechKey] = useState('');
  const [voice, setVoice] = useState('ja-JP-DaichiNeural');
  const [voiceList] = useState<string[]>(['ja-JP-DaichiNeural']); // 使用男生声音
  const [breakResults, setBreakResults] = useState<any[]>([]);
  const [selectedFiles, setSelectedFiles] = useState<string[]>([]);
  const [generating, setGenerating] = useState(false);
  const [progress, setProgress] = useState<number>(0);
  const [images, setImages] = useState<string[]>([]);
  const [selectedImages, setSelectedImages] = useState<string[]>([]);
  const [noteApiKey, setNoteApiKey] = useState('sk-xdtZS13EcaCHxoRbL50JDdP85EUKEhXtg4IcBKSKgF4ObTvW');
  const [notePrompt, setNotePrompt] = useState('');
  const [folderName, setFolderName] = useState('');
  const [availableFolders, setAvailableFolders] = useState<{name: string, path: string}[]>([]);
  const [selectedFolder, setSelectedFolder] = useState<string>('');
  const [generatingFolder, setGeneratingFolder] = useState<boolean>(false);
  const wsRef = useRef<WebSocket | null>(null);

  const fetchTaskList = async () => {
    try {
      const res = await axios.get('http://localhost:8000/api/tasks/');
      const tasksRaw = res.data;
      const taskMap = new Map<string, { id: string; name: string }>();
      Object.entries(tasksRaw).forEach(([id, task]: [string, any]) => {
        const name = task.data?.original_filename?.split('.')[0] || task.data?.pdf_filename?.split('.')[0] || id;
        taskMap.set(id, { id, name });
      });
      setTaskList(Array.from(taskMap.values()));
    } catch (error) {
      console.error(error);
      message.error('获取任务列表失败');
    }
  };

  const fetchTxtFiles = async () => {
    if (!selectedTaskId) return;
    try {
      const res = await axios.get('http://localhost:8000/api/tts/texts', {
        params: { task_id: selectedTaskId }
      });
      setTxtFiles(res.data || []);
    } catch {
      message.error('获取TXT文件失败');
    }
  };

  const fetchGeneratedFiles = async () => {
    if (!selectedTaskId) return;
    try {
      const res = await axios.get('http://localhost:8000/api/tasks/' + selectedTaskId);
      const task = res.data;
      const folder = task.data?.original_filename?.split('.')[0] || task.data?.pdf_filename?.split('.')[0];
      setFolderName(folder);
      const filesRes = await axios.get('http://localhost:8000/api/files/list', {
        params: { task_id: selectedTaskId }
      });
      const files: string[] = filesRes.data || [];
      setAudioFiles(files.filter(f => f.endsWith('.wav')));
      setSubtitleFiles(files.filter(f => f.endsWith('_merged.srt')));
    } catch {
      message.error('获取生成文件失败');
    }
  };

  const fetchImages = async () => {
    if (!selectedTaskId) return;
    try {
      const res = await axios.get('http://localhost:8000/api/image-notes/black-bordered-images', {
        params: { task_id: selectedTaskId }
      });
      setImages(res.data.images || []);
    } catch {
      message.error('获取图片失败');
    }
  };

  const fetchAvailableFolders = async () => {
    try {
      const res = await axios.get('http://localhost:8000/api/notes/available-folders');
      setAvailableFolders(res.data.folders || []);
    } catch {
      message.error('获取可用文件夹失败');
    }
  };

  const handleGenerateNotes = async (selectedOnly: boolean) => {
    try {
      const formData = new FormData();
      formData.append("api_key", noteApiKey);
      formData.append("prompt", notePrompt || "");
      
      // 收集选中的页码
      if (selectedOnly && selectedImages.length > 0) {
        const pageNumbers: number[] = [];
        selectedImages.forEach(img => {
          const match = img.match(/(\d+)\.png$/);
          if (match) {
            pageNumbers.push(parseInt(match[1], 10));
          }
        });
        
        // 将页码数组作为JSON字符串发送，或者逐个添加整数
        pageNumbers.forEach(pageNum => {
          formData.append("pages", pageNum.toString());
        });
      }
      
      const query = new URLSearchParams();
      if (selectedTaskId) query.append("task_id", selectedTaskId);
      
      await axios.post(`http://localhost:8000/api/notes/generate-pages-script?${query.toString()}`, formData, {
        headers: { "Content-Type": "multipart/form-data" }
      });
      message.success("文稿生成成功");
      fetchTxtFiles();
    } catch (err) {
      console.error(err);
      message.error("文稿生成失败");
    }
  };

  const handleGenerateFolderScripts = async () => {
    if (!selectedFolder) {
      message.warning("请选择一个文件夹");
      return;
    }
    
    if (!noteApiKey) {
      message.warning("请输入API Key");
      return;
    }

    setGeneratingFolder(true);
    try {
      const formData = new FormData();
      formData.append("folder_name", selectedFolder);
      formData.append("api_key", noteApiKey);
      if (notePrompt) {
        formData.append("prompt", notePrompt);
      }
      
      const response = await axios.post('http://localhost:8000/api/notes/generate-folder-scripts', formData, {
        headers: { "Content-Type": "multipart/form-data" }
      });
      
      message.success(`文稿生成成功！处理了 ${response.data.processed_images} 张图片`);
      
      // 刷新文件列表（如果当前选中的任务对应该文件夹）
      fetchTxtFiles();
    } catch (err: any) {
      console.error(err);
      const errorMsg = err.response?.data?.detail || "文稿生成失败";
      message.error(errorMsg);
    } finally {
      setGeneratingFolder(false);
    }
  };

  const handleGenerateSelected = async () => {
    if (!selectedTaskId) return;
    const filesToGenerate = selectedFiles.length > 0 ? selectedFiles : txtFiles;
    if (filesToGenerate.length === 0) {
      message.warning("没有选中的文稿文件");
      return;
    }
    setGenerating(true);
    setProgress(0);

    wsRef.current = new WebSocket(`ws://localhost:8000/api/tts/ws/generate-selected/${selectedTaskId}`);
    wsRef.current.onopen = () => {
      wsRef.current?.send(JSON.stringify({ filenames: filesToGenerate }));
    };
    wsRef.current.onmessage = (e) => {
      try {
        const data = JSON.parse(e.data);
        if (data.progress) setProgress(data.progress);
        else if (data.error) message.error(data.error);
      } catch {
        console.error("WebSocket解析失败", e.data);
      }
    };

    try {
      await axios.post(`http://localhost:8000/api/tts/generate-selected?task_id=${selectedTaskId}`, {
        filenames: filesToGenerate
      });
      message.success('选中文稿生成完成');
      fetchGeneratedFiles();
    } catch (err) {
      console.error(err);
      message.error('生成失败');
    } finally {
      setGenerating(false);
      wsRef.current?.close();
    }
  };

  const handleDownloadSelectedMediaZip = async () => {
    const mediaFiles = selectedFiles.filter(name => name.endsWith('.wav') || name.endsWith('.srt'));
    if (mediaFiles.length === 0) return;
    const link = document.createElement('a');
    link.href = `http://localhost:8000/api/download/all?task_id=${selectedTaskId}`;
    link.download = `${folderName}_srt_and_wav.zip`;
    link.target = '_blank';
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  };

  const handleCheckBreak = async () => {
    const res = await axios.get('http://localhost:8000/api/tts/check-breaktime/all');
    setBreakResults(res.data.results);
  };

  const deleteSingleFile = async (filename: string) => {
    await axios.delete(`http://localhost:8000/api/files/delete/${filename}`, {
      params: { task_id: selectedTaskId }
    });
    fetchGeneratedFiles();
  };

  const deleteAllFiles = async () => {
    await axios.delete('http://localhost:8000/api/files/clear', {
      params: { task_id: selectedTaskId }
    });
    fetchGeneratedFiles();
  };

  const deleteTask = async () => {
    Modal.confirm({
      title: '确定要删除此任务吗？',
      onOk: async () => {
        await axios.delete(`http://localhost:8000/api/tasks/${selectedTaskId}`);
        message.success('任务已删除');
        setSelectedTaskId('');
        fetchTaskList();
      }
    });
  };

  const handleSelectAllTxtFiles = () => {
    setSelectedFiles(txtFiles);
  };

  const handleSelectAllMediaFiles = () => {
    setSelectedFiles([...audioFiles, ...subtitleFiles]);
  };

  const handleClearSelected = () => {
    setSelectedFiles([]);
  };

  useEffect(() => {
    fetchTaskList();
    fetchAvailableFolders();
    (async () => {
      setVoice(await getConfig('voice'));
      setSpeechKey(await getConfig('speech_key'));
    })();
  }, []);

  useEffect(() => {
    fetchTxtFiles();
    fetchGeneratedFiles();
    fetchImages();
    setSelectedFiles([]);
  }, [selectedTaskId]);

  const getConfig = async (key: string) => {
    const res = await axios.get(`http://localhost:8000/api/tts/get-config/${key}`);
    return res.data.value;
  };

  const setConfig = async (key: string, value: string) => {
    await axios.post('http://localhost:8000/api/tts/set-config', { key, value });
    message.success(`${key} 设置成功`);
  };

  const hasDownloadableMedia = selectedFiles.some(name => name.endsWith('.wav') || name.endsWith('.srt'));

  return (
    <div style={{ padding: 24 }}>
      <h2>TTS 音频与字幕生成</h2>
      <Space>
        <Select
          placeholder="选择任务"
          value={selectedTaskId || undefined}
          onChange={setSelectedTaskId}
          style={{ width: 300 }}
        >
          {taskList.map(t => <Option key={t.id} value={t.id}>{t.name}</Option>)}
        </Select>
        <Button danger onClick={deleteTask}>删除任务</Button>
      </Space>

      <Card title="TTS 设置" style={{ marginTop: 16 }}>
        <Input
          value={speechKey}
          onChange={(e) => setSpeechKey(e.target.value)}
          addonAfter={<Button onClick={() => setConfig('speech_key', speechKey)}>保存</Button>}
          placeholder="Speech Key"
        />
        <Select
          value={voice}
          onChange={(v) => {
            // 使用男生声音 Daichi
            const fixedVoice = 'ja-JP-DaichiNeural';
            setVoice(fixedVoice);
            setConfig('voice', fixedVoice);
          }}
          style={{ width: '100%', marginTop: 8 }}
          disabled={true}
          placeholder="使用男生声音 Daichi"
        >
          {voiceList.map(v => <Option key={v}>{v === 'ja-JP-DaichiNeural' ? 'ja-JP-DaichiNeural (男生 - 当前)' : v}</Option>)}
        </Select>
      </Card>

      <Card title="文稿生成" style={{ marginTop: 24 }}>
        <div style={{ marginBottom: 16 }}>
          <Input value={noteApiKey} onChange={(e) => setNoteApiKey(e.target.value)} placeholder="请输入 API Key" style={{ marginBottom: 8 }} />
          <Input.TextArea value={notePrompt} onChange={(e) => setNotePrompt(e.target.value)} placeholder="请输入 Prompt（可选）" rows={2} style={{ marginBottom: 8 }} />
        </div>

        <Card type="inner" title="方式一：选择文件夹生成" style={{ marginBottom: 16 }}>
          <Space style={{ width: '100%' }} direction="vertical">
            <Space style={{ width: '100%' }}>
              <Select
                placeholder="选择 processed_images 下的文件夹"
                value={selectedFolder || undefined}
                onChange={setSelectedFolder}
                style={{ flex: 1 }}
                showSearch
                filterOption={(input, option: any) =>
                  (option?.children as string)?.toLowerCase().includes(input.toLowerCase())
                }
              >
                {availableFolders.map(folder => (
                  <Option key={folder.name} value={folder.name}>
                    {folder.name}
                  </Option>
                ))}
              </Select>
              <Button onClick={fetchAvailableFolders}>刷新</Button>
            </Space>
            <Button 
              type="primary" 
              onClick={handleGenerateFolderScripts} 
              disabled={!selectedFolder || generatingFolder}
              loading={generatingFolder}
              style={{ width: '100%' }}
            >
              {generatingFolder ? '正在生成...' : '生成该文件夹下所有图片的文稿'}
            </Button>
          </Space>
        </Card>

        <Card type="inner" title="方式二：从任务中选择图片生成">
          <Space style={{ marginBottom: 16 }}>
            <Button type="primary" onClick={() => handleGenerateNotes(true)} disabled={selectedImages.length === 0}>
              生成选中图片的文稿
            </Button>
          </Space>
          <Table
            rowSelection={{
              selectedRowKeys: selectedImages,
              onChange: keys => setSelectedImages(keys as string[])
            }}
            dataSource={images.map(i => ({ key: i, image: i }))}
            columns={[{
              title: '预览图',
              render: (row) => (
                <img src={`http://localhost:8000/processed_images/${encodeURIComponent(row.image)}`} style={{ height: 100 }} onError={(e) => (e.currentTarget.style.display = 'none')} />
              )
            }]}
            pagination={false}
            style={{ marginTop: 16 }}
          />
        </Card>
      </Card>

      <Space style={{ margin: '16px 0' }}>
        <Button onClick={handleSelectAllTxtFiles}>全选所有文稿</Button>
        <Button onClick={handleSelectAllMediaFiles}>全选所有音频和字幕</Button>
        <Button onClick={handleClearSelected}>取消全选</Button>
        <Button onClick={handleGenerateSelected}>生成选中文稿</Button>
        <Button onClick={handleDownloadSelectedMediaZip} disabled={!hasDownloadableMedia}>
          下载选中音频与字幕 (ZIP)
        </Button>
        <Button onClick={handleCheckBreak}>检查 break 标签</Button>
        <Button danger onClick={deleteAllFiles}>删除所有</Button>
      </Space>

      {generating && <Progress percent={progress} status="active" style={{ marginTop: 10 }} />}

      <h3>文稿文件</h3>
      <Table
        rowSelection={{
          selectedRowKeys: selectedFiles,
          onChange: keys => setSelectedFiles(keys as string[]),
          hideSelectAll: true
        }}
        dataSource={txtFiles.map(f => ({ key: f, name: f }))}
        columns={[{
          title: '文稿',
          render: (row) => (
            <a href={`http://localhost:8000/api/notes/${encodeURIComponent(row.name)}?dir_name=${encodeURIComponent(folderName)}`} target="_blank" rel="noopener noreferrer">{row.name}</a>
          )
        }]}
      />

      <h3>音频文件</h3>
      <Table
        rowSelection={{
          selectedRowKeys: selectedFiles,
          onChange: keys => setSelectedFiles(keys as string[]),
          hideSelectAll: true
        }}
        dataSource={audioFiles.map(f => ({ key: f, name: f }))}
        columns={[{
          title: '音频',
          render: (row) => (
            <Space>
              <audio controls src={`http://localhost:8000/srt_and_wav/${folderName}/${encodeURIComponent(row.name)}`} />
              <Button danger onClick={() => deleteSingleFile(row.name)}>删除</Button>
            </Space>
          )
        }]}
      />

      <h3>字幕文件</h3>
      <Table
        rowSelection={{
          selectedRowKeys: selectedFiles,
          onChange: keys => setSelectedFiles(keys as string[]),
          hideSelectAll: true
        }}
        dataSource={subtitleFiles.map(f => ({ key: f, name: f }))}
        columns={[{
          title: '字幕',
          render: (row) => (
            <Space>
              <a href={`http://localhost:8000/srt_and_wav/${folderName}/${encodeURIComponent(row.name)}`} download>{row.name}</a>
              <Button danger onClick={() => deleteSingleFile(row.name)}>删除</Button>
            </Space>
          )
        }]}
      />

      <Card title="Break 标签检查" style={{ marginTop: 32 }}>
        <Table
          dataSource={(breakResults || []).map((r, i) => ({ ...r, key: i }))}
          columns={[
            { title: '文件名', dataIndex: 'filename' },
            {
              title: '是否存在',
              dataIndex: 'has_breaktime',
              render: (v: boolean) =>
                v ? <Tag color="red">是</Tag> : <Tag color="green">否</Tag>,
            },
            { title: '说明', dataIndex: 'message' },
          ]}
          pagination={false}
          locale={{ emptyText: '未检测到 Break 标签' }}
        />
      </Card>
    </div>
  );
};

export default TTSPage;