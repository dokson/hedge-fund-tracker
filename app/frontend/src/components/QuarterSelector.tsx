import { AVAILABLE_QUARTERS } from "@/lib/dataService";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";

interface QuarterSelectorProps {
  value: string;
  onChange: (value: string) => void;
  className?: string;
  disabled?: boolean;
}

export function QuarterSelector({ value, onChange, className = "", disabled = false }: QuarterSelectorProps) {
  return (
    <Select value={value} onValueChange={onChange} disabled={disabled}>
      <SelectTrigger className={`w-36 bg-card border-border ${className}`}>
        <SelectValue />
      </SelectTrigger>
      <SelectContent>
        {[...AVAILABLE_QUARTERS].reverse().map((q) => (
          <SelectItem key={q} value={q}>{q.replace("Q", " Q")}</SelectItem>
        ))}
      </SelectContent>
    </Select>
  );
}
