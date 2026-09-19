import { forwardRef } from "react";
import { cn } from "@/lib/utils";

export interface FieldProps extends React.InputHTMLAttributes<HTMLInputElement> {
  label: string;
  error?: string;
}

export const Field = forwardRef<HTMLInputElement, FieldProps>(
  ({ label, error, className, id, ...props }, ref) => {
    const fieldId = id || props.name;
    return (
      <div className="flex flex-col gap-2">
        <label htmlFor={fieldId} className="text-sm font-medium text-neutral-800">
          {label}
        </label>
        <input
          id={fieldId}
          ref={ref}
          className={cn(
            "w-full rounded-full border border-neutral-200 bg-white px-5 py-3 text-sm text-neutral-900 placeholder:text-neutral-300 focus:border-neutral-900 focus:outline-none focus:ring-1 focus:ring-neutral-900",
            error && "border-rose-300 focus:border-rose-500 focus:ring-rose-500",
            className
          )}
          {...props}
        />
        {error && <span className="text-xs text-rose-600 pl-2">{error}</span>}
      </div>
    );
  }
);
Field.displayName = "Field";

export const SubmitButton = ({
  children,
  loading,
  className,
  onClick,
  type = "submit",
}: {
  children: React.ReactNode;
  loading?: boolean;
  className?: string;
  onClick?: (e: React.MouseEvent<HTMLButtonElement>) => void;
  type?: "submit" | "button";
}) => (
  <button
    type={type}
    disabled={loading}
    onClick={onClick}
    className={cn(
      "w-full rounded-full bg-neutral-900 bg-gradient-to-b from-[#3a3a3a] to-[#121212] px-6 py-3.5 text-sm font-medium text-white shadow-sm transition-all hover:opacity-90 active:scale-[0.98] disabled:opacity-60 disabled:active:scale-100",
      className
    )}
  >
    {loading ? "Please wait…" : children}
  </button>
);
