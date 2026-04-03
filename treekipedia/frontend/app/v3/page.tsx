'use client';

import Link from 'next/link';
import { useEffect, useRef, useState, type RefObject } from 'react';
import {
  ArrowRight,
  Binary,
  BrainCircuit,
  Database,
  GitBranch,
  MapPinned,
  Radar,
  ScanSearch,
  ShieldAlert,
  Sparkles,
  Trees,
} from 'lucide-react';

function seededRandom(seed: number) {
  let s = seed;
  return () => {
    s = (s * 16807) % 2147483647;
    return (s - 1) / 2147483646;
  };
}

function useInView(ref: RefObject<HTMLElement | null>, opts?: { threshold?: number }) {
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const obs = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) setVisible(true);
      },
      { threshold: opts?.threshold ?? 0.15 }
    );
    obs.observe(el);
    return () => obs.disconnect();
  }, [ref, opts?.threshold]);

  return visible;
}

function Counter({
  end,
  suffix = '',
  prefix = '',
  duration = 1800,
}: {
  end: number;
  suffix?: string;
  prefix?: string;
  duration?: number;
}) {
  const ref = useRef<HTMLSpanElement>(null);
  const visible = useInView(ref);
  const [value, setValue] = useState(0);

  useEffect(() => {
    if (!visible) return;
    const start = performance.now();

    const tick = (now: number) => {
      const progress = Math.min((now - start) / duration, 1);
      const eased = 1 - Math.pow(1 - progress, 3);
      setValue(Math.floor(eased * end));
      if (progress < 1) requestAnimationFrame(tick);
    };

    requestAnimationFrame(tick);
  }, [visible, end, duration]);

  return (
    <span ref={ref}>
      {prefix}
      {value.toLocaleString()}
      {suffix}
    </span>
  );
}

function Reveal({
  children,
  className = '',
  delay = 0,
  direction = 'up',
}: {
  children: React.ReactNode;
  className?: string;
  delay?: number;
  direction?: 'up' | 'left' | 'right';
}) {
  const ref = useRef<HTMLDivElement>(null);
  const visible = useInView(ref);
  const hiddenClass =
    direction === 'up'
      ? 'reveal-hidden'
      : direction === 'left'
        ? 'reveal-hidden-left'
        : 'reveal-hidden-right';
  const shownClass = direction === 'up' ? 'reveal-visible' : 'reveal-visible-x';

  return (
    <div
      ref={ref}
      className={`${hiddenClass} ${visible ? shownClass : ''} ${className}`}
      style={{ transitionDelay: `${delay}ms` }}
    >
      {children}
    </div>
  );
}

function GlassCard({
  children,
  className = '',
  glow = false,
}: {
  children: React.ReactNode;
  className?: string;
  glow?: boolean;
}) {
  return (
    <div
      className={`rounded-[28px] border border-white/12 bg-[linear-gradient(180deg,rgba(255,255,255,0.08),rgba(255,255,255,0.03))] p-6 shadow-[0_24px_80px_rgba(0,0,0,0.35)] backdrop-blur-xl ${glow ? 'animate-pulse-glow' : ''} ${className}`}
    >
      {children}
    </div>
  );
}

function Divider() {
  return (
    <div className="flex items-center justify-center py-8">
      <div className="h-px w-16 bg-gradient-to-r from-transparent to-emerald-300/60" />
      <div className="mx-3 h-2 w-2 rounded-full bg-emerald-300/70" />
      <div className="h-px w-16 bg-gradient-to-l from-transparent to-emerald-300/60" />
    </div>
  );
}

function PhaseBadge({ label, color }: { label: string; color: string }) {
  return (
    <span
      className={`inline-flex rounded-full border px-3 py-1 text-xs font-semibold uppercase tracking-[0.2em] ${color}`}
    >
      {label}
    </span>
  );
}

function Fence({
  children,
  accent = 'emerald',
}: {
  children: React.ReactNode;
  accent?: 'emerald' | 'amber' | 'cyan';
}) {
  const accentClass =
    accent === 'amber'
      ? 'border-amber-300/18 bg-amber-300/6'
      : accent === 'cyan'
        ? 'border-cyan-300/18 bg-cyan-300/6'
        : 'border-emerald-300/18 bg-emerald-300/6';

  return (
    <pre
      className={`overflow-x-auto rounded-[24px] border p-5 font-mono text-[13px] leading-6 text-white/78 ${accentClass}`}
    >
      {children}
    </pre>
  );
}

