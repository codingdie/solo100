"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useState } from "react";
import { useFeatures } from "@/hooks/useFeature";
import { CreateFeaturePayload } from "@/lib/api";

export default function ProjectPage() {
  const { projectId } = useParams<{ projectId: string }>();
  const { features, loading, error, createFeature } = useFeatures(projectId);
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState<CreateFeaturePayload>({ title: "", description: "" });
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setSubmitting(true);
    try {
      await createFeature(form);
      setShowForm(false);
      setForm({ title: "", description: "" });
    } finally {
      setSubmitting(false);
    }
  }

  const statusColor: Record<string, string> = {
    pending: "bg-gray-100 text-gray-600",
    brainstorming: "bg-yellow-100 text-yellow-700",
    planning: "bg-blue-100 text-blue-700",
    implementing: "bg-indigo-100 text-indigo-700",
    testing: "bg-purple-100 text-purple-700",
    reviewing: "bg-orange-100 text-orange-700",
    approved: "bg-green-100 text-green-700",
    verifying: "bg-teal-100 text-teal-700",
    merged: "bg-green-200 text-green-800",
    failed: "bg-red-100 text-red-700",
  };

  return (
    <main className="max-w-4xl mx-auto p-6">
      <div className="mb-4">
        <Link href="/" className="text-sm text-blue-600 hover:underline">
          ← 返回项目列表
        </Link>
      </div>

      <div className="flex items-center justify-between mb-8">
        <h1 className="text-2xl font-bold">Feature 列表</h1>
        <button
          onClick={() => setShowForm(true)}
          className="px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700"
        >
          新建 Feature
        </button>
      </div>

      {showForm && (
        <form
          onSubmit={handleSubmit}
          className="mb-8 p-4 border rounded bg-white space-y-3"
        >
          <h2 className="font-semibold">新建 Feature</h2>
          <input
            required
            placeholder="Feature 标题"
            value={form.title}
            onChange={(e) => setForm({ ...form, title: e.target.value })}
            className="w-full border rounded px-3 py-2"
          />
          <textarea
            placeholder="描述（可选）"
            value={form.description}
            onChange={(e) => setForm({ ...form, description: e.target.value })}
            className="w-full border rounded px-3 py-2"
            rows={3}
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
        {features.map((f) => (
          <li key={f.id}>
            <Link
              href={`/projects/${projectId}/features/${f.id}`}
              className="block p-4 border rounded bg-white hover:shadow transition"
            >
              <div className="flex items-center justify-between">
                <span className="font-semibold">{f.title}</span>
                <span
                  className={`text-xs px-2 py-1 rounded-full ${statusColor[f.status] ?? "bg-gray-100"}`}
                >
                  {f.status}
                </span>
              </div>
              {f.description && (
                <div className="text-sm text-gray-500 mt-1">{f.description}</div>
              )}
            </Link>
          </li>
        ))}
        {!loading && features.length === 0 && (
          <li className="text-gray-400 text-sm">暂无 Feature，点击「新建 Feature」开始</li>
        )}
      </ul>
    </main>
  );
}
