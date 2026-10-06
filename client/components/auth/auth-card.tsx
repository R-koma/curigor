import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { AppLogo } from "@/components/brand/app-logo";

export function AuthCard({
  subtitle,
  children,
}: {
  subtitle: string;
  children: React.ReactNode;
}) {
  return (
    <Card className="mx-auto w-full max-w-sm border bg-card shadow-xl">
      <CardHeader className="flex flex-col items-center gap-1 px-6 pt-8 pb-2 sm:px-8">
        <h1 className="flex items-center gap-2 text-2xl font-bold tracking-tight text-brand-text">
          <AppLogo className="h-8" />
          Curigor
        </h1>
        <p className="text-sm text-muted-foreground">{subtitle}</p>
      </CardHeader>
      <CardContent className="flex flex-col gap-5 px-6 pt-6 pb-8 sm:px-8">
        {children}
      </CardContent>
    </Card>
  );
}
