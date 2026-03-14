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
        "inline-flex items-center justify-center rounded-sm transition-colors hover:text-yellow-500",
        active ? "text-yellow-500" : "text-muted-foreground/40 hover:text-yellow-500/70",
        className
      )}
      aria-label={active ? "Remove from starred" : "Add to starred"}
    >
      <Star
        size={size}
        fill={active ? "currentColor" : "none"}
        strokeWidth={active ? 0 : 1.5}
      />
    </button>
  );
}
