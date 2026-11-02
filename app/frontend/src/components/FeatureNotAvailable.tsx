import LocalOnlyNotice from "@/components/ai/LocalOnlyNotice";
import { PageHeader } from "@/components/ui/PageHeader";

export default function FeatureNotAvailable({ feature }: { feature: string }) {
  return (
    <div className="flex items-center justify-center min-h-[60vh]">
      <div className="w-full max-w-xl space-y-6">
        <PageHeader title={feature} className="text-magenta" />
        <LocalOnlyNotice description="This feature requires a local AI backend and is not available in the web version." />
      </div>
    </div>
  );
}
