import React from "react";
import Image from "next/image";
import { cn } from "@/lib/utils";

interface EurekaLogoProps {
  className?: string;
  size?: "sm" | "md" | "lg" | "xl";
  height?: number;
  priority?: boolean;
}

export function EurekaLogo({
  className = "",
  size = "md",
  height,
  priority = true,
}: EurekaLogoProps) {
  // Configuración de altura por tamaño
  const heightMap = {
    sm: 20,
    md: 26,
    lg: 36,
    xl: 48,
  };

  const h = height || heightMap[size];

  return (
    <div className={cn("inline-flex items-center select-none", className)}>
      <Image
        src="/brand/eureka-logo.png"
        alt="eureka logo"
        width={1512}
        height={338}
        priority={priority}
        className="object-contain"
        style={{ height: `${h}px`, width: "auto" }}
      />
    </div>
  );
}
