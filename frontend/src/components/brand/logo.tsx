import Image from "next/image";
import Link from "next/link";
import { cn } from "@/lib/utils";

interface LogoProps {
  className?: string;
  height?: number;
  href?: string;
}

export function Logo({ className, height = 36, href }: LogoProps) {
  const img = (
    <Image
      src="/taswera-logo.jpg"
      alt="TASWERA"
      width={Math.round(height * 3.2)}
      height={height}
      className={cn("h-auto w-auto object-contain", className)}
      priority
    />
  );

  if (href) {
    return (
      <Link href={href} className="inline-flex items-center">
        {img}
      </Link>
    );
  }

  return img;
}
