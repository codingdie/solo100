"use client";

import Link from "next/link";
import { useState } from "react";
import { useProjects } from "@/hooks/useProjects";
import { CreateProjectPayload } from "@/lib/api";

export default function HomePage() {
  const { projects, loading, error, createProject } = useProjects();
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState<CreateProjectPayload>({
    name: "",
    repo_url: "",
    branch: "main",
    description: "",
  });
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setSubmitting(true);
    try {
      await createProject(form);
      setShowForm(false);
      setForm({ name: "", repo_url: "", branch: "main", description: "" });
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <main className="max-w-4xl mx-auto p-6">
      <div className="flex items-center justify-between mb-8">
        <h1 className="text-2xl font-bold">solo100 项目</h1>
        <button
          onClick={() => setShowForm(true)}
          className="px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700"
        >
          新建项目
        </button>
      </div>

      {showForm && (
        <form
          onSubmit={handleSubmit}
          className="mb-8 p-4 border rounded bg-white space-y-3"
        >
          <h2 className="font-semibold">新建项目</h2>
          <input
            required
            placeholder="项目名称"
            value={form.name}
            onChange={(e) => setForm({ ...form, name: e.target.value })}
            className="w-full border rounded px-3 py-2"
          />
          <input
            required
            placeholder="Git 仓库地址"
            value={form.repo_url}
            onChange={(e) => setForm({ ...form, repo_url: e.target.value })}
            className="w-full border rounded px-3 py-2"
          />
          <input
            placeholder="分支 (默认 main)"
            value={form.branch}
            onChange={(e) => setForm({ ...form, branch: e.target.value })}
            className="w-full border rounded px-3 py-2"
          />
          <textarea
            placeholder="描述（可选）"
            value={form.description}
            onChange={(e) => setForm({ ...form, description: e.target.value })}
            className="w-full border rounded px-3 py-2"
            rows={2}
          />
          <div className="flex gap-2">
            <button
              type="submit"
              disabled={submitting}
              className="px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700 disabled:opacity-50"
            >
              {submitting ? "创建中..." : "创建"}
            </button>
            <button
              type="button"
              onClick={() => setShowForm(false)}
              className="px-4 py-2 border rounded hover:bg-gray-50"
            >
              取消
            </button>
          </div>
        </form>
      )}

      {loading && <p className="text-gray-500">加载中...</p>}
      {error && <p className="text-red-500">{error}</p>}

      <ul className="space-y-3">
        {projects.map((p) => (
          <li key={p.id}>
            <Link
              href={`/projects/${p.id}`}
              className="block p-4 border rounded bg-white hover:shadow transition"
            >
              <div className="font-semibold">{p.name}</div>
              {p.description && (
                <div className="text-sm text-gray-500 mt-1">{p.description}</div>
              )}
              <div className="text-xs text-gray-400 mt-1">{p.repo_url}</div>
            </Link>
          </li>
        ))}
        {!loading && projects.length === 0 && (
          <li className="text-gray-400 text-sm">暂无项目，点击「新建项目」开始</li>
        )}
      </ul>
    </main>
  );
}
