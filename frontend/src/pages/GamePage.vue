<script setup lang="ts">
// Game view (DESIGN.md §9.4) — matches docs/design/reference/game.dc.html.
import { computed, nextTick, onBeforeUnmount, ref, watch } from 'vue'
import { useRoute } from 'vue-router'

import { api, ApiRequestError } from '@/api/client'
import type { Game } from '@/api/types'
import AppWordmark from '@/components/AppWordmark.vue'
import BtButton from '@/components/BtButton.vue'
import ChessBoard from '@/components/ChessBoard.vue'
import PageMessage from '@/components/PageMessage.vue'
import { MOTION } from '@/design'
import {
  type BoardArrow,
  evalToCp,
  formatEval,
  lineText,
  moveLabel,
  replay,
  tracePath,
  tracePoints,
  winPercent,
} from '@/lib/chess'
import { gradeColorClass, gradeGlyph, gradeName, gradeToken, isError } from '@/lib/grades'

const props = defineProps<{ id: string; gameId: string }>()
const route = useRoute()

/** Stockfish's evaluation of the starting position (≈ +0.2) — the first point of the trace. */
const START_EVAL = { cp: 20 }

// ---------------------------------------------------------------- loading (re-checks while the deep pass runs)
const game = ref<Game | null>(null)
const loadError = ref<'not_found' | 'failed' | null>(null)
let pollTimer: ReturnType<typeof setTimeout> | undefined

async function load(first: boolean) {
  try {
    const g = await api.getGame(props.id, props.gameId)
    game.value = g
    if (first) ply.value = initialPly(g)
    if (g.grading === 'pending') pollTimer = setTimeout(() => load(false), 1000)
  } catch (e) {
    loadError.value = e instanceof ApiRequestError && e.status === 404 ? 'not_found' : 'failed'
  }
}

/** Open at ?ply= if given, else at the user's first error, else at the start. */
function initialPly(g: Game): number {
  const q = Number(route.query.ply)
  if (Number.isInteger(q) && q >= 0 && q <= g.moves.length) return q
  const firstError = g.moves.find((m) => m.color === g.user_color && isError(m.grade))
  return firstError?.ply ?? 0
}

// ---------------------------------------------------------------- position, lines and playback
const ply = ref(0) // 0 = start position, n = after the n-th half-move
const mode = ref<'better' | 'bad' | null>(null) // replaying a line instead of the game
const step = ref(0) // how many moves of the line are shown
let lineTimer: ReturnType<typeof setInterval> | undefined

const moves = computed(() => game.value?.moves ?? [])
const total = computed(() => moves.value.length)
const replayed = computed(() => (game.value ? replay(moves.value.map((m) => m.san), game.value.start_fen) : []))
const current = computed(() => (ply.value > 0 ? moves.value[ply.value - 1] : null))

const lineSans = computed<string[] | null>(() => {
  const m = current.value
  if (!m) return null
  if (mode.value === 'better') return m.better_line
  if (mode.value === 'bad') return m.refutation_line ? [m.san, ...m.refutation_line] : null
  return null
})

// In a line, the board starts from the position before the move being questioned.
const base = computed(() => (mode.value ? ply.value - 1 : ply.value))
const baseFen = computed(() => (base.value === 0 ? (game.value?.start_fen ?? '') : moves.value[base.value - 1].fen_after))
const lineMoves = computed(() => (lineSans.value ? replay(lineSans.value, baseFen.value) : []))

const boardFen = computed(() => (mode.value && step.value > 0 ? lineMoves.value[step.value - 1].fen : baseFen.value))
const boardLastMove = computed<[string, string] | null>(() => {
  if (mode.value && step.value > 0) {
    const m = lineMoves.value[step.value - 1]
    return [m.from, m.to]
  }
  if (base.value === 0) return null
  const m = replayed.value[base.value - 1]
  return m ? [m.from, m.to] : null
})
const boardArrows = computed<BoardArrow[]>(() => {
  if (!mode.value || !lineMoves.value.length) return []
  if (step.value === 0) {
    const first = lineMoves.value[0] // preview the line's first move before it plays
    return [{ from: first.from, to: first.to, kind: mode.value === 'better' ? 'better' : 'refute' }]
  }
  if (mode.value === 'bad' && step.value >= lineMoves.value.length) {
    return (current.value?.refutation_arrows ?? []).map(([from, to]) => ({ from, to, kind: 'refute' }))
  }
  return []
})

