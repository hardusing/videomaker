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
      message.error('タスクリストの取得に失敗しました');
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
      message.error('TXTファイルの取得に失敗しました');
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
      console.log('フォルダに音声ファイルがないか、ディレクトリが存在しません');
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
      message.error('画像の取得に失敗しました');
    }
  };

  const fetchAvailableFolders = async () => {
    try {
      console.log('利用可能なフォルダを取得中...');
      // 使用 image-notes/images 接口获取 converted_images 目录下的所有图片
      const res = await axios.get('http://localhost:8000/api/image-notes/images');
             console.log('取得した画像データ:', res.data);
      
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
      
             console.log('抽出されたフォルダ:', folders);
      setAvailableFolders(folders);
    } catch (error) {
      console.error('利用可能なフォルダの取得に失敗:', error);
      message.error(`利用可能なフォルダの取得に失敗: ${error.response?.data?.detail || error.message}`);
    }
  };

  const fetchNotesFolders = async () => {
    try {
      console.log('notes_outputフォルダを取得中...');
      // 使用新的 notes-folders 接口获取 notes_output 目录下的所有文件夹
      const res = await axios.get('http://localhost:8000/api/notes/notes-folders');
             console.log('取得したnotesフォルダデータ:', res.data);
      
      const folders = res.data.folders || [];
      const folderNames = folders.map((folder: any) => folder.name);
      
             console.log('抽出されたnotesフォルダ:', folderNames);
      setNotesFolders(folderNames);
      setTtsFolders(folderNames); // 同时设置TTS文件夹列表
    } catch (error) {
      console.error('notesフォルダの取得に失敗:', error);
      message.error(`notesフォルダの取得に失敗: ${error.response?.data?.detail || error.message}`);
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
             message.success("原稿生成に成功しました");
      fetchTxtFiles();
    } catch (err) {
      console.error(err);
             message.error("原稿生成に失敗しました");
    }
  };

  const handleGenerateFolderScripts = async () => {
         if (!selectedFolder) {
       message.warning("フォルダを選択してください");
       return;
     }
     
     if (!noteApiKey) {
       message.warning("APIキーを入力してください");
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
      
             message.success(`原稿生成に成功しました！${selectedFolder}フォルダの画像を処理しました`);
      
      // 刷新文件列表（如果当前选中的任务对应该文件夹）
      fetchTxtFiles();
    } catch (err: any) {
      console.error(err);
             const errorMsg = err.response?.data?.detail || "原稿生成に失敗しました";
       message.error(errorMsg);
    } finally {
      setGeneratingFolder(false);
    }
  };

  const handleGenerateSelected = async () => {
    if (!selectedTtsFolder) return;
    const filesToGenerate = selectedFiles.length > 0 ? selectedFiles : txtFiles;
         if (filesToGenerate.length === 0) {
       message.warning("選択された原稿ファイルがありません");
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
                 console.error("WebSocket解析に失敗", e.data);
      }
    };

    try {
      await axios.post(`http://localhost:8000/api/tts/generate-selected?dir_name=${selectedTtsFolder}`, {
        filenames: filesToGenerate
      });
             message.success('選択された原稿の生成が完了しました');
      fetchGeneratedFiles();
    } catch (err) {
      console.error(err);
             message.error('生成に失敗しました');
    } finally {
      setGenerating(false);
      wsRef.current?.close();
    }
  };

  const handleGenerateTts = async () => {
         if (!selectedTtsFolder) {
       message.warning("フォルダを選択してください");
       return;
     }
     if (!ttsLanguage) {
       message.warning("言語の種類を選択してください");
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
      
             message.success('TTS音声生成に成功しました！');
      fetchGeneratedFiles(); // 刷新文件列表
    } catch (err: any) {
      console.error(err);
             const errorMsg = err.response?.data?.detail || "TTS音声生成に失敗しました";
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
             <h2>TTS 音声と字幕生成</h2>
      <Space>
                 <Select
           placeholder="フォルダを選択"
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
                 <Button onClick={fetchNotesFolders}>更新</Button>
         <Button danger onClick={deleteTask}>フォルダ削除</Button>
      </Space>

             <Card title="TTS 設定" style={{ marginTop: 16 }}>
        <Space direction="vertical" style={{ width: '100%' }}>
          <Input
            value={speechKey}
            onChange={(e) => setSpeechKey(e.target.value)}
            addonAfter={<Button onClick={() => setConfig('speech_key', speechKey)}>保存</Button>}
            placeholder="Speech Key"
          />
          
                     <div style={{ borderTop: '1px solid #f0f0f0', paddingTop: 16, marginTop: 16 }}>
             <h4>音声生成設定</h4>
                           <Select
                 value={ttsLanguage}
                 onChange={setTtsLanguage}
                 style={{ width: '100%', marginBottom: 8 }}
                 placeholder="言語の種類を選択"
               >
                 <Option value="male">日本語男性音声 (ja-JP-DaichiNeural)</Option>
                 <Option value="female">日本語女性音声 (ja-JP-NanamiNeural)</Option>
                 <Option value="chinese_female">中国語女性音声 (zh-CN-XiaoxiaoNeural)</Option>
               </Select>
                           <Button 
                 type="primary" 
                 onClick={handleGenerateTts} 
                 disabled={!selectedTtsFolder || !ttsLanguage || generatingTts}
                 loading={generatingTts}
                 style={{ width: '100%' }}
               >
                 {generatingTts ? '音声生成中...' : '音声生成'}
               </Button>
          </div>
        </Space>
      </Card>

             <Card title="原稿生成" style={{ marginTop: 24 }}>
        <div style={{ marginBottom: 16 }}>
                     <Input value={noteApiKey} onChange={(e) => setNoteApiKey(e.target.value)} placeholder="APIキーを入力してください" style={{ marginBottom: 8 }} />
           <Input.TextArea value={notePrompt} onChange={(e) => setNotePrompt(e.target.value)} placeholder="プロンプトを入力してください（オプション）" rows={2} style={{ marginBottom: 8 }} />
        </div>

                          <Card type="inner" title="フォルダ選択生成" style={{ marginBottom: 16 }}>
            <Space style={{ width: '100%' }} direction="vertical">
              <Space style={{ width: '100%' }}>
                                 <Select
                   placeholder="converted_images のフォルダを選択"
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
                                 <Button onClick={fetchAvailableFolders}>更新</Button>
              </Space>
                             <Button 
                 type="primary" 
                 onClick={handleGenerateFolderScripts} 
                 disabled={!selectedFolder || generatingFolder}
                 loading={generatingFolder}
                 style={{ width: '100%' }}
               >
                 {generatingFolder ? '生成中...' : 'このフォルダの全画像の原稿を生成'}
               </Button>
            </Space>
          </Card>
      </Card>

             <Space style={{ margin: '16px 0' }}>
         <Button onClick={handleSelectAllTxtFiles}>全原稿選択</Button>
         <Button onClick={handleSelectAllMediaFiles}>全音声・字幕選択</Button>
         <Button onClick={handleClearSelected}>選択解除</Button>
         <Button onClick={handleGenerateSelected}>選択原稿生成</Button>
         <Button onClick={handleDownloadSelectedMediaZip} disabled={!hasDownloadableMedia}>
           選択音声・字幕ダウンロード (ZIP)
         </Button>
         <Button onClick={handleCheckBreak}>break タグ確認</Button>
         <Button danger onClick={deleteAllFiles}>全削除</Button>
       </Space>

      {generating && <Progress percent={progress} status="active" style={{ marginTop: 10 }} />}

                                         <h3>原稿ファイル</h3>
        <Space style={{ marginBottom: 16 }}>
                     <Select
             placeholder="notes_output のフォルダを選択"
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
                     <Button onClick={fetchNotesFolders}>更新</Button>
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
               title: '原稿',
              render: (row) => (
                <a href={`http://localhost:8000/api/notes/${encodeURIComponent(row.name)}?dir_name=${encodeURIComponent(selectedNotesFolder)}`} target="_blank" rel="noopener noreferrer">{row.name}</a>
              )
            }]}
                         locale={{ emptyText: 'このフォルダに原稿ファイルがありません' }}
          />
        )}

             <h3>音声ファイル</h3>
      <Table
        rowSelection={{
          selectedRowKeys: selectedFiles,
          onChange: keys => setSelectedFiles(keys as string[]),
          hideSelectAll: true
        }}
        dataSource={audioFiles.map(f => ({ key: f, name: f }))}
                 columns={[{
           title: '音声',
          render: (row) => (
                         <Space>
               <audio controls src={`http://localhost:8000/srt_and_wav/${folderName}/${encodeURIComponent(row.name)}`} />
               <Button danger onClick={() => deleteSingleFile(row.name)}>削除</Button>
             </Space>
          )
        }]}
      />

             <h3>字幕ファイル</h3>
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
               <Button danger onClick={() => deleteSingleFile(row.name)}>削除</Button>
             </Space>
          )
        }]}
      />

             <Card title="Break タグ確認" style={{ marginTop: 32 }}>
        <Table
          dataSource={(breakResults || []).map((r, i) => ({ ...r, key: i }))}
                     columns={[
             { title: 'ファイル名', dataIndex: 'filename' },
             {
               title: '存在するか',
               dataIndex: 'has_breaktime',
               render: (v: boolean) =>
                 v ? <Tag color="red">はい</Tag> : <Tag color="green">いいえ</Tag>,
             },
             { title: '説明', dataIndex: 'message' },
           ]}
          pagination={false}
                     locale={{ emptyText: 'Break タグが検出されませんでした' }}
        />
      </Card>
    </div>
  );
};

export default TTSPage;