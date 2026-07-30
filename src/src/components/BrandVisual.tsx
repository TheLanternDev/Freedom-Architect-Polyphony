/** Obrazy marki z /public/brand/ (tools/ue5-brand/output). */
type BrandVariant = "login-hero" | "login-bg" | "brief" | "rail";

const SRC: Record<BrandVariant, string> = {
  "login-hero": "/brand/04_hero_title.png",
  "login-bg": "/brand/03_spotlight.png",
  brief: "/brand/01_council_nine.png",
  rail: "/brand/01_council_nine.png",
};

interface Props {
  variant: BrandVariant;
  className?: string;
  alt?: string;
}

/** Warianty widoczne od pierwszego paintu (ekran logowania = LCP). */
const EAGER: ReadonlySet<BrandVariant> = new Set(["login-hero", "login-bg"]);

export function BrandVisual({ variant, className = "", alt = "" }: Props) {
  return (
    <img
      src={SRC[variant]}
      alt={alt}
      className={className}
      loading={EAGER.has(variant) ? "eager" : "lazy"}
      fetchPriority={variant === "login-hero" ? "high" : undefined}
      decoding="async"
      draggable={false}
    />
  );
}
