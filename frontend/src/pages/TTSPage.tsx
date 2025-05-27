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
  const [voice, setVoice] = useState('');
  const [voiceList] = useState<string[]>(['ja-JP-MayuNeural', 'ja-JP-DaichiNeural']);
  const [breakResults, setBreakResults] = useState<any[]>([]);
  const [selectedFiles, setSelectedFiles] = useState<string[]>([]);
  const [generating, setGenerating] = useState(false);
  const [progress, setProgress] = useState<number>(0);
  const [images, setImages] = useState<string[]>([]);
  const [selectedImages, setSelectedImages] = useState<string[]>([]);
  const [noteApiKey, setNoteApiKey] = useState('sk-xdtZS13EcaCHxoRbL50JDdP85EUKEhXtg4IcBKSKgF4ObTvW');
  const [notePrompt, setNotePrompt] = useState('');
  const [folderName, setFolderName] = useState('');
  const wsRef = useRef<WebSocket | null>(null);

  const fetchTaskList = async () => {
    try {
      const res = await axios.get('http://localhost:8000/api/tasks/');
      const ids = Object.keys(res.data);
      const taskInfos = await Promise.allSettled(
        ids.map(id => axios.get(`http://localhost:8000/api/tasks/${id}`))
      );
      const tasks = taskInfos
        .filter(result => result.status === 'fulfilled')
        .map(result => {
          const task = (result as PromiseFulfilledResult<any>).value.data;
          const name =
            task.data?.original_filename?.split('.')[0] ||
            task.data?.pdf_filename?.split('.')[0] ||
            task.id;
          return { id: task.id, name };
        });
      setTaskList(tasks);
    } catch {
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
      const filesRes = await axios.get('http://localhost:8000/api/files/list/', {
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

  const handleGenerateNotes = async (selectedOnly: boolean) => {
    try {
      const formData = new FormData();
      formData.append("api_key", noteApiKey);
      formData.append("prompt", notePrompt || "");

      if (selectedOnly && selectedImages.length > 0) {
        selectedImages.forEach(img => {
          const match = img.match(/(\d+)\.png$/);
          if (match) {
            formData.append("pages", match[1]);
          }
        });
      }

      const query = new URLSearchParams();
      if (selectedTaskId) {
        query.append("task_id", selectedTaskId);
      }

      await axios.post(
        `http://localhost:8000/api/notes/generate-pages-script?${query.toString()}`,
        formData,
        {
          headers: {
            "Content-Type": "multipart/form-data"
          }
        }
      );

      message.success("文稿生成成功");
      fetchTxtFiles();
    } catch (err) {
      console.error(err);
      message.error("文稿生成失败");
    }
  };


  const handleGenerateAll = async () => {
    if (!selectedTaskId) return;
    setGenerating(true);
    setProgress(0);
    wsRef.current = new WebSocket(`ws://localhost:8000/api/tts/ws/generate`);
    wsRef.current.onmessage = (e) => {
      try {
        const data = JSON.parse(e.data);
        if (data.type === 'filename' && data.progress) {
          setProgress(data.progress.progress);
        }
      } catch {}
    };
    try {
      await axios.post(`http://localhost:8000/api/tts/generate`, null, {
        params: { task_id: selectedTaskId }
      });
      message.success('生成完成');
      fetchGeneratedFiles();
    } finally {
      setGenerating(false);
      wsRef.current?.close();
    }
  };

  const handleCheckBreak = async () => {
    const res = await axios.get('http://localhost:8000/api/tts/check-breaktime/all');
    setBreakResults(res.data.results);
  };

  const handleGenerateOne = async (filename: string) => {
    await axios.post('http://localhost:8000/api/tts/generate-one', { filename });
    fetchGeneratedFiles();
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

  useEffect(() => {
    fetchTaskList();
    (async () => {
      setVoice(await getConfig('voice'));
      setSpeechKey(await getConfig('speech_key'));
    })();
  }, []);

  useEffect(() => {
    fetchTxtFiles();
    fetchGeneratedFiles();
    fetchImages();
  }, [selectedTaskId]);

  const getConfig = async (key: string) => {
    const res = await axios.get(`http://localhost:8000/api/tts/get-config/${key}`);
    return res.data.value;
  };

  const setConfig = async (key: string, value: string) => {
    await axios.post('http://localhost:8000/api/tts/set-config', { key, value });
    message.success(`${key} 设置成功`);
  };

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
            setVoice(v);
            setConfig('voice', v);
          }}
          style={{ width: '100%', marginTop: 8 }}
        >
          {voiceList.map(v => <Option key={v}>{v}</Option>)}
        </Select>
      </Card>

      <Card title="图片生成文稿" style={{ marginTop: 24 }}>
        <Input
          value={noteApiKey}
          onChange={(e) => setNoteApiKey(e.target.value)}
          placeholder="请输入 API Key"
          style={{ marginBottom: 8 }}
        />
        <Input.TextArea
          value={notePrompt}
          onChange={(e) => setNotePrompt(e.target.value)}
          placeholder="请输入 Prompt"
          rows={2}
          style={{ marginBottom: 8 }}
        />
        <Space>
          <Button onClick={() => handleGenerateNotes(false)}>生成全部</Button>
          <Button onClick={() => handleGenerateNotes(true)}>生成选中</Button>
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
              <img
                src={`http://localhost:8000/processed_images/${encodeURIComponent(row.image)}`}
                style={{ height: 100 }}
                onError={(e) => (e.currentTarget.style.display = 'none')}
              />
            )
          }]}
          pagination={false}
          style={{ marginTop: 16 }}
        />
      </Card>

      <Space style={{ margin: '16px 0' }}>
        <Button onClick={handleGenerateAll}>生成所有音频与字幕</Button>
        <Button onClick={handleCheckBreak}>检查 break 标签</Button>
        <Button danger onClick={deleteAllFiles}>删除所有</Button>
      </Space>
      {generating && <Progress percent={progress} status="active" style={{ marginTop: 10 }} />}

      <h3>文稿文件</h3>
      <Table
        rowSelection={{
          selectedRowKeys: selectedFiles,
          onChange: keys => setSelectedFiles(keys as string[])
        }}
        dataSource={txtFiles.map(f => ({ key: f, name: f }))}
        columns={[{
          title: '文件名', dataIndex: 'name'
        }]}
      />

      <h3>音频文件</h3>
      <Table
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
