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
  const [taskIds, setTaskIds] = useState<string[]>([]);
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
  const [noteApiKey, setNoteApiKey] = useState('');
  const [notePrompt, setNotePrompt] = useState('');
  const wsRef = useRef<WebSocket | null>(null);

  const getTaskFolderName = async (taskId: string): Promise<string | null> => {
    try {
      const res = await axios.get(`http://localhost:8000/api/tasks/${taskId}`);
      const task = res.data;
      const type = task.type;
      if (type === 'pdf_upload' || type === 'ppt_upload') {
        return task.data.original_filename?.split('.')[0] || null;
      } else if (type === 'pdf_to_images') {
        return task.data.pdf_filename?.split('.')[0] || null;
      }
    } catch {
      return null;
    }
    return null;
  };

  const fetchTasks = async () => {
    try {
      const res = await axios.get('http://localhost:8000/api/tasks/');
      const ids = Object.keys(res.data);
      const validTaskChecks = await Promise.allSettled(
        ids.map(id => axios.get(`http://localhost:8000/api/tasks/${id}`).then(() => id))
      );
      const validIds = validTaskChecks
        .filter(result => result.status === 'fulfilled')
        .map(result => (result as PromiseFulfilledResult<string>).value);
      setTaskIds(validIds);
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
    const folder = await getTaskFolderName(selectedTaskId);
    if (!folder) return;
    try {
      const res = await axios.get('http://localhost:8000/api/files/list/', {
        params: { filename: folder }
      });
      const files: string[] = res.data || [];
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
      setImages(res.data || []);
    } catch {
      message.error('获取图片失败');
    }
  };

  const handleGenerateNotes = async (selectedOnly: boolean) => {
    try {
      const res = await axios.post('http://localhost:8000/api/notes/generate-pages-script', {
        api_key: noteApiKey,
        prompt: notePrompt,
        task_id: selectedTaskId,
        pages: selectedOnly ? selectedImages : undefined
      });
      message.success('文稿生成成功');
      fetchTxtFiles();
    } catch {
      message.error('文稿生成失败');
    }
  };

  const getConfig = async (key: string) => {
    const res = await axios.get(`http://localhost:8000/api/tts/get-config/${key}`);
    return res.data.value;
  };

  const setConfig = async (key: string, value: string) => {
    await axios.post('http://localhost:8000/api/tts/set-config', { key, value });
    message.success(`${key} 设置成功`);
  };

  const deleteTask = async () => {
    Modal.confirm({
      title: '确定要删除此任务吗？',
      onOk: async () => {
        await axios.delete(`http://localhost:8000/api/tasks/${selectedTaskId}`);
        message.success('任务已删除');
        setSelectedTaskId('');
        fetchTasks();
      }
    });
  };

  const deleteSingleFile = async (filename: string) => {
    await axios.delete(`http://localhost:8000/api/files/delete/${filename}`);
    fetchGeneratedFiles();
  };

  const deleteAllFiles = async () => {
    await axios.delete('http://localhost:8000/api/files/clear');
    fetchGeneratedFiles();
  };

  const handleGenerateAll = async () => {
    if (!selectedTaskId) {
      message.warning('请先选择任务');
      return;
    }
    const folder = await getTaskFolderName(selectedTaskId);
    if (!folder) {
      message.error('未找到任务对应的文件夹');
      return;
    }
    setGenerating(true);
    setProgress(0);
    wsRef.current = new WebSocket(`ws://localhost:8000/api/tts/ws/generate`);
    wsRef.current.onmessage = (e) => {
      try {
        const data = JSON.parse(e.data);
        if (data.type === 'filename' && data.filename === folder && data.progress) {
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

  useEffect(() => {
    const init = async () => {
      await fetchTasks();
      setVoice(await getConfig('voice'));
      setSpeechKey(await getConfig('speech_key'));
      await fetchGeneratedFiles();
    };
    init();
  }, []);

  useEffect(() => {
    const update = async () => {
      await fetchTxtFiles();
      await fetchGeneratedFiles();
      await fetchImages();
    };
    update();
  }, [selectedTaskId]);

  return (
    <div style={{ padding: 24 }}>
      <h2>图片生成文稿、音频与字幕生成</h2>
      <Space>
        <Select
          placeholder="选择任务ID"
          value={selectedTaskId || undefined}
          onChange={setSelectedTaskId}
          style={{ width: 300 }}
        >
          {taskIds.map(t => <Option key={t} value={t}>{t}</Option>)}
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
            render: (row) => <img src={`http://localhost:8000/${row.image}`} style={{ height: 100 }} />
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
        }, {
          title: '操作',
          render: (_, record) => {
            const base = record.name.replace(/\.txt$/, '');
            return (
              <Space>
                <Button onClick={() => handleGenerateOne(record.name)}>生成</Button>
                <audio controls src={`http://localhost:8000/srt_and_wav/${base}.wav`} />
                <a href={`http://localhost:8000/srt_and_wav/${base}_merged.srt`} download>字幕</a>
                <a href={`http://localhost:8000/srt_and_wav/${base}.wav`} download>音频</a>
              </Space>
            );
          }
        }]}
      />

      <h3>音频文件</h3>
      <Table
        rowSelection={{
          selectedRowKeys: selectedFiles,
          onChange: (keys) => setSelectedFiles(keys as string[])
        }}
        dataSource={audioFiles.map(f => ({ key: f, name: f }))}
        columns={[{
          title: '音频',
          render: (row) => (
            <Space>
              <audio controls src={`http://localhost:8000/srt_and_wav/${row.name}`} />
              <Button danger onClick={() => deleteSingleFile(row.name)}>删除</Button>
            </Space>
          )
        }]}
      />

      <h3>字幕文件</h3>
      <Table
        rowSelection={{
          selectedRowKeys: selectedFiles,
          onChange: (keys) => setSelectedFiles(keys as string[])
        }}
        dataSource={subtitleFiles.map(f => ({ key: f, name: f }))}
        columns={[{
          title: '字幕',
          render: (row) => (
            <Space>
              <a href={`http://localhost:8000/srt_and_wav/${row.name}`} download>{row.name}</a>
              <Button danger onClick={() => deleteSingleFile(row.name)}>删除</Button>
            </Space>
          )
        }]}
      />

      {breakResults.length > 0 && (
        <Card title="Break 标签检查" style={{ marginTop: 32 }}>
          <Table
            dataSource={breakResults.map((r, i) => ({ ...r, key: i }))}
            columns={[
              { title: '文件名', dataIndex: 'filename' },
              { title: '是否存在', dataIndex: 'has_breaktime', render: (v: boolean) => v ? <Tag color="red">是</Tag> : <Tag color="green">否</Tag> },
              { title: '说明', dataIndex: 'message' }
            ]}
          />
        </Card>
      )}
    </div>
  );
};

export default TTSPage;