function RadarChart({
  values,
  labels,
  active,
}: {
  values: number[];
  labels: string[];
  active: boolean;
}) {
  const cx = 120;
  const cy = 120;
  const r = 86;
  const n = values.length;
  const angleStep = (2 * Math.PI) / n;

  const points = values
    .map((v, i) => {
      const a = angleStep * i - Math.PI / 2;
      const dist = active ? (v / 100) * r : 0;
      return `${cx + dist * Math.cos(a)},${cy + dist * Math.sin(a)}`;
    })
    .join(' ');

  return (
    <svg viewBox="0 0 240 240" className="w-full max-w-[250px]">
      {[0.25, 0.5, 0.75, 1].map((scale) => (
        <polygon
          key={scale}
          points={Array.from({ length: n }, (_, i) => {
            const a = angleStep * i - Math.PI / 2;
            return `${cx + r * scale * Math.cos(a)},${cy + r * scale * Math.sin(a)}`;
          }).join(' ')}
          fill="none"
          stroke="rgba(255,255,255,0.08)"
          strokeWidth="1"
        />
      ))}
      {labels.map((_, i) => {
        const a = angleStep * i - Math.PI / 2;
        return (
          <line
            key={i}
            x1={cx}
            y1={cy}
            x2={cx + r * Math.cos(a)}
            y2={cy + r * Math.sin(a)}
            stroke="rgba(255,255,255,0.12)"
            strokeWidth="1"
          />
        );
      })}
      <polygon
        points={points}
        fill="rgba(16,185,129,0.18)"
        stroke="#86efac"
        strokeWidth="2"
        style={{ transition: 'all 1.1s cubic-bezier(0.34, 1.56, 0.64, 1)' }}
      />
      {values.map((v, i) => {
        const a = angleStep * i - Math.PI / 2;
        const dist = active ? (v / 100) * r : 0;
        return (
          <circle
            key={i}
            cx={cx + dist * Math.cos(a)}
            cy={cy + dist * Math.sin(a)}
            r="4"
            fill="#86efac"
            stroke="#05110f"
            strokeWidth="1.5"
            style={{ transition: 'all 1.1s cubic-bezier(0.34, 1.56, 0.64, 1)' }}
          />
        );
      })}
      {labels.map((label, i) => {
        const a = angleStep * i - Math.PI / 2;
        const lx = cx + (r + 22) * Math.cos(a);
        const ly = cy + (r + 22) * Math.sin(a);
        return (
          <text
            key={label}
            x={lx}
            y={ly}
            textAnchor="middle"
            dominantBaseline="middle"
            className="fill-white/70 text-[9px] font-medium"
          >
            {label}
          </text>
        );
      })}
    </svg>
  );
}

function IDFBars({ active }: { active: boolean }) {
  const rows = [
    { label: 'Quercus robur', value: 22, occurrences: '50K' },
    { label: 'Pinus radiata', value: 31, occurrences: '2,808' },
    { label: 'Rare endemic', value: 63, occurrences: '50' },
    { label: 'Very rare', value: 82, occurrences: '10' },
  ];

  return (
    <div className="space-y-3">
      {rows.map((row, i) => (
        <div key={row.label}>
          <div className="mb-1 flex justify-between text-[10px] text-white/55">
            <span>{row.label}</span>
            <span>{row.occurrences}</span>
          </div>
          <div className="h-2 overflow-hidden rounded-full bg-white/6">
            <div
              className="h-full rounded-full bg-gradient-to-r from-cyan-400 to-emerald-300 transition-all duration-1000"
              style={{
                width: active ? `${row.value}%` : '0%',
                transitionDelay: `${120 * i}ms`,
              }}
            />
          </div>
        </div>
      ))}
    </div>
  );
}

function GateSlider({ active }: { active: boolean }) {
  const states = [
    {
      label: 'Intact forest',
      alpha: 0.22,
      desc: 'environment and biogeography should dominate',
      color: 'from-emerald-500 to-lime-400',
    },
    {
      label: 'Mixed secondary',
      alpha: 0.5,
      desc: 'satellite and environment split influence',
      color: 'from-cyan-500 to-emerald-400',
    },
    {
      label: 'Managed plantation',
      alpha: 0.82,
      desc: 'satellite structure matters much more',
      color: 'from-amber-400 to-orange-500',
    },
  ];

  return (
    <div className="space-y-4">
      {states.map((state, i) => (
        <div key={state.label} className="rounded-[22px] border border-white/10 bg-white/4 p-4">
          <div className="flex items-center justify-between text-sm font-semibold text-white">
            <span>{state.label}</span>
            <span className="font-mono text-emerald-200">alpha = {state.alpha.toFixed(2)}</span>
          </div>
          <div className="mt-3 h-3 overflow-hidden rounded-full bg-white/7">
            <div
              className={`h-full rounded-full bg-gradient-to-r ${state.color} transition-all duration-1000`}
              style={{
                width: active ? `${state.alpha * 100}%` : '0%',
                transitionDelay: `${i * 180}ms`,
              }}
            />
          </div>
          <p className="mt-2 text-[11px] leading-5 text-white/50">{state.desc}</p>
        </div>
      ))}
    </div>
  );
}

function BenchmarkChart({ active }: { active: boolean }) {
  const bars = [
    { label: 'v1', rank: 1165, color: 'bg-red-400/75' },
    { label: 'v2', rank: 80, color: 'bg-orange-400/75' },
    { label: 'v4', rank: 12, color: 'bg-cyan-400/75' },
    { label: 'v14', rank: 2, color: 'bg-emerald-400/80' },
  ];
  const max = 1200;

  return (
    <div className="flex h-52 items-end gap-4">
      {bars.map((bar, i) => {
        const height = Math.max(8, ((max - bar.rank) / max) * 100);
        return (
          <div key={bar.label} className="flex flex-1 flex-col items-center">
            <div className="mb-2 text-[10px] font-mono text-white/45">#{bar.rank}</div>
            <div className="relative flex h-44 w-full items-end rounded-t-xl bg-white/5 px-2">
              <div
                className={`w-full rounded-t-xl transition-all duration-1000 ${bar.color}`}
                style={{
                  height: active ? `${height}%` : '0%',
                  transitionDelay: `${i * 140}ms`,
                }}
              />
            </div>
            <div className="mt-2 text-xs font-semibold text-white/70">{bar.label}</div>
          </div>
        );
      })}
    </div>
  );
}

