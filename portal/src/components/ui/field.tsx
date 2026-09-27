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
        <label htmlFor={fieldId} className="text-sm font-medium cv-body">
          {label}
        </label>
        <input
          id={fieldId}
          ref={ref}
          aria-invalid={error ? true : undefined}
          className={cn("cv-input", error && "cv-input-error", className)}
          {...props}
        />
        {error && <span className="pl-2 text-xs text-rose-600">{error}</span>}
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
    className={cn("cv-btn w-full px-6 py-3.5", className)}
  >
    {loading ? "Please wait…" : children}
  </button>
);
