import { useState, type ReactNode } from "react";
import ReactMarkdown from "react-markdown";
import rehypeHighlight from "rehype-highlight";
import remarkMath from "remark-math";
import rehypeKatex from "rehype-katex";
import "katex/dist/katex.min.css";
import styles from "./Markdown.module.css";

function CopyButton({ getText }: { getText: () => string }) {
  const [copied, setCopied] = useState(false);
  return (
    <button
      type="button"
      className={styles.copy}
      aria-label="Copy code"
      onClick={async () => {
        try {
          await navigator.clipboard.writeText(getText());
          setCopied(true);
          setTimeout(() => setCopied(false), 1500);
        } catch {
          /* clipboard unavailable */
        }
      }}
    >
      {copied ? "Copied" : "Copy"}
    </button>
  );
}

function extractText(node: ReactNode): string {
  if (typeof node === "string") return node;
  if (Array.isArray(node)) return node.map(extractText).join("");
  if (node && typeof node === "object" && "props" in node) {
    return extractText((node as { props: { children?: ReactNode } }).props.children);
  }
  return "";
}

export function Markdown({ children }: { children: string }) {
  return (
    <div className={`md ${styles.md}`}>
      <ReactMarkdown
        remarkPlugins={[remarkMath]}
        rehypePlugins={[[rehypeHighlight, { detect: true, ignoreMissing: true }], [rehypeKatex, { strict: false, trust: false }]]}
        components={{
          // Model/document text must not trigger automatic requests to arbitrary
          // image hosts (which could encode private content in a URL).
          img: ({ alt }) => <span>[Image omitted{alt ? `: ${alt}` : ''}]</span>,
          pre: ({ children }) => {
            const text = extractText(children);
            return (
              <div className={styles.preWrap}>
                <CopyButton getText={() => text} />
                <pre>{children}</pre>
              </div>
            );
          },
        }}
      >
        {children}
      </ReactMarkdown>
    </div>
  );
}
