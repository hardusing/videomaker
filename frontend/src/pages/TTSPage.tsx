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
  const [ttsFolders, setTtsFolders] = useState<string[]>([]);
  const [selectedTtsFolder, setSelectedTtsFolder] = useState<string>('');
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
  const [notesFolders, setNotesFolders] = useState<string[]>([]);
  const [selectedNotesFolder, setSelectedNotesFolder] = useState<string>('');
  const [ttsLanguage, setTtsLanguage] = useState('male');
  const [generatingTts, setGeneratingTts] = useState<boolean>(false);
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
    if (!selectedNotesFolder) {
      setTxtFiles([]);
      return;
    }
    try {
      // 使用 notes API 的 /all 接口，通过 filename 参数获取指定文件夹下的文稿
      const res = await axios.get('http://localhost:8000/api/notes/all', {
        params: { filename: selectedNotesFolder }
      });
      setTxtFiles(res.data.files || []);
    } catch {
      message.error('获取TXT文件失败');
    }
  };

  const fetchGeneratedFiles = async () => {
    if (!selectedTtsFolder) return;
    try {
      setFolderName(selectedTtsFolder);
      // 根据选中的文件夹获取音频和字幕文件
      const filesRes = await axios.get('http://localhost:8000/api/files/list', {
        params: { dir_name: selectedTtsFolder }
      });
      const files: string[] = filesRes.data || [];
      setAudioFiles(files.filter(f => f.endsWith('.wav')));
      setSubtitleFiles(files.filter(f => f.endsWith('_merged.srt')));
    } catch (error) {
      // 如果目录不存在或没有文件，不报错，只是清空文件列表
      console.log('文件夹中没有音频文件或目录不存在');
      setAudioFiles([]);
      setSubtitleFiles([]);
    }
  };

  const fetchImages = async () => {
    if (!selectedTtsFolder) return;
    try {
      const res = await axios.get('http://localhost:8000/api/image-notes/black-bordered-images', {
        params: { dir_name: selectedTtsFolder }
      });
      setImages(res.data.images || []);
    } catch {
      message.error('获取图片失败');
    }
  };

  const fetchAvailableFolders = async () => {
    try {
      console.log('正在获取可用文件夹...');
      // 使用 image-notes/images 接口获取 converted_images 目录下的所有图片
      const res = await axios.get('http://localhost:8000/api/image-notes/images');
      console.log('获取到的图片数据:', res.data);
      
      // 从图片路径中提取文件夹名称
      const folderMap = new Map<string, string>();
      const images = res.data.images || [];
      
      images.forEach((imagePath: string) => {
        const folderName = imagePath.split('/')[0];
        if (folderName && !folderMap.has(folderName)) {
          folderMap.set(folderName, folderName);
        }
      });
      
      const folders = Array.from(folderMap.values()).map(name => ({
        name,
        path: name
      }));
      
      console.log('提取的文件夹:', folders);
      setAvailableFolders(folders);
    } catch (error) {
      console.error('获取可用文件夹失败:', error);
      message.error(`获取可用文件夹失败: ${error.response?.data?.detail || error.message}`);
    }
  };

  const fetchNotesFolders = async () => {
    try {
      console.log('正在获取notes_output文件夹...');
      // 使用新的 notes-folders 接口获取 notes_output 目录下的所有文件夹
      const res = await axios.get('http://localhost:8000/api/notes/notes-folders');
      console.log('获取到的notes文件夹数据:', res.data);
      
      const folders = res.data.folders || [];
      const folderNames = folders.map((folder: any) => folder.name);
      
      console.log('提取的notes文件夹:', folderNames);
      setNotesFolders(folderNames);
      setTtsFolders(folderNames); // 同时设置TTS文件夹列表
    } catch (error) {
      console.error('获取notes文件夹失败:', error);
      message.error(`获取notes文件夹失败: ${error.response?.data?.detail || error.message}`);
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
      // 使用 generate-folder-scripts 接口
      const formData = new FormData();
      formData.append("folder_name", selectedFolder); // 文件夹名称
      formData.append("api_key", noteApiKey); // API Key
      if (notePrompt) {
        formData.append("prompt", notePrompt); // Prompt
      }
      
      const response = await axios.post('http://localhost:8000/api/notes/generate-folder-scripts', formData, {
        headers: { "Content-Type": "multipart/form-data" }
      });
      
      message.success(`文稿生成成功！处理了 ${selectedFolder} 文件夹下的图片`);
      
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
    if (!selectedTtsFolder) return;
    const filesToGenerate = selectedFiles.length > 0 ? selectedFiles : txtFiles;
    if (filesToGenerate.length === 0) {
      message.warning("没有选中的文稿文件");
      return;
    }
    setGenerating(true);
    setProgress(0);

    wsRef.current = new WebSocket(`ws://localhost:8000/api/tts/ws/generate-selected/${selectedTtsFolder}`);
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
      await axios.post(`http://localhost:8000/api/tts/generate-selected?dir_name=${selectedTtsFolder}`, {
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

  const handleGenerateTts = async () => {
    if (!selectedTtsFolder) {
      message.warning("请选择一个文件夹");
      return;
    }
    if (!ttsLanguage) {
      message.warning("请选择语言种类");
      return;
    }

    setGeneratingTts(true);
    try {
      const response = await axios.post('http://localhost:8000/api/tts/generate', null, {
        params: {
          filename: selectedTtsFolder,
          gender: ttsLanguage
        }
      });
      
      message.success('TTS音频生成成功！');
      fetchGeneratedFiles(); // 刷新文件列表
    } catch (err: any) {
      console.error(err);
      const errorMsg = err.response?.data?.detail || "TTS音频生成失败";
      message.error(errorMsg);
    } finally {
      setGeneratingTts(false);
    }
  };

  const handleDownloadSelectedMediaZip = async () => {
    const mediaFiles = selectedFiles.filter(name => name.endsWith('.wav') || name.endsWith('.srt'));
    if (mediaFiles.length === 0) return;
    const link = document.createElement('a');
    link.href = `http://localhost:8000/api/download/all?dir_name=${selectedTtsFolder}`;
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
      params: { dir_name: selectedTtsFolder }
    });
    fetchGeneratedFiles();
  };

  const deleteAllFiles = async () => {
    await axios.delete('http://localhost:8000/api/files/clear', {
      params: { dir_name: selectedTtsFolder }
    });
    fetchGeneratedFiles();
  };

  const deleteTask = async () => {
    Modal.confirm({
      title: '确定要删除此文件夹吗？',
      onOk: async () => {
        // 这里可以添加删除文件夹的逻辑
        message.success('文件夹已删除');
        setSelectedTtsFolder('');
        fetchNotesFolders();
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
    fetchAvailableFolders();
    fetchNotesFolders();
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
  }, [selectedNotesFolder, selectedTtsFolder]);

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
          placeholder="选择文件夹"
          value={selectedTtsFolder || undefined}
          onChange={(value) => {
            setSelectedTtsFolder(value);
            setSelectedFiles([]); // 清空选中的文件
          }}
          style={{ width: 300 }}
          showSearch
          filterOption={(input, option: any) =>
            (option?.children as string)?.toLowerCase().includes(input.toLowerCase())
          }
          allowClear
        >
          {ttsFolders.map(folder => (
            <Option key={folder} value={folder}>
              {folder}
            </Option>
          ))}
        </Select>
        <Button onClick={fetchNotesFolders}>刷新</Button>
        <Button danger onClick={deleteTask}>删除文件夹</Button>
      </Space>

      <Card title="TTS 设置" style={{ marginTop: 16 }}>
        <Space direction="vertical" style={{ width: '100%' }}>
          <Input
            value={speechKey}
            onChange={(e) => setSpeechKey(e.target.value)}
            addonAfter={<Button onClick={() => setConfig('speech_key', speechKey)}>保存</Button>}
            placeholder="Speech Key"
          />
          
          <div style={{ borderTop: '1px solid #f0f0f0', paddingTop: 16, marginTop: 16 }}>
            <h4>生成音频设置</h4>
            <Select
              value={ttsLanguage}
              onChange={setTtsLanguage}
              style={{ width: '100%', marginBottom: 8 }}
              placeholder="选择语言种类"
            >
              <Option value="male">日语男声 (ja-JP-DaichiNeural)</Option>
              <Option value="chinese_female">中文女声 (zh-CN-XiaoxiaoNeural)</Option>
            </Select>
            <Button 
              type="primary" 
              onClick={handleGenerateTts} 
              disabled={!selectedTtsFolder || !ttsLanguage || generatingTts}
              loading={generatingTts}
              style={{ width: '100%' }}
            >
              {generatingTts ? '正在生成音频...' : '生成音频'}
            </Button>
          </div>
        </Space>
      </Card>

      <Card title="文稿生成" style={{ marginTop: 24 }}>
        <div style={{ marginBottom: 16 }}>
          <Input value={noteApiKey} onChange={(e) => setNoteApiKey(e.target.value)} placeholder="请输入 API Key" style={{ marginBottom: 8 }} />
          <Input.TextArea value={notePrompt} onChange={(e) => setNotePrompt(e.target.value)} placeholder="请输入 Prompt（可选）" rows={2} style={{ marginBottom: 8 }} />
        </div>

                          <Card type="inner" title="选择文件夹生成" style={{ marginBottom: 16 }}>
            <Space style={{ width: '100%' }} direction="vertical">
              <Space style={{ width: '100%' }}>
                <Select
                  placeholder="选择 converted_images 下的文件夹"
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
        <Space style={{ marginBottom: 16 }}>
          <Select
            placeholder="选择 notes_output 下的文件夹"
            value={selectedNotesFolder || undefined}
            onChange={(value) => {
              setSelectedNotesFolder(value);
              setSelectedFiles([]); // 清空选中的文件
            }}
            style={{ width: 300 }}
            showSearch
            filterOption={(input, option: any) =>
              (option?.children as string)?.toLowerCase().includes(input.toLowerCase())
            }
            allowClear
          >
            {notesFolders.map(folder => (
              <Option key={folder} value={folder}>
                {folder}
              </Option>
            ))}
          </Select>
          <Button onClick={fetchNotesFolders}>刷新</Button>
        </Space>
        {selectedNotesFolder && (
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
                <a href={`http://localhost:8000/api/notes/${encodeURIComponent(row.name)}?dir_name=${encodeURIComponent(selectedNotesFolder)}`} target="_blank" rel="noopener noreferrer">{row.name}</a>
              )
            }]}
            locale={{ emptyText: '该文件夹下没有文稿文件' }}
          />
        )}

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