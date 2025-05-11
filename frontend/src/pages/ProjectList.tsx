import React, { useState, useEffect } from "react";
import { Table, Button, Upload, message } from "antd";
import { UploadOutlined } from "@ant-design/icons";
import type { UploadProps } from "antd";
import axios from "axios";

const ProjectList: React.FC = () => {
  const [projects, setProjects] = useState([]);
  const [loading, setLoading] = useState(false);

  const fetchProjects = async () => {
    try {
      const response = await axios.get("http://localhost:8000/api/v1/projects");
      setProjects(response.data);
    } catch (error) {
      message.error("获取项目列表失败");
    }
  };

  useEffect(() => {
    fetchProjects();
  }, []);

  const [notes, setNotes] = useState([]); // 新增：保存返回的notes

  const handleExtract = async (id: number) => {
    try {
      setLoading(true);
      const res = await axios.post(
        `http://localhost:8000/api/v1/projects/${id}/extract`
      );
      message.success("笔记提取成功");
      setNotes(res.data.notes); // ✅ 保存提取结果
    } catch (error) {
      message.error("笔记提取失败");
    } finally {
      setLoading(false);
    }
  };
  const uploadProps: UploadProps = {
    name: "file",
    action: "http://localhost:8000/api/v1/projects/upload",
    accept: ".pptx,.ppt",
    onChange(info) {
      if (info.file.status === "done") {
        message.success(`${info.file.name} 上传成功`);
        fetchProjects();
      } else if (info.file.status === "error") {
        message.error(`${info.file.name} 上传失败`);
      }
    },
  };

  const columns = [
    {
      title: "项目名称",
      dataIndex: "name",
      key: "name",
    },
    {
      title: "创建时间",
      dataIndex: "created_at",
      key: "created_at",
      render: (text: string) => new Date(text).toLocaleString(),
    },
    {
      title: "操作",
      key: "action",
      render: (_: any, record: any) => (
        <Button
          type="primary"
          onClick={() => handleExtract(record.id)}
          loading={loading}
        >
          提取笔记
        </Button>
      ),
    },
  ];

  return (
    <div>
      <div style={{ marginBottom: 16 }}>
        <Upload {...uploadProps}>
          <Button icon={<UploadOutlined />}>上传PPT</Button>
        </Upload>
      </div>

      {/* ✅ 项目列表（含提取按钮） */}
      <Table
        columns={columns}
        dataSource={projects}
        rowKey="id"
        pagination={false}
      />

      {/* ✅ 提取后的 notes 展示 */}
      {notes.length > 0 && (
        <div style={{ marginTop: 24 }}>
          <h3>提取结果</h3>
          <Table
            dataSource={notes}
            rowKey="page"
            columns={[
              { title: "页码", dataIndex: "page", key: "page" },
              { title: "备注内容", dataIndex: "content", key: "content" },
            ]}
            pagination={false}
          />
        </div>
      )}
    </div>
  );
};

export default ProjectList;
