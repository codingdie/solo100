"use client";

import { useEffect, useState } from "react";
import { api, Project, CreateProjectPayload } from "@/lib/api";

export function useProjects() {
  const [projects, setProjects] = useState<Project[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.projects
      .list()
      .then(setProjects)
      .catch((e: Error) => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  async function createProject(payload: CreateProjectPayload): Promise<Project> {
    const project = await api.projects.create(payload);
    setProjects((prev) => [...prev, project]);
    return project;
  }

  return { projects, loading, error, createProject };
}
