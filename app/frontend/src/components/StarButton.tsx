import { Star } from "lucide-react";
import { cn } from "@/lib/utils";

interface StarButtonProps {
  active: boolean;
  onClick: () => void;
  /**
   * What the star is for (a ticker or a fund), part of the button's name: in a list every row
   * has a star, and "Add to starred" alone would not tell a screen reader which one.
   */
  subject?: string;
  className?: string;
  size?: number;
}

export function StarButton({ active, onClick, subject, className, size = 16 }: StarButtonProps) {
  const label = subject
    ? active
      ? `Remove ${subject} from starred`
      : `Add ${subject} to starred`
    : active
      ? "Remove from starred"
      : "Add to starred";
  return (
    <button
      type="button"
      onClick={(e) => {
        e.stopPropagation();
        e.preventDefault();
        onClick();
      }}
      className={cn(
        "inline-flex h-8 w-8 shrink-0 items-center justify-center rounded-sm transition-colors hover:bg-muted hover:text-gold-text",
        active ? "text-gold-text" : "icon-faint",
        className,
      )}
      aria-pressed={active}
      aria-label={label}
    >
      <Star size={size} fill={active ? "currentColor" : "none"} strokeWidth={active ? 0 : 1.5} />
    </button>
  );
}
