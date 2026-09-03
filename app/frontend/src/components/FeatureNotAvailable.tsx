import LocalOnlyNotice from "@/components/ai/LocalOnlyNotice";

export default function FeatureNotAvailable({ feature }: { feature: string }) {
  return (
    <div className="flex items-center justify-center min-h-[60vh]">
      <div className="w-full max-w-xl space-y-6">
        <h1 className="page-title text-magenta">{feature}</h1>
        <LocalOnlyNotice description="This feature requires a local AI backend and is not available in the web version." />
      </div>
    </div>
  );
}
