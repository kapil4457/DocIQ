"use client";

import * as React from "react";
import { cn } from "@/lib/utils";

const Badge = ({ className, ...props }: React.ComponentProps<"span">) => (
  <span
    className={cn(
      "inline-flex items-center rounded-full border px-2.5 py-0.5 text-[11px] font-medium tracking-wide",
      "border-zinc-200 bg-zinc-100 text-zinc-700 dark:border-zinc-700 dark:bg-zinc-800 dark:text-zinc-300",
      className
    )}
    {...props}
  />
);

export { Badge };
