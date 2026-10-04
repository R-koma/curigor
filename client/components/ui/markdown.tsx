import type { ComponentProps } from "react";
import ReactMarkdown, { type Components } from "react-markdown";
import remarkGfm from "remark-gfm";
import remarkBreaks from "remark-breaks";
import rehypeHighlight from "rehype-highlight";
import rehypeSlug from "rehype-slug";
import rehypeAutolinkHeadings from "rehype-autolink-headings";
import { cn } from "@/lib/utils";

const articleRehypePlugins = [
  rehypeSlug,
  [
    rehypeAutolinkHeadings,
    {
      behavior: "append",
      properties: {
        className: ["heading-anchor"],
        ariaLabel: "セクションへのリンク",
      },
      content: { type: "text", value: "#" },
    },
  ],
  rehypeHighlight,
] as const;

const components: Components = {
  h1: ({ className, ...props }) => (
    <h1
      className={cn("mt-6 mb-3 text-xl font-bold first:mt-0", className)}
      {...props}
    />
  ),
  h2: ({ className, ...props }) => (
    <h2
      className={cn("mt-6 mb-3 text-lg font-semibold first:mt-0", className)}
      {...props}
    />
  ),
  h3: ({ className, ...props }) => (
    <h3
      className={cn("mt-5 mb-2 text-base font-semibold first:mt-0", className)}
      {...props}
    />
  ),
  h4: ({ className, ...props }) => (
    <h4
      className={cn("mt-4 mb-2 text-sm font-semibold first:mt-0", className)}
      {...props}
    />
  ),
  p: ({ className, ...props }) => (
    <p className={cn("my-2 leading-7", className)} {...props} />
  ),
  ul: ({ className, ...props }) => (
    <ul className={cn("my-2 list-disc space-y-1 pl-6", className)} {...props} />
  ),
  ol: ({ className, ...props }) => (
    <ol
      className={cn("my-2 list-decimal space-y-1 pl-6", className)}
      {...props}
    />
  ),
  li: ({ className, ...props }) => (
    <li className={cn("leading-7", className)} {...props} />
  ),
  strong: ({ className, ...props }) => (
    <strong className={cn("font-semibold", className)} {...props} />
  ),
  em: ({ className, ...props }) => (
    <em className={cn("italic", className)} {...props} />
  ),
  code: ({ className, ...props }) => (
    <code
      className={cn(
        "rounded bg-muted px-1.5 py-0.5 font-mono text-[0.9em]",
        className,
      )}
      {...props}
    />
  ),
  pre: ({ className, ...props }) => (
    <pre
      className={cn(
        "my-3 overflow-x-auto rounded-lg bg-muted p-3 text-sm",
        className,
      )}
      {...props}
    />
  ),
  blockquote: ({ className, ...props }) => (
    <blockquote
      className={cn(
        "my-3 border-l-2 border-border pl-4 text-muted-foreground italic",
        className,
      )}
      {...props}
    />
  ),
  a: ({ className, ...props }) => (
    <a
      className={cn(
        "text-primary underline underline-offset-2 hover:opacity-80",
        className,
      )}
      target="_blank"
      rel="noopener noreferrer"
      {...props}
    />
  ),
  hr: ({ className, ...props }) => (
    <hr className={cn("my-4 border-border", className)} {...props} />
  ),
  table: ({ className, ...props }) => (
    <div className="my-3 overflow-x-auto">
      <table
        className={cn("w-full border-collapse text-sm", className)}
        {...props}
      />
    </div>
  ),
  th: ({ className, ...props }) => (
    <th
      className={cn(
        "border border-border bg-muted px-3 py-2 text-left font-semibold",
        className,
      )}
      {...props}
    />
  ),
  td: ({ className, ...props }) => (
    <td
      className={cn("border border-border px-3 py-2", className)}
      {...props}
    />
  ),
};

interface MarkdownProps {
  children: string;
  className?: string;
  variant?: "default" | "article" | "chat";
}

