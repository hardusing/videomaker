import React, { useState, useRef, useEffect } from 'react';
import {
  Card,
  Button,
  Upload,
  Form,
  Input,
  Select,
  message,
  Progress,
  Steps,
  Typography,
  Space,
  Divider,
  Alert,
  List,
  Tag,
  Row,
  Col,
  Spin,
  Timeline
} from 'antd';
import {
  UploadOutlined,
  PlayCircleOutlined,
  CheckCircleOutlined,
  LoadingOutlined,
  ExclamationCircleOutlined,
  FileTextOutlined,
  SoundOutlined,
  PictureOutlined,
  VideoCameraOutlined,
  ClockCircleOutlined
} from '@ant-design/icons';
import type { UploadFile, UploadProps } from 'antd';

const { Title, Text, Paragraph } = Typography;
const { TextArea } = Input;
const { Option } = Select;
const { Step } = Steps;

interface WorkflowStatus {
  workflow_id: string;
  status: 'initializing' | 'running' | 'completed' | 'failed';
  current_step: number;
  current_step_name: string;
  progress: number;
  step_progress: number;
  message: string;
  error?: string;
  results?: any;
}

interface WorkflowResults {
  ppt_file: string;
  pdf_file: string;
  images_processed: number;
  scripts_generated: number;
  audio_files: string[];
  subtitle_files: string[];
  output_directory: string;
  combined_script_file: string;
}

