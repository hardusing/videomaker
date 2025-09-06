import React, { useState, useRef } from 'react';
import { 
  Card, 
  Button, 
  Upload, 
  List, 
  Row, 
  Col, 
  message, 
  Space, 
  Typography, 
  Progress, 
  Modal,
  Input,
  Divider,
  Tag,
  Tooltip
} from 'antd';
import { 
  UploadOutlined, 
  PlayCircleOutlined, 
  PauseCircleOutlined,
  DeleteOutlined,
  EyeOutlined,
  CloudUploadOutlined,
  VideoCameraOutlined,
  AudioOutlined,
  FileTextOutlined,
  PictureOutlined
} from '@ant-design/icons';
import type { UploadFile, UploadProps } from 'antd';

const { Title, Text } = Typography;
const { TextArea } = Input;

interface MediaFile {
  id: string;
  name: string;
  type: 'image' | 'audio' | 'subtitle';
  file: File;
  url: string;
  duration?: number;
}

interface TimelineItem {
  id: string;
  mediaId: string;
  startTime: number;
  duration: number;
  type: 'image' | 'audio' | 'subtitle';
}

const VideoEditor: React.FC = () => {
  const [mediaFiles, setMediaFiles] = useState<MediaFile[]>([]);
  const [timeline, setTimeline] = useState<TimelineItem[]>([]);
  const [isGenerating, setIsGenerating] = useState(false);
  const [progress, setProgress] = useState(0);
  const [videoTitle, setVideoTitle] = useState('');
  const [isPreviewVisible, setIsPreviewVisible] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  // 文件上传配置
  const uploadProps: UploadProps = {
    multiple: true,
    accept: '.png,.jpg,.jpeg,.wav,.mp3,.srt,.vtt',
    beforeUpload: (file) => {
      handleFileUpload(file);
      return false; // 阻止自动上传
    },
    showUploadList: false,
  };

  const handleFileUpload = (file: File) => {
    const fileType = getFileType(file.name);
    if (!fileType) {
      message.error('不支持的文件格式！');
      return;
    }

    const newFile: MediaFile = {
      id: Date.now().toString(),
      name: file.name,
      type: fileType,
      file: file,
      url: URL.createObjectURL(file),
    };

    setMediaFiles(prev => [...prev, newFile]);
    message.success(`${file.name} 上传成功！`);
  };

  const getFileType = (fileName: string): 'image' | 'audio' | 'subtitle' | null => {
    const ext = fileName.toLowerCase().split('.').pop();
    if (['png', 'jpg', 'jpeg', 'gif'].includes(ext || '')) return 'image';
    if (['wav', 'mp3', 'aac'].includes(ext || '')) return 'audio';
    if (['srt', 'vtt'].includes(ext || '')) return 'subtitle';
    return null;
  };

  const getFileIcon = (type: string) => {
    switch (type) {
      case 'image': return <PictureOutlined style={{ color: '#52c41a' }} />;
      case 'audio': return <AudioOutlined style={{ color: '#1890ff' }} />;
      case 'subtitle': return <FileTextOutlined style={{ color: '#fa8c16' }} />;
      default: return <UploadOutlined />;
    }
  };

  const getTypeTag = (type: string) => {
    const config = {
      image: { color: 'green', text: '图片' },
      audio: { color: 'blue', text: '音频' },
      subtitle: { color: 'orange', text: '字幕' }
    };
    const { color, text } = config[type as keyof typeof config];
    return <Tag color={color}>{text}</Tag>;
  };

  const removeFile = (id: string) => {
    setMediaFiles(prev => prev.filter(file => file.id !== id));
    // 同时从时间轴中移除相关项
    setTimeline(prev => prev.filter(item => item.mediaId !== id));
    message.success('文件已删除');
  };

  const addToTimeline = (mediaFile: MediaFile) => {
    const newTimelineItem: TimelineItem = {
      id: Date.now().toString(),
      mediaId: mediaFile.id,
      startTime: timeline.length * 5, // 默认每个项目5秒间隔
      duration: mediaFile.type === 'image' ? 5 : 10, // 图片默认5秒，音频默认10秒
      type: mediaFile.type,
    };

    setTimeline(prev => [...prev, newTimelineItem]);
    message.success(`${mediaFile.name} 已添加到时间轴`);
  };

  const removeFromTimeline = (id: string) => {
    setTimeline(prev => prev.filter(item => item.id !== id));
    message.success('已从时间轴移除');
  };

  const generateVideo = async () => {
    if (timeline.length === 0) {
      message.error('请先添加媒体文件到时间轴！');
      return;
    }

    if (!videoTitle.trim()) {
      message.error('请输入视频标题！');
      return;
    }

    setIsGenerating(true);
    setProgress(0);

    try {
      // 生成项目ID
      const projectId = `project_${Date.now()}`;

      // 首先上传所有媒体文件
      const uploadFormData = new FormData();
      uploadFormData.append('project_id', projectId);
      
      mediaFiles.forEach(mediaFile => {
        uploadFormData.append('files', mediaFile.file);
      });

      // 模拟进度更新
      const progressInterval = setInterval(() => {
        setProgress(prev => {
          if (prev >= 90) {
            clearInterval(progressInterval);
            return prev;
          }
          return prev + 10;
        });
      }, 500);

      // 上传媒体文件
      const uploadResponse = await fetch('http://localhost:8000/api/video-editor/upload-media', {
        method: 'POST',
        body: uploadFormData,
      });

      if (!uploadResponse.ok) {
        throw new Error('文件上传失败');
      }

      const uploadResult = await uploadResponse.json();
      
      // 更新timeline中的mediaId为服务器返回的文件ID
      const updatedTimeline = timeline.map(item => {
        const originalFile = mediaFiles.find(f => f.id === item.mediaId);
        if (!originalFile) return item;
        
        const uploadedFile = uploadResult.uploaded_files.find(
          (uf: any) => uf.original_name === originalFile.name
        );
        
        return uploadedFile ? { ...item, mediaId: uploadedFile.id } : item;
      });

      // 生成视频
      const generateFormData = new FormData();
      generateFormData.append('project_id', projectId);
      generateFormData.append('title', videoTitle);
      generateFormData.append('timeline', JSON.stringify(updatedTimeline));

      const generateResponse = await fetch('http://localhost:8000/api/video-editor/generate-video', {
        method: 'POST',
        body: generateFormData,
      });

      clearInterval(progressInterval);

      if (generateResponse.ok) {
        const result = await generateResponse.json();
        setProgress(100);
        message.success('视频生成任务已提交，正在后台处理...');
        
        // 可以在这里添加轮询检查生成状态的逻辑
        setTimeout(() => {
          message.info(`项目ID: ${projectId}，可通过此ID查询生成状态`);
        }, 1000);
        
      } else {
        const errorData = await generateResponse.json();
        throw new Error(errorData.detail || '视频生成失败');
      }
    } catch (error: any) {
      message.error(error.message || '视频生成失败，请稍后重试');
      console.error('Video generation error:', error);
    } finally {
      setIsGenerating(false);
      setTimeout(() => setProgress(0), 2000);
    }
  };

  const previewTimeline = () => {
    if (timeline.length === 0) {
      message.warning('时间轴为空，无法预览');
      return;
    }
    setIsPreviewVisible(true);
  };

  return (
    <div style={{ padding: '24px', backgroundColor: '#f0f2f5', minHeight: '100vh' }}>
      <Title level={2} style={{ textAlign: 'center', marginBottom: '32px' }}>
        <VideoCameraOutlined style={{ marginRight: '12px', color: '#1890ff' }} />
        视频编辑器
      </Title>

      <Row gutter={[24, 24]}>
        {/* 左侧：媒体库 */}
        <Col xs={24} lg={8}>
          <Card 
            title={
              <Space>
                <CloudUploadOutlined />
                媒体库
              </Space>
            }
            extra={
              <Upload {...uploadProps}>
                <Button type="primary" icon={<UploadOutlined />}>
                  上传文件
                </Button>
              </Upload>
            }
          >
            <div style={{ marginBottom: '16px' }}>
              <Text type="secondary">
                支持格式：图片(.png, .jpg, .jpeg)，音频(.wav, .mp3)，字幕(.srt, .vtt)
              </Text>
            </div>
            
            <List
              dataSource={mediaFiles}
              renderItem={(file) => (
                <List.Item
                  actions={[
                    <Tooltip title="添加到时间轴">
                      <Button 
                        type="text" 
                        icon={<PlayCircleOutlined />} 
                        onClick={() => addToTimeline(file)}
                      />
                    </Tooltip>,
                    <Tooltip title="删除文件">
                      <Button 
                        type="text" 
                        danger 
                        icon={<DeleteOutlined />} 
                        onClick={() => removeFile(file.id)}
                      />
                    </Tooltip>
                  ]}
                >
                  <List.Item.Meta
                    avatar={getFileIcon(file.type)}
                    title={
                      <Space>
                        <Text ellipsis style={{ maxWidth: '150px' }}>
                          {file.name}
                        </Text>
                        {getTypeTag(file.type)}
                      </Space>
                    }
                    description={`大小: ${(file.file.size / 1024 / 1024).toFixed(2)} MB`}
                  />
                </List.Item>
              )}
              locale={{ emptyText: '暂无媒体文件，请上传文件' }}
            />
          </Card>
        </Col>

        {/* 右侧：时间轴和控制面板 */}
        <Col xs={24} lg={16}>
          <Space direction="vertical" style={{ width: '100%' }} size="large">
            {/* 视频设置 */}
            <Card title="视频设置">
              <Row gutter={16}>
                <Col span={12}>
                  <Text strong>视频标题：</Text>
                  <Input
                    placeholder="请输入视频标题"
                    value={videoTitle}
                    onChange={(e) => setVideoTitle(e.target.value)}
                    style={{ marginTop: '8px' }}
                  />
                </Col>
                <Col span={12}>
                  <Text strong>操作：</Text>
                  <div style={{ marginTop: '8px' }}>
                    <Space>
                      <Button 
                        icon={<EyeOutlined />} 
                        onClick={previewTimeline}
                        disabled={timeline.length === 0}
                      >
                        预览
                      </Button>
                      <Button 
                        type="primary" 
                        icon={<VideoCameraOutlined />}
                        onClick={generateVideo}
                        loading={isGenerating}
                        disabled={timeline.length === 0 || !videoTitle.trim()}
                      >
                        生成视频
                      </Button>
                    </Space>
                  </div>
                </Col>
              </Row>
            </Card>

            {/* 时间轴 */}
            <Card 
              title={
                <Space>
                  <PlayCircleOutlined />
                  时间轴
                  <Text type="secondary">({timeline.length} 个项目)</Text>
                </Space>
              }
            >
              {timeline.length === 0 ? (
                <div style={{ 
                  textAlign: 'center', 
                  padding: '60px 20px',
                  background: '#fafafa',
                  border: '2px dashed #d9d9d9',
                  borderRadius: '6px'
                }}>
                  <VideoCameraOutlined style={{ fontSize: '48px', color: '#d9d9d9', marginBottom: '16px' }} />
                  <div>
                    <Text type="secondary">时间轴为空</Text>
                  </div>
                  <div>
                    <Text type="secondary">从左侧媒体库拖拽或点击添加文件</Text>
                  </div>
                </div>
              ) : (
                <List
                  dataSource={timeline}
                  renderItem={(item, index) => {
                    const mediaFile = mediaFiles.find(f => f.id === item.mediaId);
                    if (!mediaFile) return null;

                    return (
                      <List.Item
                        actions={[
                          <Text type="secondary">{item.startTime}s - {item.startTime + item.duration}s</Text>,
                          <Button 
                            type="text" 
                            danger 
                            icon={<DeleteOutlined />} 
                            onClick={() => removeFromTimeline(item.id)}
                          />
                        ]}
                      >
                        <List.Item.Meta
                          avatar={
                            <div style={{ 
                              width: '40px', 
                              height: '40px', 
                              background: '#f0f0f0', 
                              display: 'flex', 
                              alignItems: 'center', 
                              justifyContent: 'center',
                              borderRadius: '4px'
                            }}>
                              {getFileIcon(mediaFile.type)}
                            </div>
                          }
                          title={
                            <Space>
                              <Text>{index + 1}.</Text>
                              <Text ellipsis style={{ maxWidth: '200px' }}>
                                {mediaFile.name}
                              </Text>
                              {getTypeTag(mediaFile.type)}
                            </Space>
                          }
                          description={`持续时间: ${item.duration}秒`}
                        />
                      </List.Item>
                    );
                  }}
                />
              )}
            </Card>

            {/* 生成进度 */}
            {isGenerating && (
              <Card title="生成进度">
                <Progress 
                  percent={progress} 
                  status={progress === 100 ? 'success' : 'active'}
                  strokeColor={{
                    from: '#108ee9',
                    to: '#87d068',
                  }}
                />
                <Text type="secondary" style={{ marginTop: '8px', display: 'block' }}>
                  正在生成视频，请稍候...
                </Text>
              </Card>
            )}
          </Space>
        </Col>
      </Row>

      {/* 预览模态框 */}
      <Modal
        title="时间轴预览"
        open={isPreviewVisible}
        onCancel={() => setIsPreviewVisible(false)}
        footer={[
          <Button key="close" onClick={() => setIsPreviewVisible(false)}>
            关闭
          </Button>
        ]}
        width={800}
      >
        <div>
          <Title level={4}>视频标题: {videoTitle || '未设置'}</Title>
          <Divider />
          <Title level={5}>时间轴项目:</Title>
          {timeline.map((item, index) => {
            const mediaFile = mediaFiles.find(f => f.id === item.mediaId);
            return (
              <div key={item.id} style={{ 
                padding: '12px', 
                background: '#f9f9f9', 
                marginBottom: '8px',
                borderRadius: '6px',
                border: '1px solid #e8e8e8'
              }}>
                <Space>
                  <Text strong>{index + 1}.</Text>
                  {getFileIcon(item.type)}
                  <Text>{mediaFile?.name}</Text>
                  {getTypeTag(item.type)}
                  <Text type="secondary">
                    {item.startTime}s - {item.startTime + item.duration}s
                  </Text>
                </Space>
              </div>
            );
          })}
          <Divider />
          <Text type="secondary">
            总时长: {timeline.reduce((total, item) => Math.max(total, item.startTime + item.duration), 0)}秒
          </Text>
        </div>
      </Modal>
    </div>
  );
};

export default VideoEditor;