function stopLine() {
  clearInterval(lineTimer)
  mode.value = null
  step.value = 0
}
function go(n: number) {
  stopLine()
  ply.value = Math.max(0, Math.min(total.value, n))
}
function play(which: 'better' | 'bad') {
  clearInterval(lineTimer)
  mode.value = which
  step.value = 0
  lineTimer = setInterval(() => {
    if (step.value >= lineMoves.value.length) clearInterval(lineTimer)
    else step.value++
  }, MOTION.lineStepMs)
}

function onKey(e: KeyboardEvent) {
  const keys: Record<string, () => void> = {
    ArrowLeft: () => go(mode.value ? ply.value : ply.value - 1),
    ArrowRight: () => go(mode.value ? ply.value : ply.value + 1),
    Home: () => go(0),
    End: () => go(total.value),
    Escape: () => mode.value && stopLine(),
  }
  if (keys[e.key]) {
    e.preventDefault()
    keys[e.key]()
  }
}

// ---------------------------------------------------------------- evaluation, trace, move list
const evalAt = (p: number) => (p === 0 ? START_EVAL : moves.value[p - 1].eval)
const evalText = computed(() => formatEval(evalAt(base.value)))
const evalWin = computed(() => winPercent(evalToCp(evalAt(base.value))))

const trace = computed(() => {
  const cps = [evalToCp(START_EVAL), ...moves.value.map((m) => evalToCp(m.eval))]
  const pts = tracePoints(cps, 640, 90, 6)
  return {
    path: tracePath(pts),
    dots: moves.value
      .filter((m) => isError(m.grade))
      .map((m) => ({ key: m.ply, x: (pts[m.ply][0] / 640) * 100, y: (pts[m.ply][1] / 90) * 100, color: `var(--color-${gradeToken(m.grade)})` })),
    cx: pts[base.value] ? (pts[base.value][0] / 640) * 100 : 0,
    cy: pts[base.value] ? (pts[base.value][1] / 90) * 100 : 50,
  }
})

const rows = computed(() => {
  const out = []
  for (let i = 0; i < moves.value.length; i += 2) {
    out.push({ num: `${i / 2 + 1}.`, cells: [moves.value[i], moves.value[i + 1]].filter(Boolean) })
  }
  return out
})

// Keep the current move visible in the (scrolling) move list.
const moveList = ref<HTMLElement>()
watch(ply, async () => {
  await nextTick()
  const el = moveList.value?.querySelector<HTMLElement>('[data-current="true"]')
  if (el && moveList.value) {
    const list = moveList.value
    if (el.offsetTop < list.scrollTop || el.offsetTop + el.offsetHeight > list.scrollTop + list.clientHeight) {
      list.scrollTop = el.offsetTop - list.clientHeight / 2
    }
  }
})

