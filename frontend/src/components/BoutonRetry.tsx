import { AlertTriangle, RefreshCw } from "lucide-react";

type Props = {
  message: string;
  onRetry: () => void;
};

export default function BoutonRetry({ message, onRetry }: Props) {
  return (
    <div className="warning-box" style={{ marginTop: "1rem", alignItems: "flex-start" }}>
      <AlertTriangle size={18} style={{ flexShrink: 0, marginTop: 2 }} />
      <div style={{ flex: 1 }}>
        <strong>Une erreur est survenue</strong>
        <span>{message}</span>
        <button
          onClick={onRetry}
          style={{
            marginTop: "0.75rem",
            border: "1px solid var(--c-primaire)",
            background: "var(--c-carte)",
            color: "var(--c-primaire)",
            padding: "6px 12px",
            borderRadius: "var(--radius-sm)",
            fontSize: 11,
            fontWeight: 600,
            display: "inline-flex",
            alignItems: "center",
            gap: 6,
          }}
        >
          <RefreshCw size={12} />
          Réessayer
        </button>
      </div>
    </div>
  );
}