function TrainingCurve({ active }: { active: boolean }) {
  const path = 'M20 160 C80 130, 120 110, 170 98 S260 70, 320 58 S430 38, 500 28';
  const path2 = 'M20 150 C80 122, 120 104, 170 92 S260 64, 320 52 S430 42, 500 36';

  return (
    <svg viewBox="0 0 520 180" className="w-full">
      {[0, 1, 2, 3].map((i) => (
        <line
          key={i}
          x1="20"
          y1={30 + i * 35}
          x2="500"
          y2={30 + i * 35}
          stroke="rgba(255,255,255,0.08)"
          strokeWidth="1"
        />
      ))}
      <path
        d={path}
        fill="none"
        stroke="rgba(134,239,172,0.95)"
        strokeWidth="3"
        strokeLinecap="round"
        style={{
          strokeDasharray: 900,
          strokeDashoffset: active ? 0 : 900,
          transition: 'stroke-dashoffset 1.6s ease',
        }}
      />
      <path
        d={path2}
        fill="none"
        stroke="rgba(34,211,238,0.75)"
        strokeWidth="3"
        strokeLinecap="round"
        style={{
          strokeDasharray: 900,
          strokeDashoffset: active ? 0 : 900,
          transition: 'stroke-dashoffset 1.8s ease 0.15s',
        }}
      />
      {[
        { x: 70, y: 132 },
        { x: 145, y: 106 },
        { x: 235, y: 78 },
        { x: 320, y: 58 },
        { x: 405, y: 42 },
        { x: 485, y: 30 },
      ].map((p, i) => (
        <circle
          key={i}
          cx={p.x}
          cy={p.y}
          r={active ? 4 : 0}
          fill="#86efac"
          style={{ transition: `all 0.6s ease ${0.5 + i * 0.08}s` }}
        />
      ))}
    </svg>
  );
}

function ArchitectureDiagram({ active }: { active: boolean }) {
  return (
    <svg viewBox="0 0 680 430" className="w-full max-w-3xl">
      <defs>
        <linearGradient id="g1" x1="0" y1="0" x2="1" y2="1">
          <stop offset="0%" stopColor="#22d3ee" />
          <stop offset="100%" stopColor="#60a5fa" />
        </linearGradient>
        <linearGradient id="g2" x1="0" y1="0" x2="1" y2="1">
          <stop offset="0%" stopColor="#86efac" />
          <stop offset="100%" stopColor="#34d399" />
        </linearGradient>
        <linearGradient id="g3" x1="0" y1="0" x2="1" y2="1">
          <stop offset="0%" stopColor="#fbbf24" />
          <stop offset="100%" stopColor="#fb7185" />
        </linearGradient>
      </defs>

      <rect x="30" y="30" width="170" height="66" rx="14" fill="rgba(34,211,238,0.12)" stroke="url(#g1)" strokeWidth="2" />
      <text x="115" y="55" textAnchor="middle" className="fill-cyan-200 text-[14px] font-bold">
        AlphaEarth
      </text>
      <text x="115" y="74" textAnchor="middle" className="fill-cyan-100/60 text-[10px]">
        64 current + 512 temporal
      </text>

      <rect x="480" y="30" width="170" height="66" rx="14" fill="rgba(134,239,172,0.12)" stroke="url(#g2)" strokeWidth="2" />
      <text x="565" y="55" textAnchor="middle" className="fill-emerald-200 text-[14px] font-bold">
        Online Context
      </text>
      <text x="565" y="74" textAnchor="middle" className="fill-emerald-100/60 text-[10px]">
        58 env + 6 categorical + location
      </text>

      <rect x="255" y="120" width="170" height="72" rx="16" fill="rgba(251,191,36,0.12)" stroke="url(#g3)" strokeWidth="2" />
      <text x="340" y="147" textAnchor="middle" className="fill-amber-200 text-[14px] font-bold">
        Gated Fusion
      </text>
      <text x="340" y="166" textAnchor="middle" className="fill-amber-100/60 text-[10px]">
        blend satellite and environment
      </text>

      <rect x="220" y="240" width="240" height="74" rx="16" fill="rgba(255,255,255,0.05)" stroke="rgba(255,255,255,0.2)" strokeWidth="2" />
      <text x="340" y="268" textAnchor="middle" className="fill-white text-[14px] font-bold">
        Residual Trunk
      </text>
      <text x="340" y="287" textAnchor="middle" className="fill-white/55 text-[10px]">
        384 hidden, 6 blocks, location encoded
      </text>

      <rect x="90" y="342" width="200" height="58" rx="14" fill="rgba(134,239,172,0.12)" stroke="rgba(134,239,172,0.6)" strokeWidth="2" />
      <text x="190" y="366" textAnchor="middle" className="fill-emerald-200 text-[13px] font-bold">
        Species Head
      </text>
      <text x="190" y="384" textAnchor="middle" className="fill-emerald-100/60 text-[10px]">
        45,247 species logits
      </text>

      <rect x="390" y="342" width="200" height="58" rx="14" fill="rgba(34,211,238,0.1)" stroke="rgba(34,211,238,0.6)" strokeWidth="2" />
      <text x="490" y="366" textAnchor="middle" className="fill-cyan-200 text-[13px] font-bold">
        Aux Heads
      </text>
      <text x="490" y="384" textAnchor="middle" className="fill-cyan-100/60 text-[10px]">
        planted score + land state
      </text>

      {[
        ['115', '96', '115', '120'],
        ['565', '96', '565', '120'],
        ['115', '120', '255', '156'],
        ['565', '120', '425', '156'],
        ['340', '192', '340', '240'],
        ['280', '314', '190', '342'],
        ['400', '314', '490', '342'],
      ].map(([x1, y1, x2, y2], i) => (
        <line
          key={i}
          x1={x1}
          y1={y1}
          x2={x2}
          y2={y2}
          stroke="rgba(255,255,255,0.28)"
          strokeWidth="2"
          style={{
            opacity: active ? 1 : 0,
            transition: `opacity 0.5s ease ${0.08 * i}s`,
          }}
        />
      ))}
    </svg>
  );
}

