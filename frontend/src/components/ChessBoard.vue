<script setup lang="ts">
// A read-only chessboard: chessground (Lichess's board) themed to DESIGN.md §5.
// The parent passes a position (FEN), the last move and arrows; whenever those props change,
// we tell chessground, which animates the pieces from the old position to the new one.
import { Chessground } from 'chessground'
import type { Api } from 'chessground/api'
import type { DrawBrushes, DrawShape } from 'chessground/draw'
import type { Key } from 'chessground/types'
import { onBeforeUnmount, onMounted, ref, watch } from 'vue'

import { MOTION, prefersReducedMotion, token } from '@/design'
import { type BoardArrow, isLightSquare } from '@/lib/chess'

const props = withDefaults(
  defineProps<{
    fen: string
    label: string // read aloud by screen readers
    lastMove?: [string, string] | null
    arrows?: BoardArrow[]
    coordinates?: boolean
    instant?: boolean // jump to the position without animating (e.g. when a replay restarts)
  }>(),
  { lastMove: null, arrows: () => [], coordinates: false, instant: false },
)

// ref() creates a reactive value (like useState). Here it will hold the <div> chessground draws into,
// because of ref="host" in the template (like useRef in React).
const host = ref<HTMLDivElement>()
let cg: Api | undefined
let resizeObserver: ResizeObserver | undefined

/** Last-move squares get a class for their colour, so light and dark squares get different shades. */
function lastMoveClasses(): Map<Key, string> {
  const classes = new Map<Key, string>()
  for (const sq of props.lastMove ?? []) classes.set(sq as Key, isLightSquare(sq) ? 'bt-last-light' : 'bt-last-dark')
  return classes
}

function arrowShapes(): DrawShape[] {
  return props.arrows.map((a) => ({ orig: a.from as Key, dest: a.to as Key, brush: a.kind }))
}

// onMounted runs once after the component is on the page (like useEffect(() => {...}, [])).
onMounted(() => {
  cg = Chessground(host.value!, {
    fen: props.fen,
    viewOnly: true, // users never move pieces
    coordinates: false, // we draw our own (DESIGN.md §5)
    disableContextMenu: true,
    animation: { enabled: !prefersReducedMotion(), duration: MOTION.moveMs },
    highlight: { lastMove: false, check: false, custom: lastMoveClasses() },
    drawable: {
      enabled: false,
      visible: true,
      autoShapes: arrowShapes(),
      // Our two brushes are merged into chessground's defaults at runtime, so the type's
      // required default colours (green, red, …) are still there — hence the cast.
      brushes: {
        // lineWidth is in 1/64ths of a square: 8 ≈ 0.12 squares = 1.5% of the board (DESIGN.md §5).
        better: { key: 'better', color: token('accent'), opacity: 0.85, lineWidth: 8 },
        refute: { key: 'refute', color: token('blunder'), opacity: 0.85, lineWidth: 8 },
      } as unknown as DrawBrushes,
    },
  })
  // Redraw when the board's size changes (window resize, layout changes).
  resizeObserver = new ResizeObserver(() => cg?.redrawAll())
  resizeObserver.observe(host.value!)
})

// watch() runs a function whenever the watched values change (like useEffect with dependencies).
watch(
  () => [props.fen, props.lastMove, props.arrows],
  () => {
    if (!cg) return
    // Turn animation on/off first: chessground decides whether to animate before applying a change.
    cg.set({ animation: { enabled: !props.instant && !prefersReducedMotion() } })
    cg.set({ fen: props.fen, highlight: { custom: lastMoveClasses() }, drawable: { autoShapes: arrowShapes() } })
  },
  { deep: true },
)

// onBeforeUnmount = cleanup when the component leaves the page (the return function of useEffect).
onBeforeUnmount(() => {
  resizeObserver?.disconnect()
  cg?.destroy()
})

// The 64 squares of the coordinate overlay, a8 first (index 0) to h1 (index 63).
const coordinateSquares = Array.from({ length: 64 }, (_, i) => {
  const row = Math.floor(i / 8)
  const file = i % 8
  return {
    light: (row + file) % 2 === 0,
    rank: file === 0 ? String(8 - row) : '',
    file: row === 7 ? 'abcdefgh'[file] : '',
  }
})
</script>

<template>
  <div class="bt-board" role="img" :aria-label="label">
    <div ref="host"></div>
    <!-- v-if = render only when true (like {coordinates && ...} in JSX).
         v-for = repeat for each item (like .map() in JSX); :key helps Vue track items. -->
    <div v-if="coordinates" class="bt-coords" aria-hidden="true">
      <span
        v-for="(sq, i) in coordinateSquares"
        :key="i"
        :class="sq.light ? 'text-coord-on-light' : 'text-coord-on-dark'"
      >
        <span class="bt-rank">{{ sq.rank }}</span>
        <span class="bt-file">{{ sq.file }}</span>
      </span>
    </div>
  </div>
</template>
