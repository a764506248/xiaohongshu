import { PlusOutlined, RightOutlined } from "@ant-design/icons";
import { Button, Input, Space, Table, Typography } from "antd";
import type { ColumnsType } from "antd/es/table";
import { useEffect, useMemo, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { contentApi } from "../api/content";
import { Notice } from "../components/Notice";
import { StatusBadge } from "../components/StatusBadge";
import type { ContentTask } from "../types";

const { Text } = Typography;

export function TaskList() {
  const navigate = useNavigate();
  const [tasks, setTasks] = useState<ContentTask[]>([]);
  const [keyword, setKeyword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    contentApi
      .listTasks()
      .then(setTasks)
      .catch((e: Error) => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  const completed = tasks.filter((task) => task.status === "completed").length;
  const active = tasks.filter(
    (task) => !["completed", "failed"].includes(task.status),
  ).length;
  const filteredTasks = useMemo(() => {
    const query = keyword.trim().toLowerCase();
    if (!query) return tasks;
    return tasks.filter((task) => task.title.toLowerCase().includes(query));
  }, [keyword, tasks]);

  const columns: ColumnsType<ContentTask> = [
    {
      title: "任务名称",
      dataIndex: "title",
      key: "title",
      ellipsis: true,
      render: (title: string, task) => (
        <Link className="task-title-link" to={`/tasks/${task.id}`}>
          {title}
        </Link>
      ),
    },
    {
      title: "状态",
      dataIndex: "status",
      key: "status",
      width: 150,
      render: (_, task) => <StatusBadge status={task.status} />,
    },
    {
      title: "更新时间",
      dataIndex: "updated_at",
      key: "updated_at",
      width: 180,
      responsive: ["md"],
      sorter: (a, b) =>
        new Date(a.updated_at).getTime() - new Date(b.updated_at).getTime(),
      defaultSortOrder: "descend",
      render: (value: string) => (
        <Text type="secondary">
          {new Date(value).toLocaleString("zh-CN", {
            month: "2-digit",
            day: "2-digit",
            hour: "2-digit",
            minute: "2-digit",
          })}
        </Text>
      ),
    },
    {
      title: "操作",
      key: "action",
      width: 90,
      align: "right",
      render: (_, task) => (
        <Link className="task-action-link" to={`/tasks/${task.id}`}>
          进入 <RightOutlined />
        </Link>
      ),
    },
  ];

  return (
    <main className="task-list-page">
      <div className="task-list-toolbar">
        <div>
          <h1>内容任务</h1>
          <Space size={18} split={<span className="task-stat-divider" />}>
            <Text type="secondary">全部 {tasks.length}</Text>
            <Text type="secondary">进行中 {active}</Text>
            <Text type="secondary">已完成 {completed}</Text>
          </Space>
        </div>
        <Space>
          <Input.Search
            allowClear
            placeholder="搜索任务名称"
            value={keyword}
            onChange={(event) => setKeyword(event.target.value)}
            className="task-search"
          />
          <Link to="/tasks/new">
            <Button type="primary" icon={<PlusOutlined />}>
              创建任务
            </Button>
          </Link>
        </Space>
      </div>

      {error && <Notice>{error}</Notice>}
      <Table<ContentTask>
        className="task-list-table"
        rowKey="id"
        size="middle"
        loading={loading}
        columns={columns}
        dataSource={filteredTasks}
        onRow={(task) => ({
          onDoubleClick: () => navigate(`/tasks/${task.id}`),
        })}
        locale={{ emptyText: keyword ? "没有匹配的任务" : "还没有内容任务" }}
        pagination={{
          defaultPageSize: 15,
          showSizeChanger: true,
          pageSizeOptions: [15, 30, 50],
          showTotal: (total) => `共 ${total} 条`,
        }}
        scroll={{ x: 720 }}
      />
    </main>
  );
}