const articleProseClasses = cn(
  "prose prose-neutral dark:prose-invert max-w-[68ch] text-prose",
  "prose-headings:font-semibold prose-headings:tracking-tight prose-headings:scroll-mt-24",
  "prose-h1:text-3xl prose-h2:text-2xl prose-h3:text-xl prose-h4:text-lg",
  "prose-h2:mt-12 prose-h2:mb-4 prose-h3:mt-10 prose-h3:mb-3",
  "prose-p:leading-[1.85] prose-p:my-5",
  "[&>p:first-child]:text-lg [&>p:first-child]:text-foreground/80",
  "prose-ul:my-5 prose-ol:my-5 prose-ul:pl-5 prose-ol:pl-5",
  "prose-li:leading-[1.85] prose-li:my-1",
  "prose-ul:marker:text-primary/60 prose-ol:marker:text-primary/60",
  "[&_li>input]:mr-2 [&_li>input]:translate-y-[1px]",
  "prose-strong:text-foreground prose-strong:font-semibold",
  "prose-code:rounded prose-code:bg-muted prose-code:px-1.5 prose-code:py-0.5",
  "prose-code:font-mono prose-code:text-[0.9em] prose-code:text-primary",
  "prose-code:before:content-none prose-code:after:content-none",
  "prose-pre:rounded-lg prose-pre:bg-muted prose-pre:border prose-pre:border-border",
  "prose-pre:p-4 prose-pre:text-[0.9em] prose-pre:leading-relaxed",
  "[&_pre_code]:bg-transparent [&_pre_code]:p-0 [&_pre_code]:text-foreground",
  "[&_pre_code]:before:content-none [&_pre_code]:after:content-none",
  // blockquote (callout style)
  "prose-blockquote:rounded-r prose-blockquote:bg-muted/40",
  "prose-blockquote:border-l-4 prose-blockquote:border-primary/60",
  "prose-blockquote:px-5 prose-blockquote:py-3",
  "prose-blockquote:text-foreground/80 prose-blockquote:not-italic",
  "[&_blockquote_p]:before:content-none [&_blockquote_p]:after:content-none",
  "prose-a:text-primary prose-a:no-underline hover:prose-a:underline",
  '[&_a[href^="http"]]:after:content-["_↗"] [&_a[href^="http"]]:after:text-xs',
  "prose-table:border-collapse",
  "prose-thead:border-b prose-thead:border-border",
  "prose-th:py-2.5 prose-td:py-2.5 prose-th:px-3 prose-td:px-3",
  "prose-th:text-left prose-th:font-semibold",
  "[&_tbody_tr]:border-b [&_tbody_tr]:border-border/60",
  "[&_tbody_tr:nth-child(even)]:bg-muted/30",
  "prose-hr:my-12 prose-hr:border-border/60",
  // heading anchor (rehype-autolink-headings)
  "[&_.heading-anchor]:ml-2 [&_.heading-anchor]:text-muted-foreground/40",
  "[&_.heading-anchor]:no-underline hover:[&_.heading-anchor]:text-primary",
  "[&_h2:not(:hover)>.heading-anchor]:opacity-0 [&_h3:not(:hover)>.heading-anchor]:opacity-0",
  "[&_.heading-anchor]:transition-opacity",
);

export function Markdown({
  children,
  className,
  variant = "default",
}: MarkdownProps) {
  if (variant === "article") {
    return (
      <div className={cn(articleProseClasses, className)}>
        <ReactMarkdown
          remarkPlugins={[remarkGfm]}
          rehypePlugins={
            articleRehypePlugins as unknown as ComponentProps<
              typeof ReactMarkdown
            >["rehypePlugins"]
          }
        >
          {children}
        </ReactMarkdown>
      </div>
    );
  }

  if (variant === "chat") {
    return (
      <div className={cn("text-base text-foreground/90", className)}>
        <ReactMarkdown
          remarkPlugins={[remarkGfm, remarkBreaks]}
          rehypePlugins={[rehypeHighlight]}
          components={components}
        >
          {children}
        </ReactMarkdown>
      </div>
    );
  }

  return (
    <div className={cn("text-base text-foreground/90", className)}>
      <ReactMarkdown remarkPlugins={[remarkGfm]} components={components}>
        {children}
      </ReactMarkdown>
    </div>
  );
}
