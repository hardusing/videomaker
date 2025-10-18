import React, { useState } from 'react';
import { 
  Card, 
  Form, 
  Input, 
  Button, 
  Space, 
  Typography, 
  message, 
  Spin,
  Row,
  Col,
  Divider
} from 'antd';
import { FileTextOutlined, SendOutlined, DownloadOutlined } from '@ant-design/icons';

const { Title, Text } = Typography;
const { TextArea } = Input;

interface TextScriptResult {
  message: string;
  input_text: string;
  generated_script: string;
  output_file: string;
}

const TextScriptPage: React.FC = () => {
  const [form] = Form.useForm();
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<TextScriptResult | null>(null);

  const onFinish = async (values: any) => {
    setLoading(true);
    try {
      const formData = new FormData();
      formData.append('input_text', values.input_text);
      formData.append('api_key', values.api_key);
      if (values.prompt) {
        formData.append('prompt', values.prompt);
      }
      if (values.output_filename) {
        formData.append('output_filename', values.output_filename);
      }

      const response = await fetch('/api/notes/generate-text-script', {
        method: 'POST',
        body: formData,
      });

      if (response.ok) {
        const data = await response.json();
        setResult(data);
        message.success('讲稿生成成功！');
      } else {
        const errorData = await response.json();
        message.error(`生成失败：${errorData.detail || '未知错误'}`);
      }
    } catch (error) {
      console.error('API 调用失败:', error);
      message.error('网络错误，请稍后重试');
    } finally {
      setLoading(false);
    }
  };

  const downloadScript = () => {
    if (!result) return;
    
    const element = document.createElement('a');
    const file = new Blob([result.generated_script], { type: 'text/plain' });
    element.href = URL.createObjectURL(file);
    element.download = `${result.output_file.split('/').pop()}`;
    document.body.appendChild(element);
    element.click();
    document.body.removeChild(element);
  };

  const copyToClipboard = () => {
    if (!result) return;
    
    navigator.clipboard.writeText(result.generated_script).then(() => {
      message.success('讲稿已复制到剪贴板');
    }).catch(() => {
      message.error('复制失败，请手动复制');
    });
  };

  return (
    <div style={{ padding: '24px' }}>
      <Title level={2}>
        <FileTextOutlined /> 文字生成讲稿
      </Title>
      <Text type="secondary">
        输入您的文字内容，AI将为您生成专业的讲稿
      </Text>

      <Row gutter={24} style={{ marginTop: '24px' }}>
        <Col xs={24} lg={12}>
          <Card title="输入信息" bordered={false}>
            <Form
              form={form}
              layout="vertical"
              onFinish={onFinish}
              initialValues={{
                output_filename: 'generated_script',
                api_key: 'sk-xdtZS13EcaCHxoRbL50JDdP85EUKEhXtg4IcBKSKgF4ObTvW'
              }}
            >
              <Form.Item
                label="输入文字内容"
                name="input_text"
                rules={[{ required: true, message: '请输入要转换的文字内容' }]}
              >
                <TextArea
                  rows={8}
                  placeholder="请输入您想要转换成讲稿的文字内容..."
                  showCount
                  maxLength={5000}
                />
              </Form.Item>

              <Form.Item
                label="API Key"
                name="api_key"
                tooltip="已设置默认API Key，如需使用自定义API Key请修改此字段"
              >
                <Input.Password
                  placeholder="已设置默认API Key"
                />
              </Form.Item>

              <Form.Item
                label="自定义提示词"
                name="prompt"
                tooltip="可选：自定义AI生成讲稿的风格和要求"
              >
                <TextArea
                  rows={4}
                  placeholder="例如：请将文字转换成适合中学生理解的讲稿，语言要生动有趣..."
                />
              </Form.Item>

              <Form.Item
                label="输出文件名"
                name="output_filename"
                tooltip="可选：指定保存的文件名"
              >
                <Input
                  placeholder="generated_script"
                />
              </Form.Item>

              <Form.Item>
                <Space>
                  <Button
                    type="primary"
                    htmlType="submit"
                    loading={loading}
                    icon={<SendOutlined />}
                    size="large"
                  >
                    生成讲稿
                  </Button>
                  <Button
                    onClick={() => {
                      form.resetFields();
                      setResult(null);
                    }}
                  >
                    重置
                  </Button>
                </Space>
              </Form.Item>
            </Form>
          </Card>
        </Col>

        <Col xs={24} lg={12}>
          <Card 
            title="生成结果" 
            bordered={false}
            extra={
              result && (
                <Space>
                  <Button
                    icon={<DownloadOutlined />}
                    onClick={downloadScript}
                  >
                    下载
                  </Button>
                  <Button
                    onClick={copyToClipboard}
                  >
                    复制
                  </Button>
                </Space>
              )
            }
          >
            {loading && (
              <div style={{ textAlign: 'center', padding: '50px' }}>
                <Spin size="large" />
                <div style={{ marginTop: '16px' }}>
                  <Text>AI正在为您生成讲稿，请稍候...</Text>
                </div>
              </div>
            )}

            {!loading && !result && (
              <div style={{ textAlign: 'center', padding: '50px', color: '#999' }}>
                <FileTextOutlined style={{ fontSize: '48px', marginBottom: '16px' }} />
                <div>请在左侧输入内容并点击生成讲稿</div>
              </div>
            )}

            {!loading && result && (
              <div>
                <div style={{ marginBottom: '16px' }}>
                  <Text strong>文件保存位置：</Text>
                  <Text code>{result.output_file}</Text>
                </div>
                
                <Divider />
                
                <div style={{ marginBottom: '16px' }}>
                  <Text strong>原始输入：</Text>
                </div>
                <div style={{ 
                  padding: '12px', 
                  backgroundColor: '#f5f5f5', 
                  borderRadius: '6px',
                  marginBottom: '16px',
                  maxHeight: '150px',
                  overflowY: 'auto'
                }}>
                  <Text>{result.input_text}</Text>
                </div>

                <div style={{ marginBottom: '16px' }}>
                  <Text strong>生成的讲稿：</Text>
                </div>
                <div style={{ 
                  padding: '12px', 
                  backgroundColor: '#f9f9f9', 
                  borderRadius: '6px',
                  border: '1px solid #d9d9d9',
                  maxHeight: '400px',
                  overflowY: 'auto'
                }}>
                  <pre style={{ 
                    whiteSpace: 'pre-wrap', 
                    wordWrap: 'break-word',
                    margin: 0,
                    fontFamily: 'inherit'
                  }}>
                    {result.generated_script}
                  </pre>
                </div>
              </div>
            )}
          </Card>
        </Col>
      </Row>
    </div>
  );
};

export default TextScriptPage;
