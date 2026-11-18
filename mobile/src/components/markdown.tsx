'use dom';
/**
 * Study answers contain Markdown and maths. This is an Expo DOM component: it runs the same
 * react-markdown + KaTeX renderer as the web app inside a native web view.
 */
import 'katex/dist/katex.min.css';
import ReactMarkdown from 'react-markdown';
import rehypeKatex from 'rehype-katex';
import remarkGfm from 'remark-gfm';
import remarkMath from 'remark-math';

export default function Markdown({ text, dark }: { text: string; dark?: boolean; dom?: import('expo/dom').DOMProps }) {
  return <div style={{ fontFamily: '-apple-system, system-ui, sans-serif', fontSize: 17, lineHeight: 1.45, color: dark ? '#eef1f4' : '#1f262b', overflowWrap: 'anywhere', margin: '-1em 0' }}>
    <ReactMarkdown remarkPlugins={[remarkGfm, remarkMath]} rehypePlugins={[rehypeKatex]}
      components={{ a: ({ children }) => <span>{children}</span> }}>{text}</ReactMarkdown>
  </div>;
}
