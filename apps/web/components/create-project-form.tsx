"use client";

import { useRouter } from "next/navigation";
import { useState, type FormEvent } from "react";
import { Loader2, Plus } from "lucide-react";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { api } from "@/lib/api";
import { ApiError, ApiUnreachableError } from "@/lib/api-client";

/**
 * Project creation — two fields, per `07_System_Architecture.md`.
 *
 * "Every project begins with minimal onboarding by asking only for a project
 * name and a brief description, allowing users to enter the workspace
 * immediately without lengthy setup." No stack picker, no template gallery, no
 * wizard: the organization discovers requirements from the workspace.
 */
export function CreateProjectForm() {
  const router = useRouter();
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    if (submitting) return;

    setSubmitting(true);
    setError(null);

    try {
      const project = await api.createProject(name.trim(), description.trim());
      // Straight into the workspace, which is the point of asking for so little.
      router.push(`/projects/${project.id}`);
    } catch (cause) {
      if (cause instanceof ApiUnreachableError) {
        setError("Could not reach the API. Is it running on port 8000?");
      } else if (cause instanceof ApiError) {
        setError(cause.message);
      } else {
        setError("Something went wrong creating the project.");
      }
      setSubmitting(false);
    }
  }

  const ready = name.trim().length > 0 && description.trim().length > 0;

  return (
    <Card>
      <CardHeader>
        <CardTitle>Start a project</CardTitle>
        <p className="text-sm text-content-muted">
          A name and a description is all the organization needs. It works out the
          requirements from there.
        </p>
      </CardHeader>

      <CardContent>
        <form onSubmit={onSubmit} className="space-y-4">
          <div className="space-y-1.5">
            <label htmlFor="project-name" className="block text-xs text-content-subtle">
              Project name
            </label>
            <input
              id="project-name"
              value={name}
              onChange={(event) => setName(event.target.value)}
              maxLength={200}
              required
              placeholder="Hospital Management System"
              className="w-full rounded-md border border-border bg-canvas px-3 py-2 text-sm text-content placeholder:text-content-subtle focus:border-accent focus:outline-none"
            />
          </div>

          <div className="space-y-1.5">
            <label
              htmlFor="project-description"
              className="block text-xs text-content-subtle"
            >
              What is it?
            </label>
            <textarea
              id="project-description"
              value={description}
              onChange={(event) => setDescription(event.target.value)}
              maxLength={4000}
              required
              rows={3}
              placeholder="A platform for managing patients, appointments, billing, doctors, and hospital operations."
              className="w-full resize-y rounded-md border border-border bg-canvas px-3 py-2 text-sm text-content placeholder:text-content-subtle focus:border-accent focus:outline-none"
            />
          </div>

          {error && (
            <p role="alert" className="text-sm text-state-blocked">
              {error}
            </p>
          )}

          <button
            type="submit"
            disabled={!ready || submitting}
            className="inline-flex items-center gap-2 rounded-md bg-accent px-3.5 py-2 text-sm font-medium text-canvas transition-colors hover:bg-accent-hover disabled:cursor-not-allowed disabled:opacity-40"
          >
            {submitting ? (
              <Loader2 className="size-4 animate-spin" aria-hidden="true" />
            ) : (
              <Plus className="size-4" aria-hidden="true" />
            )}
            {submitting ? "Creating…" : "Create project"}
          </button>
        </form>
      </CardContent>
    </Card>
  );
}
