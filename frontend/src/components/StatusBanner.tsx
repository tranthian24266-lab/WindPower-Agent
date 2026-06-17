interface StatusBannerProps {
  variant?: "info" | "error" | "success";
  message: string;
}

export function StatusBanner({ variant = "info", message }: StatusBannerProps) {
  return <div className={`status-banner ${variant}`}>{message}</div>;
}
