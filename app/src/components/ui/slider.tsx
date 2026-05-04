import * as React from "react";
import { cn } from "@/lib/utils";

export interface SliderProps extends React.InputHTMLAttributes<HTMLInputElement> {
  label?: string;
  valueLabel?: string;
  hint?: string;
}

const Slider = React.forwardRef<HTMLInputElement, SliderProps>(
  ({ className, label, valueLabel, hint, ...props }, ref) => {
    return (
      <div className="flex flex-col gap-1.5">
        {(label || valueLabel) && (
          <div className="flex items-center justify-between">
            {label && <span className="text-sm font-medium">{label}</span>}
            {valueLabel && <span className="text-sm font-semibold tabular-nums">{valueLabel}</span>}
          </div>
        )}
        <input
          type="range"
          ref={ref}
          className={cn(
            "w-full h-2 rounded-full appearance-none cursor-pointer bg-secondary",
            "[&::-webkit-slider-thumb]:appearance-none [&::-webkit-slider-thumb]:h-4 [&::-webkit-slider-thumb]:w-4 [&::-webkit-slider-thumb]:rounded-full [&::-webkit-slider-thumb]:bg-primary [&::-webkit-slider-thumb]:shadow",
            "[&::-moz-range-thumb]:h-4 [&::-moz-range-thumb]:w-4 [&::-moz-range-thumb]:rounded-full [&::-moz-range-thumb]:bg-primary [&::-moz-range-thumb]:border-0",
            "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2",
            "disabled:cursor-not-allowed disabled:opacity-50",
            className
          )}
          {...props}
        />
        {hint && <p className="text-xs text-muted-foreground">{hint}</p>}
      </div>
    );
  }
);
Slider.displayName = "Slider";

export { Slider };
