import * as React from "react"
import { cn } from "@/lib/utils"

interface BadgeProps extends React.HTMLAttributes<HTMLSpanElement> {
  variant?: "default" | "purple" | "gray" | "green" | "red"
}

const Badge = ({ className, variant = "default", ...props }: BadgeProps) => (
  <span
    className={cn(
      "inline-flex items-center rounded-md px-2 py-0.5 text-xs font-medium",
      variant === "default" && "bg-gray-100 text-gray-700",
      variant === "purple" && "bg-purple-100 text-purple-700",
      variant === "gray" && "bg-gray-100 text-gray-500",
      variant === "green" && "bg-green-50 text-green-700",
      variant === "red" && "bg-red-50 text-red-600",
      className
    )}
    {...props}
  />
)

export { Badge }
