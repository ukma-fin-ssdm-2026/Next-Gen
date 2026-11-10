import academyUrl from "./assets/hero-academy.webp";

import crop1 from "./assets/academy/1.webp";
import crop2 from "./assets/academy/2.webp";
import crop3 from "./assets/academy/3.webp";
import crop4 from "./assets/academy/4.webp";
import crop5 from "./assets/academy/5.webp";
import crop6 from "./assets/academy/6.webp";

const CROPS = [crop1, crop2, crop3, crop4, crop5, crop6];

/** Різні кадри стилізованого фото Старого корпусу для оголошень без фото: кадр залежить від seed. */
export function AcademyPhoto({ seed, className }: { seed: string; className?: string }) {
  let hash = 0;
  for (let i = 0; i < seed.length; i += 1) hash = (hash * 31 + seed.charCodeAt(i)) >>> 0;
  return <img className={className} src={CROPS[hash % CROPS.length]} alt="" width={480} height={360} loading="lazy" decoding="async" />;
}

function Streak({ x, y, w, o }: { x: number; y: number; w: number; o: number }) {
  return (
    <g opacity={o} fill="#fff">
      <ellipse cx={x} cy={y} rx={w} ry={w * 0.07} />
      <ellipse cx={x + w * 0.35} cy={y - w * 0.07} rx={w * 0.55} ry={w * 0.05} />
      <ellipse cx={x - w * 0.3} cy={y + w * 0.06} rx={w * 0.45} ry={w * 0.04} />
    </g>
  );
}

/** Фонова сцена головної: небо «золотої години», витягнуті хмари та зерно. */
export function HeroScene() {
  return (
    <svg className="hero-scene" viewBox="0 0 1440 760" preserveAspectRatio="xMidYMax slice" aria-hidden="true" focusable="false">
      <defs>
        <linearGradient id="hero-sky" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stopColor="#bcd6f7" />
          <stop offset="0.5" stopColor="#d6e5fa" />
          <stop offset="0.82" stopColor="#f3e2dd" />
          <stop offset="1" stopColor="#f8d6c8" />
        </linearGradient>
        <radialGradient id="hero-sun" cx="0.5" cy="0.5" r="0.5">
          <stop offset="0" stopColor="#fff4e8" stopOpacity="0.95" />
          <stop offset="1" stopColor="#fff4e8" stopOpacity="0" />
        </radialGradient>
        <filter id="hero-grain" x="0" y="0" width="100%" height="100%">
          <feTurbulence type="fractalNoise" baseFrequency="0.85" numOctaves="2" stitchTiles="stitch" />
          <feColorMatrix type="saturate" values="0" />
        </filter>
      </defs>
      <rect width="1440" height="760" fill="url(#hero-sky)" />
      <circle cx="1120" cy="600" r="420" fill="url(#hero-sun)" />
      <Streak x={420} y={96} w={170} o={0.55} />
      <Streak x={760} y={170} w={150} o={0.5} />
      <Streak x={1230} y={110} w={210} o={0.6} />
      <Streak x={330} y={420} w={200} o={0.45} />
      <Streak x={560} y={520} w={170} o={0.5} />
      <rect width="1440" height="760" filter="url(#hero-grain)" opacity="0.07" />
    </svg>
  );
}

/** Стилізоване фото Старого корпусу КМА праворуч героя (дуотон у палітрі сайту, без неба). */
export function HeroBuilding() {
  return <img className="hero-building" src={academyUrl} alt="" width={769} height={620} aria-hidden="true" decoding="async" />;
}
