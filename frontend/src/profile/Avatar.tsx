// The learner's generated avatar (same seed, same look as the phone app), drawn as inline SVG.
import { useId } from 'react';
import { avatarSpec, initialOf } from './avatarSpec';

export function Avatar({ seed, name, size = 40, label }: { seed: string; name: string; size?: number; label?: string }) {
  const spec = avatarSpec(seed);
  const letter = initialOf(name);
  const id = useId().replace(/:/g, '');
  const glass = 'rgba(255,255,255,0.28)';
  const faint = 'rgba(255,255,255,0.16)';
  const motif = {
    diamond: <><rect x="7" y="7" width="30" height="30" rx="7" fill={faint} transform="rotate(45 22 22)" />
      <rect x="26" y="14" width="16" height="16" rx="4" fill={glass} transform="rotate(45 34 22)" /></>,
    orbit: <><ellipse cx="22" cy="22" rx="17" ry="7" fill="none" stroke={glass} strokeWidth="2.5" />
      <circle cx="39" cy="22" r="4.5" fill={glass} /></>,
    petal: <>{[0, 90, 180, 270].map(r => <rect key={r} x="15" y="0" width="14" height="26" rx="7" fill={faint} transform={`rotate(${r} 22 22)`} />)}</>,
    stack: <><rect x="9" y="19" width="26" height="18" rx="5" fill={faint} transform="rotate(-14 22 28)" />
      <rect x="9" y="7" width="26" height="18" rx="5" fill={glass} transform="rotate(10 22 16)" /></>,
  }[spec.motif];
  return <svg width={size} height={size} viewBox="0 0 44 44" role={label ? 'img' : undefined} aria-label={label} aria-hidden={label ? undefined : true}>
    <defs>
      <linearGradient id={`g${id}`} x1="0" y1="0" x2="1" y2="1"><stop offset="0" stopColor={spec.colors[0]} /><stop offset="1" stopColor={spec.colors[1]} /></linearGradient>
      <clipPath id={`c${id}`}><circle cx="22" cy="22" r="22" /></clipPath>
    </defs>
    <g clipPath={`url(#c${id})`}>
      <rect width="44" height="44" fill={`url(#g${id})`} />
      <g transform={`rotate(${spec.angle} 22 22)`}>{motif}</g>
    </g>
    {letter && <text x="22" y="22" dy="0.36em" textAnchor="middle" fill="#ffffff" fontFamily="var(--font-heading)" fontWeight="800" fontSize="19">{letter}</text>}
  </svg>;
}
