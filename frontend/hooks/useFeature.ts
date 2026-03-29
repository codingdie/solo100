"use client";

import { useCallback, useEffect, useState } from "react";
import { api, Feature, FeatureExecution, CreateFeaturePayload } from "@/lib/api";

export function useFeatures(projectId: string) {
  const [features, setFeatures] = useState<Feature[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(() => {
    setLoading(true);
    api.features
      .list(projectId)
      .then(setFeatures)
      .catch((e: Error) => setError(e.message))
      .finally(() => setLoading(false));
  }, [projectId]);

  useEffect(() => {
    refresh();
  }, [refresh]);

  async function createFeature(payload: CreateFeaturePayload): Promise<Feature> {
    const feature = await api.features.create(projectId, payload);
    setFeatures((prev) => [...prev, feature]);
    return feature;
  }

  return { features, loading, error, refresh, createFeature };
}

export function useFeature(featureId: string) {
  const [feature, setFeature] = useState<Feature | null>(null);
  const [executions, setExecutions] = useState<FeatureExecution[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(() => {
    Promise.all([
      api.features.get(featureId),
      api.features.executions(featureId),
    ])
      .then(([f, execs]) => {
        setFeature(f);
        setExecutions(execs);
      })
      .catch((e: Error) => setError(e.message))
      .finally(() => setLoading(false));
  }, [featureId]);

  useEffect(() => {
    refresh();
  }, [refresh]);

  return { feature, executions, loading, error, refresh, setFeature };
}