const stats = [
  { end: 67743, label: 'Species in Database' },
  { end: 22033317, label: 'Strict Preview Rows' },
  { end: 45247, label: 'V3 Model Species' },
  { end: 19583985, label: 'Neural Parameters' },
];

const timeline = [
  {
    version: 'v0.1',
    date: "Sept '25",
    title: 'Knowledge Graph',
    stat: '67,743 records',
    desc: 'species encyclopedia plus occurrence tiles',
    color: 'border-white/20',
  },
  {
    version: 'v1',
    date: "Oct '25",
    title: 'Single Centroid',
    stat: '~100 species',
    desc: 'AlphaEarth mean-centroid matching',
    color: 'border-cyan-400/30',
  },
  {
    version: 'v2',
    date: "Jan '26",
    title: 'SAFE-B',
    stat: 'multi-signal scoring',
    desc: 'ecological weighting replaces pure similarity',
    color: 'border-purple-400/30',
  },
  {
    version: 'v3 k-NN',
    date: "Feb '26",
    title: 'Occurrence Retrieval',
    stat: '11.4M points',
    desc: 'HNSW + IDF + managed-forest context',
    color: 'border-cyan-300/30',
  },
  {
    version: 'v3 SINR',
    date: "Mar '26",
    title: 'Location-Encoded v14',
    stat: '45,247 species',
    desc: 'SAFE-B + SINR hybrid local runtime',
    color: 'border-emerald-400/35',
  },
];

