import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { AlertCircle, CheckCircle2, Info, X, XCircle } from "lucide-react";

export type NotifyVariant = "default" | "success" | "error" | "warning";

export interface ToastItem {
  id: string;
  title: string;
  description?: string;
  variant: NotifyVariant;
}

interface ConfirmOptions {
  title: string;
  description?: string;
  confirmLabel?: string;
  cancelLabel?: string;
  destructive?: boolean;
}

interface NotifyContextValue {
  toast: (title: string, options?: { description?: string; variant?: NotifyVariant; duration?: number }) => void;
  confirm: (options: ConfirmOptions) => Promise<boolean>;
}

const NotifyContext = createContext<NotifyContextValue | null>(null);

const VARIANT_ICON = {
  default: Info,
  success: CheckCircle2,
  error: XCircle,
  warning: AlertCircle,
};

const VARIANT_STYLES: Record<NotifyVariant, string> = {
  default: "border-border bg-card text-foreground",
  success: "border-success/50 bg-card text-foreground border-l-[3px] border-l-success",
  error: "border-destructive/60 bg-card text-foreground border-l-[3px] border-l-destructive",
  warning: "border-warning/50 bg-card text-foreground border-l-[3px] border-l-warning",
};

const DESCRIPTION_STYLES: Record<NotifyVariant, string> = {
  default: "text-muted-foreground",
  success: "text-foreground/90",
  error: "text-foreground/90",
  warning: "text-foreground/90",
};

const ICON_STYLES: Record<NotifyVariant, string> = {
  default: "text-primary",
  success: "text-success",
  error: "text-destructive",
  warning: "text-warning",
};

export function NotifyProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<ToastItem[]>([]);
  const [confirmState, setConfirmState] = useState<
    (ConfirmOptions & { open: boolean; resolve?: (v: boolean) => void }) | null
  >(null);

  const dismiss = useCallback((id: string) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
  }, []);

  const toast = useCallback(
    (
      title: string,
      options?: { description?: string; variant?: NotifyVariant; duration?: number }
    ) => {
      const id = crypto.randomUUID();
      const item: ToastItem = {
        id,
        title,
        description: options?.description,
        variant: options?.variant ?? "default",
      };
      setToasts((prev) => [...prev, item]);
      window.setTimeout(() => dismiss(id), options?.duration ?? 6000);
    },
    [dismiss]
  );

  const confirm = useCallback((options: ConfirmOptions) => {
    return new Promise<boolean>((resolve) => {
      setConfirmState({ ...options, open: true, resolve });
    });
  }, []);

  const closeConfirm = useCallback((result: boolean) => {
    setConfirmState((prev) => {
      prev?.resolve?.(result);
      return null;
    });
  }, []);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape" && confirmState?.open) {
        closeConfirm(false);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [confirmState?.open, closeConfirm]);

  return (
    <NotifyContext.Provider value={{ toast, confirm }}>
      {children}

      {/* Toasts — bottom-right, in-app */}
      <div
        className="fixed bottom-4 right-4 z-[100] flex flex-col gap-2 w-[min(100vw-2rem,22rem)] pointer-events-none"
        aria-live="polite"
      >
        {toasts.map((t) => {
          const Icon = VARIANT_ICON[t.variant];
          return (
            <div
              key={t.id}
              role="status"
              className={cn(
                "pointer-events-auto rounded-lg border shadow-xl backdrop-blur-sm px-3 py-2.5 animate-in slide-in-from-bottom-2 fade-in duration-200",
                VARIANT_STYLES[t.variant]
              )}
            >
              <div className="flex items-start gap-2">
                <Icon className={cn("h-4 w-4 shrink-0 mt-0.5", ICON_STYLES[t.variant])} />
                <div className="min-w-0 flex-1">
                  <p className="text-xs font-semibold leading-snug text-foreground">{t.title}</p>
                  {t.description && (
                    <p className={cn("text-[11px] mt-1 leading-relaxed", DESCRIPTION_STYLES[t.variant])}>
                      {t.description}
                    </p>
                  )}
                </div>
                <button
                  type="button"
                  onClick={() => dismiss(t.id)}
                  className="shrink-0 rounded p-0.5 text-foreground/60 hover:text-foreground"
                  aria-label="Dismiss"
                >
                  <X className="h-3.5 w-3.5" />
                </button>
              </div>
            </div>
          );
        })}
      </div>

      {/* Confirm dialog — centered in-app */}
      {confirmState?.open && (
        <div className="fixed inset-0 z-[110] flex items-center justify-center p-4">
          <button
            type="button"
            className="absolute inset-0 bg-background/80 backdrop-blur-sm"
            aria-label="Cancel"
            onClick={() => closeConfirm(false)}
          />
          <div
            role="alertdialog"
            aria-modal="true"
            className="relative z-10 w-full max-w-sm rounded-lg border border-border bg-card p-4 shadow-xl animate-in zoom-in-95 fade-in duration-150"
          >
            <h3 className="text-sm font-semibold">{confirmState.title}</h3>
            {confirmState.description && (
              <p className="text-xs text-muted-foreground mt-1.5 leading-relaxed">{confirmState.description}</p>
            )}
            <div className="flex justify-end gap-2 mt-4">
              <Button
                type="button"
                variant="outline"
                size="sm"
                className="h-8 text-xs"
                onClick={() => closeConfirm(false)}
              >
                {confirmState.cancelLabel ?? "Cancel"}
              </Button>
              <Button
                type="button"
                variant={confirmState.destructive ? "destructive" : "default"}
                size="sm"
                className="h-8 text-xs"
                onClick={() => closeConfirm(true)}
              >
                {confirmState.confirmLabel ?? "Confirm"}
              </Button>
            </div>
          </div>
        </div>
      )}
    </NotifyContext.Provider>
  );
}

export function useNotify() {
  const ctx = useContext(NotifyContext);
  if (!ctx) throw new Error("useNotify must be used within NotifyProvider");
  return ctx;
}

/** Shorthand helpers — stable references so they are safe in effect deps */
export function useNotifyHelpers() {
  const { toast, confirm } = useNotify();
  return useMemo(
    () => ({
      toast,
      confirm,
      success: (title: string, description?: string) =>
        toast(title, { description, variant: "success" }),
      error: (title: string, description?: string) =>
        toast(title, { description, variant: "error", duration: 8000 }),
      warning: (title: string, description?: string) =>
        toast(title, { description, variant: "warning" }),
    }),
    [toast, confirm]
  );
}
