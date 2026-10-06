import { Card, CardContent, CardHeader } from "@/components/ui/card";

export function AuthCard({ children }: { children: React.ReactNode }) {
  return (
    <Card className="mx-auto w-full max-w-sm border bg-card shadow-xl">
      <CardHeader className="flex flex-col items-center gap-1 px-6 pt-8 pb-2 sm:px-8">
        <h1 className="text-2xl font-bold tracking-tight text-brand-text">
          Curigor
        </h1>
        <p className="text-sm text-muted-foreground">ログイン・新規登録</p>
      </CardHeader>
      <CardContent className="flex flex-col gap-5 px-6 pt-6 pb-8 sm:px-8">
        {children}
      </CardContent>
    </Card>
  );
}
