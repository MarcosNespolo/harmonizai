import type { Wine, WineListState } from "../lib/wines";

const SLOT_COUNT = 3;

interface WineListProps {
  state: WineListState;
  wines?: Wine[];
}

export function WineList({ state, wines = [] }: WineListProps) {
  const slots = Array.from({ length: SLOT_COUNT });
  const showEmpty = state === "empty";
  const showLoading = state === "loading";
  const showPopulated = state === "populated";

  return (
    <div className="flex w-full flex-col gap-4">
      <div className="relative flex min-h-[32px] items-center">
        <StateCaption
          visible={showEmpty}
          icon={<WineGlassIcon className="h-4 w-4 text-primary/50" />}
          text="Digite sua refeição ao lado para descobrirmos o vinho perfeito."
        />
        <StateCaption
          visible={showLoading}
          icon={<Spinner className="h-3.5 w-3.5 text-primary" />}
          text="Buscando as melhores harmonizações…"
        />
        <StateCaption
          visible={showPopulated}
          icon={
            <span className="inline-flex h-4 w-4 items-center justify-center rounded-full bg-secondary/15 text-secondary">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3" className="h-2.5 w-2.5">
                <path d="M5 13l4 4L19 7" strokeLinecap="round" strokeLinejoin="round" />
              </svg>
            </span>
          }
          text={`${wines.length} harmoniza${wines.length === 1 ? "ção" : "ções"} para seu prato.`}
        />
      </div>

      <div className="flex flex-col gap-3">
        {slots.map((_, i) => (
          <WineCard key={i} state={state} wine={wines[i]} />
        ))}
      </div>
    </div>
  );
}

function StateCaption({
  visible,
  icon,
  text,
}: {
  visible: boolean;
  icon: React.ReactNode;
  text: string;
}) {
  return (
    <div
      aria-hidden={!visible}
      className={`absolute flex items-center gap-2 text-[12px] text-ink-muted transition-opacity duration-300 ${
        visible ? "opacity-100" : "pointer-events-none opacity-0"
      }`}
    >
      {icon}
      <span>{text}</span>
    </div>
  );
}

function WineCard({ state, wine }: { state: WineListState; wine?: Wine }) {
  const showReal = state === "populated" && wine !== undefined;
  const shimmer = state === "loading";
  const skeletonClass = shimmer ? "skeleton skeleton-shimmer" : "skeleton";

  return (
    <article className="relative flex gap-4 rounded-xl border border-border bg-card p-4 shadow-[0_1px_2px_rgba(20,20,20,0.03)]">
      <div className="relative h-[112px] w-[72px] shrink-0">
        <div
          className={`${skeletonClass} flex h-full w-full items-center justify-center transition-opacity duration-300 ${
            showReal ? "opacity-0" : "opacity-100"
          }`}
        >
          <BottleSilhouette className="h-[84%] w-auto text-[#c8c8c8]" />
        </div>
        {wine && (
          <div
            className={`absolute inset-0 transition-opacity duration-300 ${
              showReal ? "opacity-100" : "opacity-0"
            }`}
          >
            <BottleVisual color={wine.color} />
          </div>
        )}
      </div>

      <div className="relative min-w-0 flex-1">
        <div
          aria-hidden={showReal}
          className={`flex flex-col gap-2 transition-opacity duration-300 ${
            showReal ? "opacity-0" : "opacity-100"
          }`}
        >
          <div className={`${skeletonClass} h-[18px] w-[70%]`} />
          <div className={`${skeletonClass} h-3 w-[45%]`} />
          <div className={`${skeletonClass} h-[10px] w-[55%]`} />
          <div className="mt-1 flex flex-col gap-1.5">
            <div className={`${skeletonClass} h-3 w-[96%]`} />
            <div className={`${skeletonClass} h-3 w-[78%]`} />
          </div>
          <div className={`${skeletonClass} mt-1.5 h-[22px] w-28 rounded-full`} />
        </div>

        {wine && (
          <div
            className={`absolute inset-0 flex min-w-0 flex-col transition-opacity duration-300 ${
              showReal ? "opacity-100" : "opacity-0"
            }`}
          >
            <h3 className="truncate text-[15px] font-semibold leading-tight tracking-tight text-ink">
              {wine.name}
            </h3>
            <p className="mt-1 text-[12px] text-ink-muted">
              {wine.winery} · {wine.vintage}
            </p>
            <p className="text-[10px] uppercase tracking-[0.08em] text-ink-subtle">
              {wine.region}
            </p>
            <p className="mt-1.5 line-clamp-2 text-[12px] leading-snug text-ink-muted">
              {wine.notes}
            </p>
            <div className="mt-auto inline-flex w-fit items-center gap-1.5 rounded-full bg-primary/10 px-2 py-0.5 text-[11px] font-medium text-primary">
              <span className="h-1.5 w-1.5 rounded-full bg-primary" />
              {wine.matchScore}% · {wine.matchLabel}
            </div>
          </div>
        )}
      </div>
    </article>
  );
}

function BottleVisual({ color }: { color: string }) {
  return (
    <div
      className="flex h-full w-full items-center justify-center rounded-md"
      style={{
        background: `linear-gradient(180deg, ${color}10 0%, ${color}30 100%)`,
      }}
    >
      <svg viewBox="0 0 40 100" className="h-[88%] w-auto" aria-hidden>
        <path
          d="M17 4 h6 v14 q0 3 2 6 q5 7 5 18 v52 q0 4 -4 4 h-12 q-4 0 -4 -4 v-52 q0 -11 5 -18 q2 -3 2 -6 z"
          fill={color}
        />
        <rect
          x="11"
          y="44"
          width="18"
          height="16"
          fill="rgba(255,255,255,0.92)"
          rx="1"
        />
      </svg>
    </div>
  );
}

function BottleSilhouette({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 40 100" className={className} fill="currentColor" aria-hidden>
      <path d="M17 4 h6 v14 q0 3 2 6 q5 7 5 18 v52 q0 4 -4 4 h-12 q-4 0 -4 -4 v-52 q0 -11 5 -18 q2 -3 2 -6 z" />
    </svg>
  );
}

function WineGlassIcon({ className }: { className?: string }) {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.5"
      strokeLinecap="round"
      strokeLinejoin="round"
      className={className}
      aria-hidden
    >
      <path d="M7 3h10l-1 9c-.3 2.5-2.4 4.5-4 4.5s-3.7-2-4-4.5L7 3z" />
      <line x1="12" y1="16.5" x2="12" y2="21" />
      <line x1="8" y1="21" x2="16" y2="21" />
    </svg>
  );
}

function Spinner({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 24 24" className={className} aria-hidden>
      <circle
        cx="12"
        cy="12"
        r="9"
        fill="none"
        stroke="currentColor"
        strokeOpacity="0.2"
        strokeWidth="2.5"
      />
      <path
        d="M21 12a9 9 0 0 1-9 9"
        fill="none"
        stroke="currentColor"
        strokeWidth="2.5"
        strokeLinecap="round"
      >
        <animateTransform
          attributeName="transform"
          type="rotate"
          from="0 12 12"
          to="360 12 12"
          dur="0.9s"
          repeatCount="indefinite"
        />
      </path>
    </svg>
  );
}
