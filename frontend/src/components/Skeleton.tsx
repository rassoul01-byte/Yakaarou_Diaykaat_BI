/** Squelettes de chargement — remplacent les « … » par une animation douce. */

export function SkeletonLigne({ largeur = "moyen" }: { largeur?: "court" | "moyen" | "plein" }) {
  const classe = largeur === "plein" ? "" : ` ${largeur}`;
  return <div className={`skeleton skeleton-ligne${classe}`} />;
}

export function SkeletonBloc() {
  return <div className="skeleton skeleton-bloc" />;
}

export function SkeletonAssistant() {
  return (
    <div className="answer-card" style={{ marginTop: "1.5rem" }}>
      <SkeletonLigne largeur="court" />
      <div style={{ marginTop: "0.75rem" }}>
        <SkeletonLigne largeur="plein" />
        <SkeletonLigne largeur="plein" />
        <SkeletonLigne largeur="moyen" />
      </div>
    </div>
  );
}

export function SkeletonProduit() {
  return <div className="skeleton skeleton-carte" />;
}

export function SkeletonListeProduits({ nombre = 4 }: { nombre?: number }) {
  return (
    <div style={{ marginTop: "1rem" }}>
      {Array.from({ length: nombre }).map((_, i) => (
        <SkeletonProduit key={i} />
      ))}
    </div>
  );
}
