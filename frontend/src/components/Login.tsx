import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Form, Input, Button, Card, message } from 'antd';
import { UserOutlined, LockOutlined } from '@ant-design/icons';
import { useDispatch, useSelector } from 'react-redux';
import { loginStart, loginSuccess, loginFailure } from '../store/slices/authSlice';
import type { RootState } from '../store';
import './Login.css';

interface LoginForm {
  username: string;
  password: string;
}

const Login: React.FC = () => {
  const dispatch = useDispatch();
  const navigate = useNavigate();
  const { loading, error } = useSelector((state: RootState) => state.auth);

  const onFinish = async (values: LoginForm) => {
    dispatch(loginStart());
    try {
      const response = await fetch('/api/auth/login', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(values),
      });

      if (response.ok) {
        const data = await response.json();
        localStorage.setItem('token', data.token);
        dispatch(loginSuccess(data.token));
        message.success('登录成功');
        navigate('/dashboard');
      } else {
        const errorData = await response.json();
        dispatch(loginFailure(errorData.message || '用户名或密码错误'));
        message.error(errorData.message || '用户名或密码错误');
      }
    } catch (error) {
      dispatch(loginFailure('登录失败，请稍后重试'));
      message.error('登录失败，请稍后重试');
    }
  };

  return (
    <div className="login-container">
      <Card className="login-card">
        <h2 className="login-title">视频制作系统</h2>
        <Form
          name="login"
          onFinish={onFinish}
          autoComplete="off"
        >
          <Form.Item
            name="username"
            rules={[{ required: true, message: '请输入用户名' }]}
          >
            <Input 
              prefix={<UserOutlined />} 
              placeholder="用户名" 
              size="large"
            />
          </Form.Item>

          <Form.Item
            name="password"
            rules={[{ required: true, message: '请输入密码' }]}
          >
            <Input.Password
              prefix={<LockOutlined />}
              placeholder="密码"
              size="large"
            />
          </Form.Item>

          {error && (
            <div className="error-message">{error}</div>
          )}

          <Form.Item>
            <Button 
              type="primary" 
              htmlType="submit"
              loading={loading}
              size="large"
              className="login-button"
            >
              登录
            </Button>
          </Form.Item>
        </Form>
      </Card>
    </div>
  );
};

export default Login; 