// ---------------------------------------------------------------- side panel
const isUserMove = computed(() => current.value?.color === game.value?.user_color)
const mover = computed(() => (isUserMove.value ? 'your' : current.value?.color === 'white' ? 'White’s' : 'Black’s'))
const lossPoints = computed(() => {
  if (!current.value) return 0
  const before = winPercent(evalToCp(evalAt(ply.value - 1)))
  const after = winPercent(evalToCp(evalAt(ply.value)))
  return Math.round(current.value.color === 'white' ? before - after : after - before)
})
const panel = computed(() => {
  const m = current.value
  if (mode.value && m) return 'line'
  if (m && isError(m.grade)) return 'error'
  if (m && (m.grade === 'great' || m.grade === 'brilliant')) return 'great'
  return 'hint'
})
const hasLines = computed(() => !!current.value?.better_line && !!current.value?.refutation_line)
const linesPending = computed(() => !hasLines.value && game.value?.grading === 'pending' && isUserMove.value)
const greatText = computed(() => {
  const m = current.value
  if (!m) return ''
  if (m.grade === 'brilliant') return 'A sacrifice that works — and the best move here.'
  const win = winPercent(evalToCp(m.eval))
  const moverWin = m.color === 'white' ? win : 100 - win
  if (moverWin >= 60) return `The only move that keeps ${mover.value} advantage.`
  if (moverWin >= 40) return 'The only move that holds the balance.'
  return `The only move that keeps ${mover.value === 'your' ? 'you' : m.color === 'white' ? 'White' : 'Black'} in the game.`
})

// ---------------------------------------------------------------- title line
const opponent = computed(() => (game.value ? (game.value.user_color === 'white' ? game.value.black : game.value.white) : ''))
const metaLine = computed(() => {
  const g = game.value
  if (!g) return ''
  const userWon = (g.result === '1-0' && g.user_color === 'white') || (g.result === '0-1' && g.user_color === 'black')
  const outcome = g.result === '1/2-1/2' ? 'drew' : userWon ? 'won' : 'lost'
  const score = g.result === '1/2-1/2' ? '½–½' : g.result.replace('-', '–')
  return `${g.opening} · you played ${g.user_color === 'white' ? 'White' : 'Black'} · ${outcome} ${score}`
})

// ---------------------------------------------------------------- lifecycle
watch(
  () => [props.id, props.gameId],
  () => {
    clearTimeout(pollTimer)
    stopLine()
    game.value = null
    loadError.value = null
    load(true)
  },
  { immediate: true },
)
onBeforeUnmount(() => {
  clearTimeout(pollTimer)
  clearInterval(lineTimer)
})
</script>

