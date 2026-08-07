"use client";

import { useRouter } from "next/navigation";
import { useState, type FormEvent } from "react";
import { CircleAlert, Loader2, Plus } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Field, Input, Textarea } from "@/components/ui/field";
import { api } from "@/lib/api";
import { ApiError, ApiUnreachableError } from "@/lib/api-client";

/**
 * Project creation — two fields, per `07_System_Architecture.md`.
 *
 * "Every project begins with minimal onboarding by asking only for a project
 * name and a brief description, allowing users to enter the workspace
 * immediately without lengthy setup." No stack picker, no template gallery, no
 * wizard: the organization discovers requirements from the workspace.
 *
 * The form says so in its own copy, because a two-field form is unusual enough
 * that a user's first instinct is to look for the rest of it.
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
        <p className="text-sm leading-relaxed text-content-muted">
          A name and a description is all the organization needs. It works out the
          requirements from there.
        </p>
      </CardHeader>

      <CardContent>
        <form onSubmit={onSubmit} className="space-y-4">
          <div className="grid gap-4 sm:grid-cols-2">
            <Field label="Project name" htmlFor="project-name">
              <Input
                id="project-name"
                value={name}
                onChange={(event) => setName(event.target.value)}
                maxLength={200}
                required
                placeholder="Hospital Management System"
              />
            </Field>

            <Field
              label="What is it?"
              htmlFor="project-description"
              hint="One or two sentences. The Product Manager expands this into requirements."
            >
              <Textarea
                id="project-description"
                value={description}
                onChange={(event) => setDescription(event.target.value)}
                maxLength={4000}
                required
                rows={3}
                placeholder="A platform for managing patients, appointments, billing, doctors, and hospital operations."
              />
            </Field>
          </div>

          {error && (
            <p
              role="alert"
              className="flex animate-[fade-in_0.25s_ease-out_both] items-center gap-2 rounded-lg border border-state-blocked/30 bg-state-blocked/[0.08] px-3 py-2 text-sm text-state-blocked"
            >
              <CircleAlert className="size-4 shrink-0" aria-hidden="true" />
              {error}
            </p>
          )}

          <Button type="submit" disabled={!ready || submitting}>
            {submitting ? (
              <Loader2 className="animate-spin" aria-hidden="true" />
            ) : (
              <Plus aria-hidden="true" />
            )}
            {submitting ? "Creating…" : "Create project"}
          </Button>
        </form>
      </CardContent>
    </Card>
  );
}
