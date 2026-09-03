import { Star } from "lucide-react";
import { cn } from "@/lib/utils";

interface StarButtonProps {
  active: boolean;
  onClick: () => void;
  className?: string;
  size?: number;
}

export function StarButton({ active, onClick, className, size = 16 }: StarButtonProps) {
  return (
    <button
      type="button"
      onClick={(e) => {
        e.stopPropagation();
        e.preventDefault();
        onClick();
      }}
      className={cn(
        "inline-flex h-8 w-8 shrink-0 items-center justify-center rounded-sm transition-colors hover:bg-muted hover:text-warning",
        active ? "text-warning" : "icon-faint",
        className,
      )}
      aria-pressed={active}
      aria-label={active ? "Remove from starred" : "Add to starred"}
    >
      <Star size={size} fill={active ? "currentColor" : "none"} strokeWidth={active ? 0 : 1.5} />
    </button>
  );
}