<template>
  <PageMessage
    v-if="loadError"
    eyebrow="Game"
    :title="loadError === 'not_found' ? 'This game isn’t in the report.' : 'We couldn’t load this game.'"
    detail="Go back to your report and pick a game from the list."
    action="New analysis"
  />
  <div v-else class="min-h-screen box-border bg-page text-bone font-sans pt-[28px] px-[24px] pb-[72px]">
    <header class="max-w-[1160px] mx-auto flex justify-between items-baseline flex-wrap gap-[12px]">
      <RouterLink :to="{ name: 'report', params: { id } }" class="text-[14px] focus-ring">← Back to report</RouterLink>
      <AppWordmark size="sm" />
    </header>

    <template v-if="game">
      <div class="max-w-[1160px] mx-auto mt-[36px]">
        <h1 class="m-0 font-display font-[400] text-game-title">vs {{ opponent }}</h1>
        <p class="mt-[8px] mb-0 font-mono text-[13px] text-muted">{{ metaLine }}</p>
      </div>

      <main class="max-w-[1160px] mx-auto mt-[32px] flex flex-wrap gap-y-[40px] gap-x-[56px] items-start">
        <!-- tabindex="0" makes the board area focusable so the arrow keys work (DESIGN.md §11). -->
        <section
          tabindex="0"
          aria-label="Board. Use the left and right arrow keys to step through the moves."
          class="flex-[0_1_620px] min-w-0 w-full focus-ring-tight"
          @keydown="onKey"
        >
          <div class="flex gap-[10px] items-stretch">
            <div
              role="img"
              :aria-label="`Evaluation ${evalText}`"
              class="relative flex-[0_0_14px] bg-rule-subtle border border-solid border-rule overflow-hidden"
            >
              <!-- White's share of the bar, on White's side of the board. -->
              <div
                class="absolute left-0 right-0 bg-bone transition-[height] duration-[400ms] ease-in-out"
                :class="game.user_color === 'black' ? 'top-0' : 'bottom-0'"
                :style="{ height: `${evalWin.toFixed(1)}%` }"
              ></div>
            </div>
            <div class="flex-[1_1_auto] min-w-0">
              <div class="box-border p-[8px] bg-surface border border-solid border-rule">
                <ChessBoard
                  :fen="boardFen"
                  :last-move="boardLastMove"
                  :arrows="boardArrows"
                  coordinates
                  :orientation="game.user_color"
                  label="Chess board"
                />
              </div>
            </div>
          </div>

          <div class="flex justify-between items-center gap-[12px] mt-[14px] flex-wrap">
            <span class="font-mono text-[14px] min-w-[56px]">{{ evalText }}</span>
            <div class="flex gap-[4px]">
              <button type="button" aria-label="First move" :disabled="ply === 0 && !mode" class="bt-ctl" @click="go(0)">
                <svg aria-hidden="true" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M6 5v14" /><path d="M18 6l-7 6 7 6" /></svg>
              </button>
              <button type="button" aria-label="Previous move" :disabled="ply === 0 && !mode" class="bt-ctl" @click="go(mode ? ply : ply - 1)">
                <svg aria-hidden="true" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M15 6l-7 6 7 6" /></svg>
              </button>
              <button type="button" aria-label="Next move" :disabled="ply === total && !mode" class="bt-ctl" @click="go(mode ? ply : ply + 1)">
                <svg aria-hidden="true" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M9 6l7 6-7 6" /></svg>
              </button>
              <button type="button" aria-label="Last move" :disabled="ply === total && !mode" class="bt-ctl" @click="go(total)">
                <svg aria-hidden="true" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M6 6l7 6-7 6" /><path d="M18 5v14" /></svg>
              </button>
            </div>
            <span class="min-w-[56px] text-right font-mono text-[12px] text-faint">← → keys</span>
          </div>

          <div aria-hidden="true" class="relative w-full aspect-[640/90] mt-[22px]">
            <svg viewBox="0 0 640 90" preserveAspectRatio="none" class="absolute inset-0 w-full h-full overflow-visible">
              <line x1="0" y1="45" x2="640" y2="45" stroke="var(--color-selected)" stroke-width="1" stroke-dasharray="3 5" vector-effect="non-scaling-stroke" />
              <path :d="trace.path" fill="none" stroke="var(--color-muted)" stroke-width="1.6" stroke-linejoin="round" vector-effect="non-scaling-stroke" />
            </svg>
            <span
              v-for="d in trace.dots"
              :key="d.key"
              class="absolute w-[8px] h-[8px] -ml-[4px] -mt-[4px] rounded-full"
              :style="{ left: `${d.x}%`, top: `${d.y}%`, background: d.color }"
            ></span>
            <span
              class="absolute w-[14px] h-[14px] -ml-[8px] -mt-[8px] rounded-full border-2 border-solid border-accent transition-[left,top] duration-300"
              :style="{ left: `${trace.cx}%`, top: `${trace.cy}%` }"
            ></span>
          </div>
        </section>

        <aside class="flex-[1_1_320px] min-w-0">
          <div class="bg-surface border border-solid border-rule py-[10px] px-[8px]">
            <p class="mt-[4px] mx-[8px] mb-[10px] font-mono text-label uppercase text-muted">Moves</p>
            <ol ref="moveList" class="list-none m-0 p-0 flex flex-col gap-[2px] font-mono text-[15px] max-h-[440px] overflow-y-auto relative">
              <li v-for="row in rows" :key="row.num" class="grid grid-cols-[40px_minmax(0,1fr)_minmax(0,1fr)] items-center">
                <span class="text-faint text-[13px] pl-[8px]">{{ row.num }}</span>
                <button
                  v-for="m in row.cells"
                  :key="m.ply"
                  type="button"
                  :aria-label="`Go to ${moveLabel(m.ply, m.san)}${gradeGlyph(m.grade)}`"
                  :data-current="m.ply === ply"
                  class="text-left min-h-[36px] px-[10px] border-0 text-bone font-mono text-[15px] cursor-pointer hover:bg-surface-hover focus-ring-tight"
                  :class="m.ply === ply ? 'bg-selected font-[600]' : 'bg-transparent font-[400]'"
                  @click="go(m.ply)"
                >
                  {{ m.san }}<span :class="gradeColorClass(m.grade)">{{ gradeGlyph(m.grade) }}</span>
                </button>
              </li>
            </ol>
          </div>

          <div aria-live="polite" class="mt-[20px] border-0 border-t border-solid border-rule pt-[22px] min-h-[180px]">
            <div v-if="panel === 'error' && current">
              <p class="m-0 font-mono text-label uppercase text-muted">{{ isUserMove ? 'Your move' : 'Your opponent’s move' }}</p>
              <p class="mt-[8px] mb-0 font-display text-panel">
                <!-- {{ ' ' }} keeps the space: Vue drops whitespace between tags on separate lines. -->
                <span :class="gradeColorClass(current.grade)">{{ gradeName(current.grade) }}</span>{{ ' ' }}<span
                  class="font-mono text-[20px]"
                  >{{ moveLabel(current.ply, current.san) }}{{ gradeGlyph(current.grade) }}</span
                >
              </p>
              <p class="mt-[8px] mb-0 text-[15px] text-muted">This lost {{ lossPoints }} points of winning chance.</p>
              <div v-if="hasLines" class="flex gap-[10px] flex-wrap mt-[18px]">
                <BtButton size="sm" @click="play('better')">Show better move</BtButton>
                <BtButton size="sm" variant="secondary" @click="play('bad')">Show why it's bad</BtButton>
              </div>
              <p v-else-if="linesPending" class="mt-[18px] mb-0 font-display italic text-[15px] text-muted">
                Working out the better lines…
              </p>
            </div>

            <div v-else-if="panel === 'line' && current">
              <p
                class="m-0 font-mono text-label uppercase"
                :class="mode === 'better' ? 'text-accent' : 'text-blunder'"
              >
                {{ mode === 'better' ? 'Better move' : 'Why it’s bad' }}
              </p>
              <p class="mt-[10px] mb-0 font-mono text-[17px] leading-[1.6]">{{ lineText(current.ply, lineSans ?? []) }}</p>
              <p class="mt-[10px] mb-0 font-display italic text-[17px] leading-[1.5] text-muted">
                {{ mode === 'better' ? current.better_note : current.refutation_note }}
              </p>
              <div class="mt-[16px]">
                <BtButton size="sm" variant="secondary" @click="stopLine">↩ Back to game</BtButton>
              </div>
            </div>

            <div v-else-if="panel === 'great' && current">
              <p class="m-0 font-mono text-label uppercase text-muted">{{ isUserMove ? 'Your move' : 'Your opponent’s move' }}</p>
              <p class="mt-[8px] mb-0 font-display text-panel">
                <span class="text-accent">{{ gradeName(current.grade) }}</span>{{ ' ' }}<span class="font-mono text-[20px]"
                  >{{ moveLabel(current.ply, current.san) }}{{ gradeGlyph(current.grade) }}</span
                >
              </p>
              <p class="mt-[8px] mb-0 text-[15px] text-muted">{{ greatText }}</p>
            </div>

            <p v-else class="m-0 font-display italic text-[17px] text-muted">
              Step to a marked move — ?? ? ?! — to see what went wrong.
            </p>
          </div>
        </aside>
      </main>
    </template>
  </div>
</template>

<style scoped>
/* Board controls (DESIGN.md §8 "Icon control"). */
.bt-ctl {
  width: 48px;
  height: 44px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  background: none;
  border: 1px solid var(--color-rule);
  color: var(--color-bone);
  cursor: pointer;
}
.bt-ctl:hover:not(:disabled) {
  background: var(--color-surface-hover);
}
.bt-ctl:disabled {
  opacity: 0.35;
  cursor: default;
}
.bt-ctl:focus-visible {
  outline: 2px solid var(--color-accent);
  outline-offset: 2px;
}
</style>