const WorkflowPage: React.FC = () => {
  const [form] = Form.useForm();
  const [fileList, setFileList] = useState<UploadFile[]>([]);
  const [isRunning, setIsRunning] = useState(false);
  const [workflowId, setWorkflowId] = useState<string>('');
  const [status, setStatus] = useState<WorkflowStatus | null>(null);
  const [results, setResults] = useState<WorkflowResults | null>(null);
  const [logs, setLogs] = useState<string[]>([]);
  const intervalRef = useRef<number | null>(null);

  // 工作流步骤定义
  const workflowSteps = [
    { title: 'PPT转PDF', icon: <FileTextOutlined />, description: '上传PPT并转换为PDF格式' },
    { title: 'PDF转图片', icon: <PictureOutlined />, description: '将PDF转换为图片序列' },
    { title: '添加黑边', icon: <PictureOutlined />, description: '为图片添加黑色边框' },
    { title: '生成脚本', icon: <FileTextOutlined />, description: 'AI生成讲解脚本' },
    { title: '生成音频', icon: <SoundOutlined />, description: '转换为音频和字幕' }
  ];

  // 文件上传配置
  const uploadProps: UploadProps = {
    accept: '.ppt,.pptx',
    beforeUpload: (file) => {
      const isPPT = file.type === 'application/vnd.ms-powerpoint' || 
                   file.type === 'application/vnd.openxmlformats-officedocument.presentationml.presentation' ||
                   file.name.toLowerCase().endsWith('.ppt') ||
                   file.name.toLowerCase().endsWith('.pptx');
      
      if (!isPPT) {
        message.error('只能上传PPT或PPTX文件！');
        return false;
      }

      const isLt100M = file.size / 1024 / 1024 < 100;
      if (!isLt100M) {
        message.error('文件大小不能超过100MB！');
        return false;
      }

      setFileList([file]);
      return false; // 阻止自动上传
    },
    fileList,
    onRemove: () => {
      setFileList([]);
    },
    maxCount: 1,
  };

  // 启动工作流
  const startWorkflow = async (values: any) => {
    if (fileList.length === 0) {
      message.error('请先上传PPT文件！');
      return;
    }

    setIsRunning(true);
    setStatus(null);
    setResults(null);
    setLogs([]);
    
    try {
      const formData = new FormData();
      formData.append('file', fileList[0] as any);
      formData.append('api_key', values.api_key);
      if (values.prompt) {
        formData.append('prompt', values.prompt);
      }
      formData.append('gender', values.gender || 'male');

      addLog('开始启动工作流...');

      const response = await fetch('http://localhost:8000/api/workflow/ppt-to-video', {
        method: 'POST',
        body: formData,
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || '工作流启动失败');
      }

      const result = await response.json();
      setWorkflowId(result.workflow_id);
      
      addLog(`工作流已启动，ID: ${result.workflow_id}`);
      message.success('工作流已启动，开始处理...');

      // 开始轮询状态
      startStatusPolling(result.workflow_id);

    } catch (error: any) {
      message.error(error.message || '工作流启动失败');
      setIsRunning(false);
      addLog(`错误: ${error.message}`);
    }
  };

  // 开始状态轮询
  const startStatusPolling = (id: string) => {
    if (intervalRef.current) {
      clearInterval(intervalRef.current);
    }

    intervalRef.current = setInterval(async () => {
      try {
        const response = await fetch(`http://localhost:8000/api/workflow/status/${id}`);
        if (response.ok) {
          const statusData: WorkflowStatus = await response.json();
          setStatus(statusData);
          
          addLog(`步骤${statusData.current_step}: ${statusData.current_step_name} - ${statusData.message}`);

          if (statusData.status === 'completed') {
            setIsRunning(false);
            message.success('工作流完成！');
            addLog('🎉 工作流执行完成！');
            
            // 获取详细结果
            fetchResults(id);
            
            if (intervalRef.current) {
              clearInterval(intervalRef.current);
            }
          } else if (statusData.status === 'failed') {
            setIsRunning(false);
            message.error('工作流执行失败');
            addLog(`❌ 工作流执行失败: ${statusData.error}`);
            
            if (intervalRef.current) {
              clearInterval(intervalRef.current);
            }
          }
        }
      } catch (error) {
        console.error('状态查询失败:', error);
      }
    }, 3000); // 每3秒查询一次
  };

  // 获取详细结果
  const fetchResults = async (id: string) => {
    try {
      const response = await fetch(`http://localhost:8000/api/workflow/results/${id}`);
      if (response.ok) {
        const resultsData = await response.json();
        setResults(resultsData.final_results);
        addLog('📊 结果详情已获取');
      }
    } catch (error) {
      console.error('获取结果失败:', error);
    }
  };

  // 添加日志
  const addLog = (message: string) => {
    const timestamp = new Date().toLocaleTimeString();
    setLogs(prev => [...prev, `[${timestamp}] ${message}`]);
  };

  // 重置工作流
  const resetWorkflow = () => {
    if (intervalRef.current) {
      clearInterval(intervalRef.current);
    }
    setIsRunning(false);
    setWorkflowId('');
    setStatus(null);
    setResults(null);
    setLogs([]);
    setFileList([]);
    form.resetFields();
  };

  // 组件卸载时清理定时器
  useEffect(() => {
    return () => {
      if (intervalRef.current) {
        clearInterval(intervalRef.current);
      }
    };
  }, []);

  // 获取当前步骤状态
  const getStepStatus = (stepIndex: number) => {
    if (!status) return 'wait';
    if (stepIndex < status.current_step - 1) return 'finish';
    if (stepIndex === status.current_step - 1) {
      if (status.status === 'failed') return 'error';
      if (status.status === 'completed') return 'finish';
      return 'process';
    }
    return 'wait';
  };

  return (
    <div style={{ padding: '24px', backgroundColor: '#f0f2f5', minHeight: '100vh' }}>
      <Title level={2} style={{ textAlign: 'center', marginBottom: '32px' }}>
        <VideoCameraOutlined style={{ marginRight: '12px', color: '#1890ff' }} />
        PPT到视频工作流
      </Title>

      <Row gutter={[24, 24]}>
        {/* 左侧：配置面板 */}
        <Col xs={24} lg={12}>
          <Card title="工作流配置" style={{ height: '100%' }}>
            <Form
              form={form}
              layout="vertical"
              onFinish={startWorkflow}
              disabled={isRunning}
            >
              <Form.Item
                label="上传PPT文件"
                required
                tooltip="支持PPT和PPTX格式，文件大小不超过100MB"
              >
                <Upload {...uploadProps}>
                  <Button icon={<UploadOutlined />} disabled={isRunning}>
                    选择PPT文件
                  </Button>
                </Upload>
                {fileList.length > 0 && (
                  <Text type="secondary" style={{ marginTop: '8px', display: 'block' }}>
                    已选择: {fileList[0].name} ({(fileList[0].size! / 1024 / 1024).toFixed(2)} MB)
                  </Text>
                )}
              </Form.Item>

              <Form.Item
                name="api_key"
                label="API密钥"
                rules={[{ required: true, message: '请输入API密钥' }]}
                tooltip="用于AI生成脚本的API密钥"
                initialValue="sk-xdtZS13EcaCHxoRbL50JDdP85EUKEhXtg4IcBKSKgF4ObTvW"
              >
                <Input.Password placeholder="请输入您的API密钥" />
              </Form.Item>

              <Form.Item
                name="gender"
                label="音频性别"
                initialValue="male"
                tooltip="选择生成音频的声音性别"
              >
                <Select>
                  <Option value="male">日语男声</Option>
                  <Option value="female">日语女声</Option>
                  <Option value="chinese_female">中文女声</Option>
                </Select>
              </Form.Item>

              <Form.Item
                name="prompt"
                label="自定义提示词"
                tooltip="可选：自定义AI生成脚本的提示词"
                initialValue={`JavaScript Basics Practical Course Script Generation - Requirements
Course Context

Generate lecture scripts for a JavaScript practical course covering fundamental programming concepts, including variables, data types, operators, functions, control flow, loops, arrays, objects, DOM manipulation, event handling, and small hands-on projects. The content is exclusively focused on JavaScript basics and practical usage. Content will be provided one slide at a time for slide-by-slide script generation.

Core Output Requirements

Use natural spoken language, approximately 4–5 minutes per slide (target: 800–900 English words per slide)

Explain concepts using relatable analogies and real-life examples

Include interactive questions with [PAUSE5] markers (at least 3 per slide)

Directly emphasize key points in the text

Provide a detailed explanation of any figures, diagrams, or code examples shown on the slide

output japanese

Audience Consideration

Targeted at complete beginners with zero programming background

No prior JavaScript or web development knowledge required

Must be highly beginner-friendly and accessible

Examples should match audience comprehension level

Avoid unnecessary technical jargon, unless fully explained

Content Guidelines

Use complete, natural sentences suitable for spoken audio

Avoid:

Overly complex technical jargon without explanation

Using any language other than English

Overusing enumerated lists — prefer storytelling style explanations

Parenthetical expressions (no brackets)

Adding Q&A sections at the end of slides

Talking about slide design or formatting

Repetitive phrasing between slides

Overusing rhetorical questions — vary teaching techniques

Filler words like Well, Okay, You know, etc.

Include:

References to previous slide content when relevant

Clear explanations of code examples and visuals

A conversational, teacher-to-student tone

At least 3 [PAUSE5] markers per slide to engage learners

Varied delivery style across slides to keep lessons dynamic

Focus strictly on JavaScript fundamentals and practical use cases

Process Requirements

Generate one script per slide

Do not merge content from multiple slides

Ensure script matches the current slide's topic

Explain all visual elements, diagrams, and code examples

Maintain a natural flow between slides

Input Format

[Previous page scripts]
...
[Content of the current page as image format]`}
              >
                <TextArea
                  rows={8}
                  placeholder="请为这张IT课程幻灯片生成详细的讲解脚本..."
                />
              </Form.Item>

              <Form.Item>
                <Space>
                  <Button
                    type="primary"
                    htmlType="submit"
                    loading={isRunning}
                    icon={<PlayCircleOutlined />}
                    size="large"
                  >
                    {isRunning ? '执行中...' : '开始执行工作流'}
                  </Button>
                  <Button onClick={resetWorkflow} disabled={isRunning}>
                    重置
                  </Button>
                </Space>
              </Form.Item>
            </Form>

            <Divider />

            {/* 工作流说明 */}
            <div>
              <Title level={4}>工作流程说明</Title>
              <Paragraph>
                <Text type="secondary">
                  此工作流将按顺序执行以下5个步骤：
                </Text>
              </Paragraph>
              <List
                size="small"
                dataSource={workflowSteps}
                renderItem={(item, index) => (
                  <List.Item>
                    <List.Item.Meta
                      avatar={item.icon}
                      title={`${index + 1}. ${item.title}`}
                      description={item.description}
                    />
                  </List.Item>
                )}
              />
            </div>
          </Card>
        </Col>

        {/* 右侧：进度显示 */}
        <Col xs={24} lg={12}>
          <Space direction="vertical" style={{ width: '100%' }} size="large">
            {/* 步骤进度 */}
            <Card title="执行进度">
              {status ? (
                <div>
                  <Steps
                    current={status.current_step - 1}
                    status={status.status === 'failed' ? 'error' : undefined}
                    direction="vertical"
                    size="small"
                  >
                    {workflowSteps.map((step, index) => (
                      <Step
                        key={index}
                        title={step.title}
                        description={step.description}
                        icon={step.icon}
                        status={getStepStatus(index)}
                      />
                    ))}
                  </Steps>
                  
                  <Divider />
                  
                  <div>
                    <Text strong>当前状态: </Text>
                    <Tag color={
                      status.status === 'completed' ? 'success' :
                      status.status === 'failed' ? 'error' :
                      status.status === 'running' ? 'processing' : 'default'
                    }>
                      {status.status === 'completed' ? '已完成' :
                       status.status === 'failed' ? '失败' :
                       status.status === 'running' ? '执行中' : '初始化'}
                    </Tag>
                  </div>
                  
                  <div style={{ marginTop: '16px' }}>
                    <Text>总体进度: </Text>
                    <Progress 
                      percent={status.progress} 
                      status={status.status === 'failed' ? 'exception' : 'active'}
                    />
                  </div>
                  
                  <div style={{ marginTop: '8px' }}>
                    <Text type="secondary">{status.message}</Text>
                  </div>

                  {status.error && (
                    <Alert
                      message="执行错误"
                      description={status.error}
                      type="error"
                      style={{ marginTop: '16px' }}
                      showIcon
                    />
                  )}
                </div>
              ) : (
                <div style={{ textAlign: 'center', padding: '40px' }}>
                  <ClockCircleOutlined style={{ fontSize: '48px', color: '#d9d9d9' }} />
                  <div style={{ marginTop: '16px' }}>
                    <Text type="secondary">等待开始执行工作流</Text>
                  </div>
                </div>
              )}
            </Card>

            {/* 执行结果 */}
            {results && (
              <Card title="执行结果" extra={<CheckCircleOutlined style={{ color: '#52c41a' }} />}>
                <Row gutter={[16, 16]}>
                  <Col span={12}>
                    <Text strong>原始文件:</Text>
                    <div>{results.ppt_file}</div>
                  </Col>
                  <Col span={12}>
                    <Text strong>PDF文件:</Text>
                    <div>{results.pdf_file}</div>
                  </Col>
                  <Col span={12}>
                    <Text strong>处理图片数:</Text>
                    <div>{results.images_processed} 张</div>
                  </Col>
                  <Col span={12}>
                    <Text strong>生成脚本数:</Text>
                    <div>{results.scripts_generated} 个</div>
                  </Col>
                  <Col span={12}>
                    <Text strong>音频文件数:</Text>
                    <div>{results.audio_files?.length || 0} 个</div>
                  </Col>
                  <Col span={12}>
                    <Text strong>字幕文件数:</Text>
                    <div>{results.subtitle_files?.length || 0} 个</div>
                  </Col>
                </Row>
                
                <Divider />
                
                <div>
                  <Text strong>输出目录:</Text>
                  <div style={{ marginTop: '8px' }}>
                    <Text code>{results.output_directory}</Text>
                  </div>
                </div>
                
                <div style={{ marginTop: '16px' }}>
                  <Text strong>合并脚本文件:</Text>
                  <div style={{ marginTop: '8px' }}>
                    <Text code>{results.combined_script_file}</Text>
                  </div>
                </div>
              </Card>
            )}

            {/* 执行日志 */}
            <Card title="执行日志" bodyStyle={{ maxHeight: '300px', overflow: 'auto' }}>
              {logs.length > 0 ? (
                <Timeline
                  items={logs.map((log, index) => ({
                    children: <Text style={{ fontSize: '12px' }}>{log}</Text>,
                    color: log.includes('错误') || log.includes('❌') ? 'red' :
                           log.includes('完成') || log.includes('🎉') ? 'green' : 'blue'
                  }))}
                />
              ) : (
                <div style={{ textAlign: 'center', padding: '20px' }}>
                  <Text type="secondary">暂无执行日志</Text>
                </div>
              )}
            </Card>
          </Space>
        </Col>
      </Row>
    </div>
  );
};

export default WorkflowPage;
