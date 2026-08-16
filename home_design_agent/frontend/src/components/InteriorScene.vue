<script setup>
const props = defineProps({
  variant: { type: String, default: 'living' },
})
</script>

<template>
  <svg
    class="scene-svg"
    viewBox="0 0 400 500"
    role="img"
    :aria-label="`${props.variant} interior scene`"
  >
    <defs>
      <linearGradient id="wall" x1="0" y1="0" x2="0" y2="1">
        <stop offset="0" stop-color="#edf3ed" />
        <stop offset="1" stop-color="#dbe8dd" />
      </linearGradient>
      <linearGradient id="wood" x1="0" y1="0" x2="1" y2="0">
        <stop offset="0" stop-color="#d9b181" />
        <stop offset="0.5" stop-color="#c89662" />
        <stop offset="1" stop-color="#b9824c" />
      </linearGradient>
      <linearGradient id="sky" x1="0" y1="0" x2="0" y2="1">
        <stop offset="0" stop-color="#bfe3d0" />
        <stop offset="1" stop-color="#eaf7ef" />
      </linearGradient>
      <linearGradient id="rug" x1="0" y1="0" x2="1" y2="1">
        <stop offset="0" stop-color="#f0e4d1" />
        <stop offset="1" stop-color="#e5cfae" />
      </linearGradient>
      <linearGradient id="glass" x1="0" y1="0" x2="1" y2="1">
        <stop offset="0" stop-color="#ffffff" stop-opacity="0.95" />
        <stop offset="1" stop-color="#e9f2ec" stop-opacity="0.85" />
      </linearGradient>
      <linearGradient id="leaf" x1="0" y1="0" x2="1" y2="1">
        <stop offset="0" stop-color="#4e8a64" />
        <stop offset="1" stop-color="#2f6b4f" />
      </linearGradient>
      <filter id="soft" x="-20%" y="-20%" width="140%" height="140%">
        <feGaussianBlur stdDeviation="10" />
      </filter>
    </defs>

    <!-- shared room -->
    <rect x="0" y="0" width="400" height="350" fill="url(#wall)" />
    <circle cx="330" cy="40" r="72" fill="#f7c966" opacity="0.22" filter="url(#soft)" />
    <path d="M0 350 L400 350 L400 500 L0 500 Z" fill="url(#wood)" />
    <g opacity="0.18" stroke="#7d4f28" stroke-width="2">
      <path d="M0 368 L400 368" />
      <path d="M0 392 L400 392" />
      <path d="M0 416 L400 416" />
      <path d="M0 440 L400 440" />
      <path d="M0 464 L400 464" />
      <path d="M0 488 L400 488" />
      <path d="M118 350 L94 500" />
      <path d="M208 350 L224 500" />
      <path d="M318 350 L296 500" />
    </g>

    <!-- window -->
    <g v-if="variant !== 'kitchen'">
      <rect x="44" y="46" width="150" height="190" rx="14" fill="url(#sky)" stroke="#ffffff" stroke-width="8" />
      <path d="M119 46 V236 M44 141 H194" stroke="#ffffff" stroke-width="6" />
      <path d="M30 46 C30 22 62 14 84 18 L82 32" fill="none" stroke="#8fc7a4" stroke-width="4" stroke-linecap="round" opacity="0.7" />
    </g>

    <!-- living -->
    <g v-if="variant === 'living'">
      <ellipse cx="230" cy="360" rx="150" ry="34" fill="url(#rug)" opacity="0.9" />
      <rect x="150" y="272" width="190" height="66" rx="24" fill="#75927c" />
      <rect x="150" y="306" width="190" height="34" rx="17" fill="#5f7c68" />
      <rect x="168" y="256" width="64" height="34" rx="17" fill="#7d9a84" />
      <rect x="262" y="256" width="64" height="34" rx="17" fill="#7d9a84" />
      <path d="M122 300 C142 278 166 266 194 266 L194 306 C166 308 142 318 122 338 Z" fill="#5f7c68" />
      <path d="M262 300 C284 278 310 266 336 266 L336 306 C310 308 284 318 262 338 Z" fill="#5f7c68" />
      <rect x="196" y="368" width="58" height="20" rx="10" fill="#b9824c" />
      <rect x="204" y="354" width="18" height="16" rx="4" fill="#7d5a36" />
      <circle cx="258" cy="356" r="10" fill="#f2dfc4" />
      <circle cx="192" cy="356" r="10" fill="#f2dfc4" />
      <path d="M320 300 L320 356" stroke="#8c5f33" stroke-width="8" stroke-linecap="round" />
      <path d="M320 300 L352 314 M320 300 L288 314" stroke="#8c5f33" stroke-width="6" stroke-linecap="round" />
      <circle cx="320" cy="292" r="18" fill="#f6e2b7" opacity="0.95" />
    </g>

    <!-- bedroom -->
    <g v-else-if="variant === 'bedroom'">
      <ellipse cx="210" cy="376" rx="156" ry="34" fill="url(#rug)" opacity="0.9" />
      <rect x="92" y="264" width="240" height="98" rx="22" fill="#f6f1e8" />
      <path d="M112 264 Q200 228 308 264" fill="#75927c" />
      <rect x="110" y="288" width="204" height="60" rx="18" fill="#dbe6dc" />
      <rect x="110" y="288" width="204" height="22" rx="11" fill="#eaf2ec" />
      <rect x="136" y="344" width="30" height="40" rx="12" fill="#b9824c" />
      <rect x="290" y="344" width="30" height="40" rx="12" fill="#b9824c" />
      <rect x="60" y="360" width="16" height="42" rx="7" fill="#8c5f33" />
      <rect x="60" y="354" width="26" height="14" rx="6" fill="#f2dfc4" />
      <circle cx="330" cy="232" r="24" fill="#f6dfae" opacity="0.92" />
      <path d="M330 208 V172" stroke="#8c5f33" stroke-width="4" stroke-linecap="round" />
    </g>

    <!-- kitchen -->
    <g v-else-if="variant === 'kitchen'">
      <ellipse cx="200" cy="376" rx="150" ry="32" fill="url(#rug)" opacity="0.85" />
      <rect x="46" y="200" width="180" height="124" rx="14" fill="#75927c" />
      <rect x="56" y="210" width="76" height="104" rx="10" fill="#5f7c68" />
      <rect x="142" y="210" width="74" height="104" rx="10" fill="#5f7c68" />
      <rect x="64" y="196" width="12" height="18" rx="6" fill="#d8b181" />
      <rect x="162" y="196" width="12" height="18" rx="6" fill="#d8b181" />
      <rect x="256" y="234" width="118" height="88" rx="14" fill="#b9824c" />
      <rect x="256" y="214" width="118" height="20" rx="10" fill="#d8b181" />
      <rect x="80" y="290" width="120" height="12" rx="6" fill="#ffffff" opacity="0.5" />
      <rect x="236" y="330" width="120" height="28" rx="14" fill="#f6f1e8" />
      <path d="M290 330 V358" stroke="#8c5f33" stroke-width="4" />
    </g>

    <!-- plant -->
    <g>
      <path d="M366 330 C382 330 384 352 366 352 C349 352 351 330 366 330 Z" fill="#b9824c" />
      <path d="M366 330 Q338 292 350 262" fill="none" stroke="url(#leaf)" stroke-width="9" stroke-linecap="round" />
      <path d="M366 330 Q392 286 386 256" fill="none" stroke="url(#leaf)" stroke-width="9" stroke-linecap="round" />
      <path d="M366 332 Q358 292 332 286" fill="none" stroke="url(#leaf)" stroke-width="8" stroke-linecap="round" />
      <path d="M366 332 Q386 300 396 300" fill="none" stroke="url(#leaf)" stroke-width="8" stroke-linecap="round" />
      <path d="M366 332 Q366 292 372 272" fill="none" stroke="url(#leaf)" stroke-width="8" stroke-linecap="round" />
    </g>

    <!-- iPhone-style status pill -->
    <rect x="146" y="26" width="108" height="18" rx="9" fill="#204b37" opacity="0.9" />
    <circle cx="188" cy="35" r="4" fill="#f7c966" />
    <rect x="198" y="33" width="42" height="4" rx="2" fill="#ffffff" opacity="0.8" />
  </svg>
</template>

<style scoped>
.scene-svg {
  display: block;
  width: 100%;
  height: 100%;
}
</style>
