"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useFeature } from "@/hooks/useFeature";
import { useFeatureWebSocket } from "@/hooks/useFeatureWebSocket";
import { api } from "@/lib/api";
import { useState } from "react";

export default function FeaturePage() {
  const { projectId, featureId } = useParams<{
    projectId: string;
    featureId: string;
  }>();
  const { feature, executions, loading, error, refresh, setFeature } =
    useFeature(featureId);
  const { events, connected } = useFeatureWebSocket(featureId);
  const [approving, setApproving] = useState(false);

  // Merge WebSocket status updates into local feature state
  const latestStatusEvent = [...events]
    .reverse()
    .find((e) => e.type === "status_change");
  const displayStatus = latestStatusEvent?.data
    ? (latestStatusEvent.data as { new_status?: string }).new_status ??
      feature?.status
    : feature?.status;

  async function handleApproval(approved: boolean) {
    setApproving(true);
    try {
      await api.approvals.submit(featureId, { approved });
      refresh();
    } finally {
      setApproving(false);
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

  if (loading) return <p className="p-6 text-gray-500">加载中...</p>;
  if (error) return <p className="p-6 text-red-500">{error}</p>;
  if (!feature) return null;

  return (
    <main className="max-w-4xl mx-auto p-6 space-y-6">
      {/* Breadcrumb */}
      <div className="text-sm text-blue-600 space-x-2">
        <Link href="/" className="hover:underline">
          项目列表
        </Link>
        <span className="text-gray-400">/</span>
        <Link href={`/projects/${projectId}`} className="hover:underline">
          Feature 列表
        </Link>
      </div>

      {/* Header */}
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-2xl font-bold">{feature.title}</h1>
          {feature.description && (
            <p className="text-gray-500 mt-1">{feature.description}</p>
          )}
        </div>
        <div className="flex items-center gap-2">
          <span
            className={`text-sm px-3 py-1 rounded-full ${statusColor[displayStatus ?? "pending"] ?? "bg-gray-100"}`}
          >
            {displayStatus}
          </span>
          <span
            className={`text-xs px-2 py-1 rounded-full ${connected ? "bg-green-100 text-green-700" : "bg-gray-100 text-gray-500"}`}
          >
            {connected ? "实时" : "离线"}
          </span>
        </div>
      </div>

      {/* Approval panel */}
      {displayStatus === "reviewing" && (
        <div className="p-4 border border-orange-200 rounded bg-orange-50">
          <p className="font-semibold text-orange-800 mb-3">等待人工审批</p>
          <div className="flex gap-3">
            <button
              onClick={() => handleApproval(true)}
              disabled={approving}
              className="px-4 py-2 bg-green-600 text-white rounded hover:bg-green-700 disabled:opacity-50"
            >
              批准
            </button>
            <button
              onClick={() => handleApproval(false)}
              disabled={approving}
              className="px-4 py-2 bg-red-600 text-white rounded hover:bg-red-700 disabled:opacity-50"
            >
              拒绝
            </button>
          </div>
        </div>
      )}

      {/* Executions */}
      <section>
        <h2 className="text-lg font-semibold mb-3">执行阶段</h2>
        {executions.length === 0 ? (
          <p className="text-gray-400 text-sm">暂无执行记录</p>
        ) : (
          <ul className="space-y-2">
            {executions.map((ex) => (
              <li key={ex.id} className="p-3 border rounded bg-white">
                <div className="flex items-center justify-between">
                  <span className="font-medium capitalize">{ex.stage}</span>
                  <span
                    className={`text-xs px-2 py-0.5 rounded-full ${
                      ex.status === "completed"
                        ? "bg-green-100 text-green-700"
                        : ex.status === "failed"
                          ? "bg-red-100 text-red-700"
                          : "bg-yellow-100 text-yellow-700"
                    }`}
                  >
                    {ex.status}
                  </span>
                </div>
                {ex.error && (
                  <p className="text-red-500 text-sm mt-1">{ex.error}</p>
                )}
                {ex.output && (
                  <pre className="text-xs text-gray-600 mt-2 whitespace-pre-wrap bg-gray-50 p-2 rounded max-h-40 overflow-auto">
                    {ex.output}
                  </pre>
                )}
              </li>
            ))}
          </ul>
        )}
      </section>

      {/* Live event log */}
      <section>
        <h2 className="text-lg font-semibold mb-3">实时日志</h2>
        {events.length === 0 ? (
          <p className="text-gray-400 text-sm">暂无实时事件</p>
        ) : (
          <ul className="space-y-1 max-h-64 overflow-auto border rounded bg-gray-900 p-3">
            {events.map((ev, i) => (
              <li key={i} className="text-xs font-mono text-gray-200">
                <span className="text-gray-500 mr-2">
                  {ev.timestamp ? new Date(ev.timestamp).toLocaleTimeString() : ""}
                </span>
                <span className="text-yellow-400 mr-2">[{ev.type}]</span>
                {ev.message}
              </li>
            ))}
          </ul>
        )}
      </section>
    </main>
  );
}
