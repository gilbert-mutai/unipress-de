import { cva, type VariantProps } from "class-variance-authority";
import { forwardRef } from "react";
import { cn } from "../../lib/utils";

const button = cva(
  "inline-flex items-center justify-center gap-2 rounded-lg font-medium transition-all focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand/50 disabled:opacity-50 disabled:pointer-events-none",
  {
    variants: {
      variant: {
        primary: "bg-ink text-paper hover:bg-ink/90 shadow-sm",
        brand: "bg-brand text-brand-fg hover:bg-brand/90 shadow-sm",
        // Gold CTA, echoing the "APPLY ONLINE" button on unideb.hu. Dark green
        // text on gold rather than white, which would fail contrast.
        accent: "bg-accent text-accent-fg hover:bg-accent/90 shadow-sm",
        outline: "border border-line bg-card hover:bg-line/40 text-ink",
        ghost: "hover:bg-line/50 text-ink",
        // For controls sitting on the deep-green header band.
        onHeader: "text-header-fg hover:bg-white/15 focus-visible:ring-header-fg/60",
      },
      size: {
        sm: "h-8 px-3 text-sm",
        md: "h-10 px-4 text-sm",
        lg: "h-12 px-6 text-base",
        icon: "h-9 w-9",
      },
    },
    defaultVariants: { variant: "primary", size: "md" },
  },
);

export interface ButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof button> {}

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant, size, ...props }, ref) => (
    <button ref={ref} className={cn(button({ variant, size }), className)} {...props} />
  ),
);
Button.displayName = "Button";
