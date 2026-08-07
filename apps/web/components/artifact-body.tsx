"use client";

import Markdown from "react-markdown";
import remarkGfm from "remark-gfm";

import { MermaidDiagram } from "@/components/mermaid-diagram";
import { cn } from "@/lib/utils";

/**
 * Renders an engineering artifact's markdown body.
 *
 * `react-markdown` is used rather than a raw HTML pipeline because it never
 * renders raw HTML: artifact bodies contain model-generated text derived from a
 * user-supplied project description, so treating that content as trusted markup
 * would be an injection path straight through the workspace.
 *
 * GFM is enabled for tables — nearly every artifact the organization produces
 * renders its structured data as one.
 */
export function ArtifactBody({ markdown }: { markdown: string }) {
  return (
    <div className="max-w-none text-sm leading-[1.75] text-content-muted">
      <Markdown
        remarkPlugins={[remarkGfm]}
        components={{
          h1: ({ children }) => (
            <h1 className="mt-9 mb-4 text-xl font-semibold tracking-tight text-balance text-content first:mt-0">
              {children}
            </h1>
          ),
          h2: ({ children }) => (
            <h2 className="mt-8 mb-3 border-b border-border pb-2 text-base font-semibold tracking-tight text-content">
              {children}
            </h2>
          ),
          h3: ({ children }) => (
            <h3 className="mt-6 mb-2 text-sm font-semibold text-content">{children}</h3>
          ),
          p: ({ children }) => <p className="my-3">{children}</p>,
          ul: ({ children }) => (
            <ul className="my-3 list-disc space-y-1 pl-5">{children}</ul>
          ),
          ol: ({ children }) => (
            <ol className="my-3 list-decimal space-y-1 pl-5">{children}</ol>
          ),
          li: ({ children }) => <li className="pl-1 marker:text-content-subtle">{children}</li>,
          strong: ({ children }) => (
            <strong className="font-medium text-content">{children}</strong>
          ),
          em: ({ children }) => <em className="text-content-subtle">{children}</em>,
          a: ({ children, href }) => (
            <a
              href={href}
              className="text-accent underline underline-offset-2 hover:text-accent-hover"
              rel="noopener noreferrer"
            >
              {children}
            </a>
          ),
          blockquote: ({ children }) => (
            <blockquote className="my-4 rounded-r-lg border-l-2 border-accent-muted bg-surface-raised/40 py-2 pr-3 pl-4 text-content-subtle">
              {children}
            </blockquote>
          ),
          hr: () => (
            <hr className="my-7 h-px border-0 bg-gradient-to-r from-border via-border to-transparent" />
          ),

          // Tables are how nearly every artifact presents its structured data,
          // and they are frequently wider than the column. The wrapper scrolls
          // so the page itself never does.
          table: ({ children }) => (
            <div className="my-5 overflow-x-auto rounded-lg border border-border elevated">
              <table className="w-full border-collapse text-xs">{children}</table>
            </div>
          ),
          thead: ({ children }) => (
            <thead className="bg-surface-raised text-left">{children}</thead>
          ),
          th: ({ children }) => (
            <th className="border-b border-border px-3 py-2.5 text-[11px] font-medium tracking-wide whitespace-nowrap text-content uppercase">
              {children}
            </th>
          ),
          td: ({ children }) => (
            <td className="border-b border-border/70 px-3 py-2.5 align-top">{children}</td>
          ),

          // `pre` is flattened because the `code` renderer below emits the block
          // wrapper itself; leaving both would nest two scroll containers.
          pre: ({ children }) => <>{children}</>,

          code: ({ className, children }) => {
            const language = /language-(\w+)/.exec(className ?? "")?.[1];
            const source = String(children).replace(/\n$/, "");

            if (language === "mermaid") {
              return <MermaidDiagram chart={source} />;
            }

            if (!language) {
              return (
                <code className="rounded border border-border/70 bg-surface-raised px-1.5 py-0.5 font-mono text-[0.85em] text-content">
                  {children}
                </code>
              );
            }

            return (
              <div className="my-5 overflow-hidden rounded-lg border border-border elevated">
                <div className="flex items-center gap-1.5 border-b border-border bg-surface-raised px-3 py-2 font-mono text-[11px] text-content-subtle">
                  <span
                    aria-hidden="true"
                    className="size-1.5 rounded-full bg-border-strong"
                  />
                  {language}
                </div>
                <pre className="overflow-x-auto bg-canvas-deep p-4">
                  <code className={cn("font-mono text-xs leading-relaxed text-content")}>
                    {source}
                  </code>
                </pre>
              </div>
            );
          },
        }}
      >
        {markdown}
      </Markdown>
    </div>
  );
}
