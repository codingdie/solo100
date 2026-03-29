/**
 * Tests for lib/api.ts
 */
import { describe, it, expect, vi, beforeEach } from "vitest";
import { api } from "@/lib/api";

const mockFetch = vi.fn();
vi.stubGlobal("fetch", mockFetch);

function mockResponse(data: unknown, status = 200) {
  return Promise.resolve({
    ok: status >= 200 && status < 300,
    status,
    json: () => Promise.resolve(data),
    text: () => Promise.resolve(JSON.stringify(data)),
  });
}

beforeEach(() => {
  mockFetch.mockReset();
});

describe("api.projects", () => {
  it("list() calls GET /api/projects", async () => {
    const projects = [{ id: "p1", name: "Test", repo_url: "git@x.com:a/b.git" }];
    mockFetch.mockReturnValueOnce(mockResponse(projects));

    const result = await api.projects.list();

    expect(mockFetch).toHaveBeenCalledWith(
      expect.stringContaining("/api/projects"),
      expect.objectContaining({ headers: expect.any(Object) })
    );
    expect(result).toEqual(projects);
  });

  it("get() calls GET /api/projects/:id", async () => {
    const project = { id: "p1", name: "Test", repo_url: "git@x.com:a/b.git" };
    mockFetch.mockReturnValueOnce(mockResponse(project));

    const result = await api.projects.get("p1");
    expect(result).toEqual(project);
  });

  it("create() calls POST /api/projects with body", async () => {
    const project = { id: "p2", name: "New", repo_url: "git@x.com:a/c.git" };
    mockFetch.mockReturnValueOnce(mockResponse(project));

    const result = await api.projects.create({ name: "New", repo_url: "git@x.com:a/c.git" });

    expect(mockFetch).toHaveBeenCalledWith(
      expect.stringContaining("/api/projects"),
      expect.objectContaining({ method: "POST" })
    );
    expect(result).toEqual(project);
  });

  it("throws on non-ok response", async () => {
    mockFetch.mockReturnValueOnce(mockResponse({ detail: "Not found" }, 404));

    await expect(api.projects.get("missing")).rejects.toThrow("API 404");
  });
});

describe("api.features", () => {
  it("list() calls GET /api/projects/:id/features", async () => {
    mockFetch.mockReturnValueOnce(mockResponse([]));
    await api.features.list("p1");
    expect(mockFetch).toHaveBeenCalledWith(
      expect.stringContaining("/api/projects/p1/features"),
      expect.any(Object)
    );
  });

  it("create() calls POST with payload", async () => {
    const feature = { id: "f1", title: "Login", status: "pending" };
    mockFetch.mockReturnValueOnce(mockResponse(feature));

    const result = await api.features.create("p1", { title: "Login" });
    expect(result).toEqual(feature);
    expect(mockFetch).toHaveBeenCalledWith(
      expect.stringContaining("/api/projects/p1/features"),
      expect.objectContaining({ method: "POST" })
    );
  });
});

describe("api.approvals", () => {
  it("submit() calls POST /api/approvals/:id", async () => {
    mockFetch.mockReturnValueOnce(mockResponse({ ok: true }));

    const result = await api.approvals.submit("f1", { approved: true });
    expect(result).toEqual({ ok: true });
    expect(mockFetch).toHaveBeenCalledWith(
      expect.stringContaining("/api/approvals/f1"),
      expect.objectContaining({ method: "POST" })
    );
  });
});
