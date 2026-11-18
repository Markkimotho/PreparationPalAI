import styles from "./ErrorState.module.css";

interface Props {
  message: string;
  onRetry?: () => void;
}

/** Show a safe https link when the message carries one (for example a top-up page). */
function withLinks(message: string) {
  return message.split(/(https?:\/\/\S+)/g).map((part, i) =>
    /^https?:\/\//.test(part)
      ? <a key={i} href={part} target="_blank" rel="noopener noreferrer">{part}</a>
      : part);
}

export function ErrorState({ message, onRetry }: Props) {
  return (
    <div className={styles.wrap} role="alert">
      <span className={styles.msg}>{withLinks(message)}</span>
      {onRetry && (
        <button className={styles.retry} onClick={onRetry} type="button">
          Retry
        </button>
      )}
    </div>
  );
}