export default function V3Page() {
  const radarRef = useRef<HTMLDivElement>(null);
  const idfRef = useRef<HTMLDivElement>(null);
  const gateRef = useRef<HTMLDivElement>(null);
  const benchRef = useRef<HTMLDivElement>(null);
  const curveRef = useRef<HTMLDivElement>(null);
  const archRef = useRef<HTMLDivElement>(null);

  const radarVisible = useInView(radarRef);
  const idfVisible = useInView(idfRef);
  const gateVisible = useInView(gateRef);
  const benchVisible = useInView(benchRef);
  const curveVisible = useInView(curveRef);
  const archVisible = useInView(archRef);

  return (
    <div className="relative isolate overflow-hidden bg-[#071211] text-white">
      <div className="absolute inset-0 bg-[radial-gradient(circle_at_top_left,_rgba(146,215,171,0.16),_transparent_26%),radial-gradient(circle_at_90%_10%,_rgba(230,194,94,0.14),_transparent_24%),linear-gradient(180deg,_rgba(6,18,16,0.98),_rgba(4,10,9,0.98))]" />
      <div className="absolute inset-0 opacity-25 [background-image:linear-gradient(rgba(255,255,255,0.06)_1px,transparent_1px),linear-gradient(90deg,rgba(255,255,255,0.06)_1px,transparent_1px)] [background-size:84px_84px]" />

      <section className="relative min-h-[88vh] border-b border-white/10 px-4 pb-16 pt-16 sm:px-6 lg:px-8">
        <div className="mx-auto flex max-w-6xl flex-col items-center text-center">
          <div className="animate-fade-in-up">
            <div className="inline-flex flex-wrap items-center gap-2 rounded-full border border-white/12 bg-white/6 px-4 py-2 text-[11px] uppercase tracking-[0.25em] text-white/70">
              <span>Treekipedia Species Intelligence</span>
              <span className="h-1 w-1 rounded-full bg-emerald-300/70" />
              <span>Claude Visualizer Restored</span>
            </div>
          </div>

          <h1 className="mt-6 animate-fade-in-up-delay-1 font-serif text-5xl leading-none tracking-tight sm:text-6xl lg:text-7xl">
            <span className="bg-gradient-to-r from-emerald-200 to-cyan-200 bg-clip-text text-transparent">
              The v3 Model
            </span>
            <br />
            <span className="text-white">From Static Knowledge to Neural Habitat Prediction</span>
          </h1>

          <p className="mt-6 max-w-3xl animate-fade-in-up-delay-2 text-lg leading-8 text-white/64 sm:text-xl">
            The animations are back. This page keeps the markdown-visualizer feel Claude
            built, but the numbers and caveats now match the current local branch:
            `45,247` mapped species, location-encoded `v14`, strict preview in use, and
            strict-full still not finished.
          </p>

          <div className="mt-8 flex flex-wrap justify-center gap-3 animate-fade-in-up-delay-2">
            <Link
              href="/analysis"
              className="inline-flex items-center gap-2 rounded-full bg-[#e7c46d] px-5 py-3 text-sm font-semibold text-[#17211b] transition-transform duration-300 hover:-translate-y-0.5"
            >
              Open Analysis
              <ArrowRight className="h-4 w-4" />
            </Link>
            <Link
              href="/search"
              className="inline-flex items-center gap-2 rounded-full border border-white/15 bg-white/5 px-5 py-3 text-sm font-semibold text-white transition-colors duration-300 hover:bg-white/10"
            >
              Search Species
            </Link>
          </div>

          <div className="mt-12 grid w-full max-w-5xl grid-cols-2 gap-4 animate-fade-in-up-delay-3 md:grid-cols-4">
            {stats.map((s, i) => (
              <GlassCard key={i} className="py-4">
                <div className="text-2xl font-semibold text-emerald-200 md:text-3xl">
                  <Counter end={s.end} />
                </div>
                <div className="mt-1 text-xs text-white/48">{s.label}</div>
              </GlassCard>
            ))}
          </div>

          <div className="absolute bottom-8 flex flex-col items-center animate-float">
            <div className="mb-2 text-xs text-white/30">Scroll to explore</div>
            <svg width="24" height="24" viewBox="0 0 24 24" fill="none" className="text-white/30">
              <path d="M12 5v14M5 12l7 7 7-7" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
            </svg>
          </div>
        </div>
      </section>

      <Divider />

      <section className="px-4 py-14 sm:px-6 lg:px-8">
        <div className="mx-auto max-w-6xl">
          <Reveal>
            <h2 className="text-center font-serif text-3xl text-white sm:text-4xl">
              The Journey at a Glance
            </h2>
            <p className="mx-auto mt-3 max-w-2xl text-center text-white/52">
              Same narrative structure, corrected for the current branch.
            </p>
          </Reveal>

          <div className="relative mt-10">
            <div className="absolute left-0 right-0 top-1/2 hidden h-px bg-gradient-to-r from-transparent via-emerald-300/30 to-transparent md:block" />
            <div className="grid gap-4 md:grid-cols-5">
              {timeline.map((step, i) => (
                <Reveal key={step.version} delay={i * 100}>
                  <GlassCard className={`relative border-l-2 md:border-l-0 md:border-t-2 ${step.color}`}>
                    <div className="absolute -left-[5px] h-2.5 w-2.5 rounded-full border-2 border-[#071211] bg-emerald-300 md:left-1/2 md:-top-[5px] md:-translate-x-1/2" />
                    <div className="text-[10px] font-mono text-white/38">{step.date}</div>
                    <div className="mt-1 text-lg font-semibold text-white">{step.version}</div>
                    <div className="text-sm font-semibold text-emerald-200">{step.title}</div>
                    <div className="mt-2 text-xs text-white/48">{step.desc}</div>
                    <div className="mt-2 text-xs font-mono text-cyan-200/70">{step.stat}</div>
                  </GlassCard>
                </Reveal>
              ))}
            </div>
          </div>
        </div>
      </section>

      <Divider />

      <section className="px-4 py-14 sm:px-6 lg:px-8">
        <div className="mx-auto max-w-5xl">
          <Reveal>
            <PhaseBadge label="Phase 0" color="border-white/20 bg-white/8 text-white/80" />
            <h2 className="mt-4 font-serif text-3xl text-white sm:text-4xl">
              The Knowledge Graph
            </h2>
            <p className="mb-10 mt-3 max-w-2xl text-white/56">
              Treekipedia started as a structured tree encyclopedia. That layer still
              powers the explanatory context around every prediction.
            </p>
          </Reveal>

          <div className="grid gap-6 md:grid-cols-2">
            <Reveal delay={100} direction="left">
              <GlassCard>
                <div className="flex items-center gap-3 text-emerald-100">
                  <Database className="h-5 w-5" />
                  <h3 className="text-lg font-semibold text-white">Dual-source schema</h3>
                </div>
                <p className="mt-4 text-sm leading-7 text-white/58">
                  Human and AI research fields coexist; the frontend resolves precedence
                  instead of flattening everything into one source.
                </p>
                <div className="mt-5 space-y-2">
                  {['habitat', 'conservation_status', 'growth_form', 'stewardship', 'ecology'].map((field, i) => (
                    <div key={i} className="flex gap-2">
                      <div className="flex-1 rounded-xl border border-cyan-300/15 bg-cyan-300/7 px-3 py-2 text-[10px] font-mono text-cyan-200">
                        {field}_ai
                      </div>
                      <div className="flex-1 rounded-xl border border-emerald-300/15 bg-emerald-300/7 px-3 py-2 text-[10px] font-mono text-emerald-200">
                        {field}_human
                      </div>
                    </div>
                  ))}
                </div>
              </GlassCard>
            </Reveal>

            <Reveal delay={200} direction="right">
              <GlassCard>
                <div className="flex items-center gap-3 text-cyan-100">
                  <MapPinned className="h-5 w-5" />
                  <h3 className="text-lg font-semibold text-white">Geohash occurrence tiles</h3>
                </div>
                <p className="mt-4 text-sm leading-7 text-white/58">
                  Observation density remains a live evidence channel in the current
                  recommendation pipeline.
                </p>
                <div className="mt-5 grid gap-px" style={{ gridTemplateColumns: 'repeat(14, minmax(0, 1fr))' }}>
                  {(() => {
                    const rng = seededRandom(42);
                    return Array.from({ length: 196 }, (_, i) => {
                      const occupied = rng() > 0.58;
                      const intensity = occupied ? 0.18 + rng() * 0.5 : 0.03;
                      return (
                        <div
                          key={i}
                          className="aspect-square rounded-[2px]"
                          style={{
                            backgroundColor: occupied
                              ? `rgba(134,239,172,${intensity})`
                              : `rgba(255,255,255,${intensity})`,
                          }}
                        />
                      );
                    });
                  })()}
                </div>
                <div className="mt-4 flex justify-between text-[10px] text-white/40">
                  <span>5,786,835 tiles</span>
                  <span>48,129 species covered</span>
                </div>
              </GlassCard>
            </Reveal>
          </div>
        </div>
      </section>

      <Divider />

      <section className="px-4 py-14 sm:px-6 lg:px-8">
        <div className="mx-auto max-w-5xl">
          <Reveal>
            <PhaseBadge label="Phase 1" color="border-cyan-300/30 bg-cyan-300/10 text-cyan-100" />
            <h2 className="mt-4 font-serif text-3xl text-white sm:text-4xl">Satellite Embeddings</h2>
            <p className="mb-10 mt-3 max-w-2xl text-white/56">
              AlphaEarth gave the project a habitat fingerprint. The first implementation
              then over-compressed that signal into centroids.
            </p>
          </Reveal>

          <div className="grid gap-6 md:grid-cols-2">
            <Reveal delay={100}>
              <GlassCard glow>
                <div className="flex items-center gap-3 text-cyan-100">
                  <ScanSearch className="h-5 w-5" />
                  <h3 className="text-lg font-semibold text-white">64-D habitat fingerprint</h3>
                </div>
                <p className="mt-4 text-sm leading-7 text-white/58">
                  The key insight is unchanged: the embedding describes habitat, not species.
                </p>
                <div className="mt-5 flex h-20 items-end gap-[2px]">
                  {(() => {
                    const rng = seededRandom(137);
                    return Array.from({ length: 64 }, (_, i) => {
                      const val = Math.sin(i * 0.3) * 0.5 + rng() * 0.5;
                      const h = Math.max(6, Math.abs(val) * 100);
                      const opacity = 0.25 + Math.abs(val) * 0.55;
                      return (
                        <div
                          key={i}
                          className="flex-1 rounded-t-[1px]"
                          style={{
                            height: `${h}%`,
                            backgroundColor:
                              val > 0
                                ? `rgba(34,211,238,${opacity})`
                                : `rgba(168,85,247,${opacity})`,
                          }}
                        />
                      );
                    });
                  })()}
                </div>
              </GlassCard>
            </Reveal>

            <Reveal delay={200}>
              <GlassCard>
                <div className="flex items-center gap-3 text-amber-100">
                  <ShieldAlert className="h-5 w-5" />
                  <h3 className="text-lg font-semibold text-white">The centroid problem</h3>
                </div>
                <p className="mt-4 text-sm leading-7 text-white/58">
                  Averaging multiple habitat modes into one centroid broke ecological
                  specificity and erased native-vs-introduced context.
                </p>
                <Fence accent="amber">
                  {`Pinus radiata:
NZ plantations      !=      AU dry forest

cluster A --------\\
                    > centroid -> neither habitat
cluster B --------/

native / introduced signal:
missing`}
                </Fence>
              </GlassCard>
            </Reveal>
          </div>
        </div>
      </section>

      <Divider />

      <section className="px-4 py-14 sm:px-6 lg:px-8">
        <div className="mx-auto max-w-5xl">
          <Reveal>
            <PhaseBadge label="Phase 2" color="border-purple-300/30 bg-purple-300/10 text-purple-100" />
            <h2 className="mt-4 font-serif text-3xl text-white sm:text-4xl">
              SAFE-B Multi-Signal Scoring
            </h2>
            <p className="mb-10 mt-3 max-w-2xl text-white/56">
              SAFE-B remains part of the live recommendation stack. It was not replaced
              by SINR; it was joined by SINR.
            </p>
          </Reveal>

          <div className="grid gap-6 md:grid-cols-2">
            <Reveal delay={100} direction="left">
              <GlassCard>
                <div ref={radarRef}>
                  <div className="mb-4 flex items-center gap-3 text-purple-100">
                    <Radar className="h-5 w-5" />
                    <h3 className="text-lg font-semibold text-white">SAFE-B Radar</h3>
                  </div>
                  <div className="flex justify-center">
                    <RadarChart
                      values={[82, 78, 58, 72, 49]}
                      labels={['Spatial', 'Abiotic', 'Functional', 'Ecosystem', 'Biotic']}
                      active={radarVisible}
                    />
                  </div>
                </div>
              </GlassCard>
            </Reveal>

            <Reveal delay={200} direction="right">
              <div className="space-y-3">
                {[
                  { letter: 'S', name: 'Spatial', desc: 'occurrence density and nearby evidence' },
                  { letter: 'A', name: 'Abiotic', desc: 'climate, soil, elevation, water, heat' },
                  { letter: 'F', name: 'Functional', desc: 'trait fit for the planting goal' },
                  { letter: 'E', name: 'Ecosystem', desc: 'ecoregion, biome, land context' },
                  { letter: 'B', name: 'Biotic', desc: 'pollinators, dispersers, interactions' },
                ].map((item, i) => (
                  <Reveal key={item.letter} delay={80 * i}>
                    <GlassCard className="rounded-[22px] p-4">
                      <div className="flex items-center gap-4">
                        <div className="flex h-10 w-10 items-center justify-center rounded-2xl border border-white/12 bg-white/7 text-lg font-semibold text-emerald-100">
                          {item.letter}
                        </div>
                        <div>
                          <div className="text-sm font-semibold text-white">{item.name}</div>
                          <div className="text-[11px] text-white/46">{item.desc}</div>
                        </div>
                      </div>
                    </GlassCard>
                  </Reveal>
                ))}
              </div>
            </Reveal>
          </div>
        </div>
      </section>

      <Divider />

      <section className="px-4 py-14 sm:px-6 lg:px-8">
        <div className="mx-auto max-w-5xl">
          <Reveal>
            <PhaseBadge label="Phase 3a" color="border-cyan-300/30 bg-cyan-300/10 text-cyan-100" />
            <h2 className="mt-4 font-serif text-3xl text-white sm:text-4xl">
              Individual Occurrence Matching
            </h2>
            <p className="mb-10 mt-3 max-w-2xl text-white/56">
              The k-NN layer still matters. It is now a discovery channel inside the
              hybrid system, not the whole system.
            </p>
          </Reveal>

          <Reveal>
            <div className="mb-10 text-center">
              <div className="text-5xl font-semibold text-emerald-200 md:text-7xl">
                <Counter end={11400000} />
              </div>
              <div className="mt-2 text-sm text-white/42">individual occurrence embeddings in the retrieval layer</div>
            </div>
          </Reveal>

          <div className="grid gap-6 md:grid-cols-2">
            <Reveal delay={100} direction="left">
              <GlassCard>
                <div ref={idfRef}>
                  <div className="mb-4 flex items-center gap-3 text-emerald-100">
                    <Sparkles className="h-5 w-5" />
                    <h3 className="text-lg font-semibold text-white">IDF Weighting</h3>
                  </div>
                  <p className="mb-4 text-sm leading-7 text-white/58">
                    Rare species matches are more informative than common species with the
                    same raw neighbor count.
                  </p>
                  <IDFBars active={idfVisible} />
                </div>
              </GlassCard>
            </Reveal>

            <Reveal delay={200} direction="right">
              <GlassCard>
                <div className="mb-4 flex items-center gap-3 text-cyan-100">
                  <Trees className="h-5 w-5" />
                  <h3 className="text-lg font-semibold text-white">What changed</h3>
                </div>
                <Fence accent="cyan">
                  {`current recommendation flow:

1. k-NN occurrence search
2. centroid fallback
3. spatial evidence
4. WCVP + ecoregion context
5. SAFE-B scoring
6. SINR re-rank

combined_score = 0.6 SAFE-B + 0.4 SINR`}
                </Fence>
              </GlassCard>
            </Reveal>
          </div>
        </div>
      </section>

      <Divider />

      <section className="px-4 py-14 sm:px-6 lg:px-8">
        <div className="mx-auto max-w-6xl">
          <Reveal>
            <PhaseBadge label="Phase 3b" color="border-emerald-300/30 bg-emerald-300/10 text-emerald-100" />
            <h2 className="mt-4 font-serif text-3xl text-white sm:text-4xl">
              The SINR Neural Model
            </h2>
            <p className="mb-10 mt-3 max-w-2xl text-white/56">
              This is the part that needed the biggest factual correction: the current
              local model is `v14_location_5m`, not the older 35,561-class snapshot.
            </p>
          </Reveal>

          <Reveal delay={100}>
            <GlassCard className="mb-8 max-w-3xl mx-auto">
              <div className="mb-3 flex items-center gap-3 text-amber-100">
                <ShieldAlert className="h-5 w-5" />
                <h3 className="text-base font-semibold text-white">The Plantation Paradox</h3>
              </div>
              <div className="grid gap-4 md:grid-cols-2">
                <div className="rounded-[22px] border border-purple-300/18 bg-purple-300/7 p-4">
                  <div className="text-xs font-semibold uppercase tracking-[0.16em] text-purple-200">
                    Environment says
                  </div>
                  <div className="mt-2 text-sm text-white/66">cool temperate rainforest</div>
                  <div className="mt-1 text-[11px] text-purple-100/56">native beeches and podocarps</div>
                </div>
                <div className="rounded-[22px] border border-cyan-300/18 bg-cyan-300/7 p-4">
                  <div className="text-xs font-semibold uppercase tracking-[0.16em] text-cyan-200">
                    Satellite sees
                  </div>
                  <div className="mt-2 text-sm text-white/66">managed conifer plantation</div>
                  <div className="mt-1 text-[11px] text-cyan-100/56">radiata pine structure dominates</div>
                </div>
              </div>
            </GlassCard>
          </Reveal>

          <Reveal>
            <GlassCard className="mb-8" glow>
              <div className="mb-4 flex items-center gap-3 text-emerald-100">
                <BrainCircuit className="h-5 w-5" />
                <h3 className="text-lg font-semibold text-white">
                  v14 Architecture: location-encoded hybrid runtime
                </h3>
              </div>
              <div ref={archRef} className="flex justify-center">
                <ArchitectureDiagram active={archVisible} />
              </div>
            </GlassCard>
          </Reveal>

          <div className="grid gap-6 md:grid-cols-2">
            <Reveal delay={100} direction="left">
              <GlassCard>
                <div ref={gateRef}>
                  <div className="mb-4 flex items-center gap-3 text-amber-100">
                    <Binary className="h-5 w-5" />
                    <h3 className="text-lg font-semibold text-white">The Learned Gate</h3>
                  </div>
                  <p className="mb-4 text-sm leading-7 text-white/58">
                    Rebuilt as an animation so the page still shows how blending shifts
                    across intact forest, mixed secondary, and plantation-like structure.
                  </p>
                  <GateSlider active={gateVisible} />
                </div>
              </GlassCard>
            </Reveal>

            <Reveal delay={200} direction="right">
              <GlassCard>
                <div className="mb-4 flex items-center gap-3 text-cyan-100">
                  <GitBranch className="h-5 w-5" />
                  <h3 className="text-lg font-semibold text-white">Current local truth</h3>
                </div>
                <Fence accent="emerald">
                  {`primary model:
sinr_v3_v14_location

species:
45,247

inputs:
- 64 current AlphaEarth dims
- 512 temporal dims
- 58 online env features
- 6 categorical features
- 40D location encoding

runtime:
- v3 primary
- v2.2 fallback
- two-pass max inference
- land-state zero mode for parity`}
                </Fence>
              </GlassCard>
            </Reveal>
          </div>
        </div>
      </section>

      <Divider />

      <section className="px-4 py-14 sm:px-6 lg:px-8">
        <div className="mx-auto max-w-5xl">
          <Reveal>
            <h2 className="text-center font-serif text-3xl text-white sm:text-4xl">
              Results and Current Status
            </h2>
            <p className="mx-auto mt-3 max-w-2xl text-center text-white/52">
              Keep the benchmark charts, but keep the caveats too.
            </p>
          </Reveal>

          <div className="mt-10 grid gap-6 md:grid-cols-2">
            <Reveal delay={100}>
              <GlassCard>
                <div className="mb-3 flex items-center gap-3 text-white">
                  <Trees className="h-5 w-5 text-emerald-200" />
                  <h3 className="text-lg font-semibold">P. radiata Benchmark</h3>
                </div>
                <p className="mb-4 text-[11px] text-white/36">
                  lower rank is better, benchmarked locally
                </p>
                <div ref={benchRef}>
                  <BenchmarkChart active={benchVisible} />
                </div>
              </GlassCard>
            </Reveal>

            <Reveal delay={200}>
              <GlassCard>
                <div className="mb-3 flex items-center gap-3 text-white">
                  <Radar className="h-5 w-5 text-cyan-200" />
                  <h3 className="text-lg font-semibold">v14 Training Curve</h3>
                </div>
                <p className="mb-4 text-[11px] text-white/36">
                  animated proxy of the artifact log trend; final val top-10 = 46.3%
                </p>
                <div ref={curveRef}>
                  <TrainingCurve active={curveVisible} />
                </div>
              </GlassCard>
            </Reveal>
          </div>

          <div className="mt-8 grid gap-3 md:grid-cols-4">
            {[
              { label: 'Best Local Rank', value: '#2', sub: 'v14_location_5m' },
              { label: 'Class Count', value: '45,247', sub: 'current mapping contract' },
              { label: 'Strict Preview', value: '22.0M', sub: 'HIT-only rows' },
              { label: 'Carbon Coverage', value: '87.4%', sub: 'preview-safe only' },
            ].map((m, i) => (
              <Reveal key={i} delay={i * 90}>
                <GlassCard className="text-center">
                  <div className="text-2xl font-semibold text-emerald-200">{m.value}</div>
                  <div className="mt-1 text-xs font-semibold text-white/72">{m.label}</div>
                  <div className="text-[10px] text-white/36">{m.sub}</div>
                </GlassCard>
              </Reveal>
            ))}
          </div>
        </div>
      </section>

      <Divider />

      <section className="px-4 py-14 sm:px-6 lg:px-8">
        <div className="mx-auto max-w-5xl">
          <Reveal>
            <h2 className="text-center font-serif text-3xl text-white sm:text-4xl">What&apos;s Next</h2>
            <p className="mx-auto mt-3 max-w-2xl text-center text-white/52">
              Restore the full evidence chain first, then promote.
            </p>
          </Reveal>

          <div className="mt-10 grid gap-6 md:grid-cols-2">
            <Reveal delay={100} direction="left">
              <GlassCard>
                <Fence>
                  {`v3.0 strict preview -> available now
v3.1 strict-full    -> not trained yet

before promotion:
1. finish strict full extraction
2. rebuild strict unified table
3. rerun gateboard + preflight
4. train v3.1 strict-full
5. compare preview vs strict-full`}
                </Fence>
              </GlassCard>
            </Reveal>

            <Reveal delay={200} direction="right">
              <GlassCard>
                <div className="mb-4 flex items-center gap-3 text-amber-100">
                  <Sparkles className="h-5 w-5" />
                  <h3 className="text-lg font-semibold text-white">Active caveats</h3>
                </div>
                <div className="space-y-3">
                  {[
                    'Strict full re-extraction is still incomplete against the 14,710,338-context target.',
                    'Carbon is good enough for preview experiments and not good enough for final-quality claims.',
                    'Land-state parity is still unresolved, so trusted inference uses zero mode there.',
                    'Introduced conditioning is better surfaced now but still not something to oversell.',
                  ].map((line) => (
                    <div
                      key={line}
                      className="rounded-[22px] border border-white/10 bg-white/4 p-4 text-sm leading-7 text-white/60"
                    >
                      {line}
                    </div>
                  ))}
                </div>
              </GlassCard>
            </Reveal>
          </div>
        </div>
      </section>

      <section className="px-4 py-10 text-center sm:px-6 lg:px-8">
        <Reveal>
          <p className="mx-auto max-w-3xl text-xs leading-7 text-white/26">
            This version restores the animated client-side visualizer shell Claude had
            built, while updating the story to reflect the current local v3 stack rather
            than the older February claims.
          </p>
        </Reveal>
      </section>
    </div>
  );
}
