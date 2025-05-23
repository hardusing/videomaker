import React, { useState, useEffect } from "react";
import { Table, Button, Upload, message, Popconfirm, Modal, Steps } from "antd";
import {
  UploadOutlined,
  DeleteOutlined,
  DownloadOutlined,
} from "@ant-design/icons";
import type { UploadProps } from "antd";
import axios from "axios";

interface Picture {
  url: string;
  name: string;
  page: number;
}

interface PDFFile {
  name: string;
  created_at: string;
}

const UploadPage: React.FC = () => {
  const [projects, setProjects] = useState<PDFFile[]>([]);
  const [loading, setLoading] = useState(false);
  const [selectedPdf, setSelectedPdf] = useState<string | null>(null);
  const [pictures, setPictures] = useState<Picture[]>([]);
  const [pdfTaskMap, setPdfTaskMap] = useState<{ [pdfName: string]: string }>({});
  const [selectedTaskId, setSelectedTaskId] = useState<string | null>(null);
  const [previewVisible, setPreviewVisible] = useState(false);
  const [previewImages, setPreviewImages] = useState<Picture[]>([]);
  const [selectedRowKeys, setSelectedRowKeys] = useState<React.Key[]>([]);
  const [selectedRows, setSelectedRows] = useState<Picture[]>([]);
  const [blackBorderRefreshKey, setBlackBorderRefreshKey] = useState(Date.now());
  const picturesRef = React.useRef<HTMLDivElement>(null);
  const [currentStep, setCurrentStep] = useState(0);

  // PDF一覧を取得
  const fetchProjects = async () => {
    try {
      const response = await axios.get(
        "http://localhost:8000/api/pdf/upload/list"
      );
      // 兼容老格式和新格式
      let files: any[] = [];
      let map: { [pdfName: string]: string } = {};
      if (Array.isArray(response.data) && response.data.length > 0 && typeof response.data[0] === "object") {
        // 新格式 [{name, task_id}]
        files = response.data.map((item: any) => ({
          name: item.name || item.filename, // 兼容 filename 字段
          created_at: "",
        }));
        response.data.forEach((item: any) => {
          map[item.name || item.filename] = item.task_id;
        });
      } else {
        // 老格式 [filename, ...]
        files = response.data.map((filename: string) => ({
          name: filename,
          created_at: "",
        }));
      }
      setProjects(files);
      if (Object.keys(map).length > 0) {
        setPdfTaskMap(map);
      }
    } catch (error) {
      message.error("PDF取得失敗");
    }
  };

  useEffect(() => {
    const last = localStorage.getItem("lastSelectedPdf");
    if (last) {
      setSelectedPdf(last);
    }
    fetchProjects();
  }, []);

  // PDFアップロード
  const uploadProps: UploadProps = {
    name: "file",
    action: "http://localhost:8000/api/pdf/upload",
    accept: ".pdf",
    onChange(info) {
      if (info.file.status === "done") {
        message.success(`${info.file.name} PDFアップロード成功`);
        fetchProjects();
        const taskId = info.file.response?.task_id;
        if (taskId) {
          setPdfTaskMap(prev => ({ ...prev, [info.file.name]: taskId }));
          setSelectedTaskId(taskId);
          setSelectedPdf(info.file.name);
        }
      } else if (info.file.status === "error") {
        message.error(`${info.file.name} PDFアップロード失敗`);
      }
    },
  };

  // PDFから画像生成
  const handleConvert = async (pdfName: string) => {
    const taskId = pdfTaskMap[pdfName];
    if (!taskId) {
      message.error("タスクIDがありません。PDFをアップロードしてください。");
      return;
    }

    // 1. 生成前清空本地缓存和 state
    setPictures([]);
    localStorage.removeItem(`pictures_${pdfName}`);

    try {
      setLoading(true);
      setSelectedPdf(pdfName);
      setSelectedTaskId(taskId);

      // 2. 发送生成请求（流式接口，不处理流内容，只等返回即可）
      await axios.post(`http://localhost:8000/api/pdf/convert/${taskId}`);

      // 3. 生成后获取图片列表
      const imgRes = await axios.get("http://localhost:8000/api/image-notes/images", {
        params: { task_id: taskId }
      });
      const images: string[] = imgRes.data.images || [];
      const pictureList = images.map((img, index) => ({
        url: `http://localhost:8000/converted_images/${img}`,
        name: img.split("/").pop() || "",
        page: index + 1,
      }));
      setPictures(pictureList);
      localStorage.setItem(`pictures_${pdfName}`, JSON.stringify(pictureList));
      message.success("写真生成成功");
    } catch (error) {
      message.error("写真生成失敗");
    } finally {
      setLoading(false);
    }
  };

  // PDF削除
  const handleDeletePdf = async (pdfName: string) => {
    try {
      await axios.delete(`http://localhost:8000/api/pdf/upload/delete/${pdfName}`);
      message.success("PDF削除成功");
      fetchProjects();
      setPictures([]);
      localStorage.removeItem(`pictures_${pdfName}`);
      if (selectedPdf === pdfName) {
        setSelectedPdf(null);
        setSelectedTaskId(null);
      }
      setPdfTaskMap(prev => {
        const newMap = { ...prev };
        delete newMap[pdfName];
        return newMap;
      });
    } catch (error) {
      message.error("PDF削除失敗");
    }
  };

  // 写真削除
  const handleDeleteImage = async (imagePath: string) => {
    try {
      // imagePath 形如 "1(1)/1.png"
      const pdfName = selectedPdf?.replace(/\.pdf$/i, "");
      const imageId = imagePath.split("/").pop()?.replace(/\.png$/i, "");
      await axios.delete("http://localhost:8000/api/image-notes/image", {
        params: {
          task_id: pdfTaskMap[selectedPdf!], // 或 selectedTaskId
          black_bordered: false, // 删除黑边图片时传 true
        },
        data: {
          image_ids: [imageId],
        },
      });
      message.success("画像削除成功");
      // 前端同步移除
      const newPictures = pictures.filter((pic) => `${pdfName}/${pic.name}` !== imagePath);
      setPictures(newPictures);
      if (selectedPdf) {
        localStorage.setItem(`pictures_${selectedPdf}`, JSON.stringify(newPictures));
      }
    } catch (error) {
      console.error(error);
      message.error("画像削除失敗");
    }
  };

  // 写真ダウンロード
  const handleDownloadImage = async (url: string, name: string, page?: number) => {
    try {
      const response = await fetch(url);
      const blob = await response.blob();
      const link = document.createElement("a");
      // 用页码+原名，保证顺序
      link.download = page ? `${page}_${name}` : name;
      link.href = window.URL.createObjectURL(blob);
      link.click();
      window.URL.revokeObjectURL(link.href);
    } catch {
      message.error("画像ダウンロード失敗");
    }
  };

  // 黒枠追加
  const handleAddBlackBorder = async () => {
    if (!selectedPdf) {
      message.warning("PDFを選択してください");
      return;
    }
    const pdfName = selectedPdf.replace(/\.pdf$/i, "");
    try {
      await axios.get("http://localhost:8000/api/image-notes/add-black-border", {
        params: { pdf_name: pdfName }
      });
      message.success("黒枠追加成功");
      window.location.reload(); // 黑边生成后强制刷新页面
    } catch (error) {
      message.error("黒枠追加失敗");
    }
  };

  const handleShowPictures = (pdfName: string) => {
    const cached = localStorage.getItem(`pictures_${pdfName}`);
    if (cached) {
      setPictures(JSON.parse(cached));
      setSelectedPdf(pdfName);
      localStorage.setItem("lastSelectedPdf", pdfName);
      if (picturesRef.current) {
        picturesRef.current.scrollIntoView({ behavior: "smooth" });
      }
      window.location.reload(); // 强制刷新页面
    } else {
      message.info("まだ写真が生成されていません");
    }
  };

  const pdfColumns = [
    {
      title: "PDF名称",
      dataIndex: "name",
      key: "name",
    },
    // {
    //   title: "アップロード日時",
    //   dataIndex: "created_at",
    //   key: "created_at",
    //   render: (text: string) => text ? new Date(text).toLocaleString() : "-",
    // },
    {
      title: "操作",
      key: "action",
      render: (_: any, record: any) => {
        const cached = localStorage.getItem(`pictures_${record.name}`);
        let cachedPics: Picture[] = [];
        if (cached) {
          try {
            cachedPics = JSON.parse(cached);
          } catch {}
        }
        return (
          <>
            <Button
              type="primary"
              onClick={() => handleConvert(record.name)}
              loading={loading && selectedPdf === record.name}
              style={{ marginRight: 8 }}
            >
              写真生成
            </Button>
            <Button
              onClick={() => handleShowPictures(record.name)}
              disabled={!cachedPics.length}
              style={{ marginRight: 8 }}
            >
              写真一览
            </Button>
            <Popconfirm
              title="このPDFを削除しますか？"
              onConfirm={() => handleDeletePdf(record.name)}
              okText="はい"
              cancelText="いいえ"
            >
              <Button danger icon={<DeleteOutlined />}>
                削除
              </Button>
            </Popconfirm>
          </>
        );
      },
    },
  ];

  const pictureColumns = [
    {
      title: "ページ",
      dataIndex: "page",
      key: "page",
    },
    {
      title: "画像",
      dataIndex: "url",
      key: "url",
      render: (url: string) => (
        <img
          src={url}
          alt="preview"
          style={{
            width: 150,
            height: "auto",
            border: "1px solid #ddd",
            borderRadius: 4,
          }}
        />
      ),
    },
    {
      title: "黒枠画像",
      key: "blackBordered",
      render: (_: any, record: Picture) => {
        if (!selectedPdf) return null;
        const pdfName = selectedPdf.replace(/\.pdf$/i, "");
        const blackUrl = `http://localhost:8000/processed_images/${pdfName}/${record.name}?t=${blackBorderRefreshKey}`;
        return (
          <img
            src={blackUrl}
            alt="black-bordered"
            style={{
              width: 150,
              height: "auto",
              border: "1px solid #222",
              borderRadius: 4,
            }}
            onError={e => (e.currentTarget.style.display = "none")}
          />
        );
      }
    },
  ];

  useEffect(() => {
    if (selectedPdf) {
      const saved = localStorage.getItem(`pictures_${selectedPdf}`);
      if (saved) {
        setPictures(JSON.parse(saved));
      } else {
        setPictures([]);
      }
    } else {
      setPictures([]);
    }
  }, [selectedPdf]);

  const rowSelection = {
    selectedRowKeys,
    onChange: (keys: React.Key[], rows: Picture[]) => {
      setSelectedRowKeys(keys);
      setSelectedRows(rows);
    },
  };

  const handleBatchDownload = () => {
    selectedRows.forEach(pic => {
      handleDownloadImage(pic.url, pic.name, pic.page);
    });
  };

  const handleDownloadAll = () => {
    pictures.forEach(pic => {
      handleDownloadImage(pic.url, pic.name, pic.page);
    });
  };

// 全部削除
const handleBatchDeleteAll = async () => {
  if (!selectedPdf || pictures.length === 0) return;

  const pdfName = selectedPdf.replace(/\.pdf$/i, "");
  const taskId = pdfTaskMap[selectedPdf];
  const imageIds = pictures.map(pic => pic.name.replace(/\.png$/i, ""));

  try {
    await axios.delete("http://localhost:8000/api/image-notes/image", {
      params: {
        task_id: taskId,
        black_bordered: false,
      },
      data: {
        image_ids: imageIds,
      },
    });

    message.success("すべての画像を削除しました");
    setPictures([]);
    setSelectedRowKeys([]);
    setSelectedRows([]);
    localStorage.removeItem(`pictures_${selectedPdf}`);
  } catch (error) {
    console.error(error);
    message.error("画像削除に失敗しました");
  }
};

  const handleBatchDelete = async () => {
    if (!selectedPdf || selectedRows.length === 0) return;
    const pdfName = selectedPdf.replace(/\.pdf$/i, "");
    const taskId = pdfTaskMap[selectedPdf];
    const imageIds = selectedRows.map(pic => pic.name.replace(/\.png$/i, "")); // 去掉扩展名

    try {
      await axios.delete("http://localhost:8000/api/image-notes/image", {
        params: {
          task_id: taskId,
          black_bordered: false,
        },
        data: {
          image_ids: imageIds,
        },
      });
      message.success("画像削除成功");
      // 前端同步移除
      const newPictures = pictures.filter(
        (pic) => !imageIds.includes(pic.name.replace(/\.png$/i, ""))
      );
      setPictures(newPictures);
      setSelectedRowKeys([]);
      setSelectedRows([]);
      if (selectedPdf) {
        localStorage.setItem(`pictures_${selectedPdf}`, JSON.stringify(newPictures));
      }
    } catch (error) {
      message.error("画像削除失敗");
    }
  };

  return (
    <div style={{ padding: 24 }}>
      <Steps
        current={currentStep}
        items={[
          { title: "PDF上传" },
          { title: "写真生成" },
          { title: "写真下载" },
        ]}
        style={{ marginBottom: 32, maxWidth: 600 }}
      />
      <Upload {...uploadProps} showUploadList={false}>
        <Button icon={<UploadOutlined />}>PDFをアップロード</Button>
      </Upload>

      <div
        style={{
          maxWidth: 1500,
          margin: "32px auto 0 auto",
          background: "#fff",
          borderRadius: 16,
          boxShadow: "0 4px 24px rgba(0,0,0,0.08)",
          padding: 32,
        }}
      >
        <div style={{ marginTop: 32 }}>
          <h2 style={{ marginBottom: 24, letterSpacing: 2 }}>
            PDF一覧
          </h2>
          <Table
            style={{
              borderRadius: 8,
              background: "#fff",
              boxShadow: "0 1px 4px rgba(0,0,0,0.04)",
            }}
            columns={pdfColumns}
            dataSource={projects}
            rowKey="name"
            pagination={false}
          />
        </div>
      </div>

      {pictures.length > 0 && (
        <div
          ref={picturesRef}
          style={{
            maxWidth: 1500,
            margin: "40px auto 0 auto",
            background: "#fff",
            borderRadius: 16,
            boxShadow: "0 4px 24px rgba(0,0,0,0.08)",
            padding: 32,
          }}
        >
          <h2 style={{ marginBottom: 24, letterSpacing: 2 }}>写真一覧</h2>
          <Button
              onClick={handleBatchDownload}
              disabled={selectedRowKeys.length === 0}
              style={{ marginRight: 8 }}
            >
              選択した写真をダウンロード
            </Button>
            <Button
              onClick={handleDownloadAll}
              disabled={pictures.length === 0}
            >
              全部ダウンロード
            </Button>
            <Button
              onClick={handleBatchDelete}
              disabled={selectedRowKeys.length === 0}
              danger
              style={{ marginLeft: 8, marginRight: 8 }}
            >
              選択した写真を削除
            </Button>
            <Button
              onClick={handleBatchDeleteAll}
              disabled={pictures.length === 0}
            >
              全ての写真を削除
            </Button>
            <Button
              onClick={handleAddBlackBorder}
              disabled={!selectedPdf}
            >
              黒枠追加
            </Button>
          <Table
            rowSelection={rowSelection}
            dataSource={pictures}
            columns={pictureColumns}
            rowKey="name"
            pagination={{ pageSize: 5 }}
            style={{
              borderRadius: 8,
              background: "#fff",
              boxShadow: "0 1px 4px rgba(0,0,0,0.04)",
            }}
          />
          <div
            style={{
              display: "flex",
              alignItems: "center",
              marginTop: 24,
              flexWrap: "wrap",
              gap: 8,
              justifyContent: "flex-start", // 靠左排列
            }}
          >
            
          </div>
        </div>
      )}

      <Modal
        open={previewVisible}
        title="画像プレビュー"
        footer={null}
        onCancel={() => setPreviewVisible(false)}
        width={800}
      >
        <div style={{ display: "flex", flexWrap: "wrap", gap: 16 }}>
          {previewImages.map((pic) => (
            <img
              key={pic.url}
              src={pic.url}
              alt={pic.name}
              style={{
                width: 150,
                height: "auto",
                border: "1px solid #ddd",
                borderRadius: 4,
              }}
            />
          ))}
          {previewImages.length === 0 && <div>画像がありません</div>}
        </div>
      </Modal>
    </div>
  );
};

export default UploadPage;