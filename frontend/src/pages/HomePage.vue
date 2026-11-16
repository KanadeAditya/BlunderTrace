<script setup lang="ts">
// Home (DESIGN.md §9.1) — matches docs/design/reference/home.dc.html.
import { watchDebounced } from '@vueuse/core'
import {
  SelectContent,
  SelectItem,
  SelectItemText,
  SelectPortal,
  SelectRoot,
  SelectTrigger,
  SelectValue,
  SelectViewport,
  ToggleGroupItem,
  ToggleGroupRoot,
} from 'reka-ui'
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'

import { api, ApiRequestError } from '@/api/client'
import type { Player, TimeControl } from '@/api/types'
import AppWordmark from '@/components/AppWordmark.vue'
import BtButton from '@/components/BtButton.vue'
import ChessBoard from '@/components/ChessBoard.vue'
import { HERO, heroCaption, heroNotation } from '@/content/heroGame'
import { MOTION, prefersReducedMotion } from '@/design'
import { type BoardArrow, START_FEN, tracePath, tracePoints } from '@/lib/chess'

// ---------------------------------------------------------------- hero animation
// `tick` counts 0 → 9 (one move per 1.1 s), holds for 4 more ticks, then starts again.
// computed() = a value derived from other reactive values, recalculated automatically (like useMemo).
const tick = ref(0)
const ply = computed(() => Math.min(tick.value, HERO.lastPly))
let timer: ReturnType<typeof setInterval> | undefined

onMounted(() => {
  if (prefersReducedMotion()) {
    tick.value = HERO.lastPly // show the final frame, no autoplay
    return
  }
  timer = setInterval(() => {
    tick.value = tick.value >= HERO.lastPly + MOTION.heroHoldSteps ? 0 : tick.value + 1
  }, MOTION.heroStepMs)
})
onBeforeUnmount(() => clearInterval(timer))

const heroMove = computed(() => (ply.value > 0 ? HERO.moves[ply.value - 1] : null))
const heroFen = computed(() => heroMove.value?.fen ?? START_FEN)
const heroLastMove = computed<[string, string] | null>(() =>
  heroMove.value ? [heroMove.value.from, heroMove.value.to] : null,
)
const heroArrows = computed<BoardArrow[]>(() =>
  (HERO.arrowsAtPly[ply.value] ?? []).map(([from, to]) => ({ from, to, kind: 'refute' })),
)

const tracePts = tracePoints(HERO.evals, 520, 120, 6)
const trace = computed(() => {
  const [mx, my] = tracePts[HERO.momentPly]
  return {
    full: tracePath(tracePts),
    drawn: tracePath(tracePts.slice(0, ply.value + 1)),
    mx,
    my,
    markerOpacity: ply.value >= HERO.momentPly ? 1 : 0,
  }
})

// ---------------------------------------------------------------- username + player preview
const username = ref('')
const player = ref<Player | null>(null)
// Two separate messages so they can't overwrite each other: one from pressing Analyse
// (shakes), one from the background player lookup (quiet). The submit message wins.
const submitMessage = ref('')
const lookupMessage = ref('')
const message = computed(() => submitMessage.value || lookupMessage.value)
const shakes = ref(0) // bumped on every failed submit, so the message shakes again each time
const input = ref<HTMLInputElement>()

// Typing hides the old preview and the old submit error straight away…
watch(username, () => {
  player.value = null
  submitMessage.value = ''
})

// …and 400 ms after the user stops typing, we look the player up.
watchDebounced(
  username,
  async (value) => {
    const name = value.trim()
    if (name.length < 3) {
      lookupMessage.value = ''
      return
    }
    try {
      const found = await api.getPlayer(name)
      if (username.value.trim() !== name) return // the user kept typing; ignore the old answer
      player.value = found
      lookupMessage.value = ''
    } catch (e) {
      if (username.value.trim() !== name) return
      lookupMessage.value = e instanceof ApiRequestError ? e.message : ''
    }
  },
  { debounce: 400 },
)

// Number of games (DESIGN.md §8 "Game-count selector"): ~9 s of analysis per game.
const GAME_COUNTS = [10, 20, 30, 50]
const gameCount = ref(20)
const minutes = computed(() => Math.ceil((gameCount.value * 9) / 60))

const timeControl = ref<TimeControl>('rapid')
const timeControls = computed(() => {
  const g = player.value?.games
  const options: { value: TimeControl; label: string; count?: number }[] = [
    { value: 'rapid', label: 'Rapid', count: g?.rapid },
    { value: 'blitz', label: 'Blitz', count: g?.blitz },
    { value: 'both', label: 'Both', count: g ? g.rapid + g.blitz : undefined },
  ]
  return options.map((o) => ({ ...o, text: o.count === undefined ? o.label : `${o.label} · ${o.count}` }))
})

const ratingsLine = computed(() => {
  const r = player.value?.ratings ?? {}
  return [r.rapid && `Rapid ${r.rapid}`, r.blitz && `Blitz ${r.blitz}`].filter(Boolean).join(' · ')
})

// ---------------------------------------------------------------- start the analysis
const router = useRouter()
const submitting = ref(false)

async function analyse() {
  const name = username.value.trim()
  if (name.length < 3) {
    submitMessage.value = 'Enter your chess.com username.'
    shakes.value++
    input.value?.focus()
    return
  }
  submitting.value = true
  submitMessage.value = ''
  try {
    const report = await api.startReport({ username: name, time_control: timeControl.value, games: gameCount.value })
    await router.push({ name: 'report', params: { id: report.id } })
  } catch (e) {
    submitMessage.value = e instanceof ApiRequestError ? e.message : 'Something went wrong. Please try again.'
    shakes.value++
  } finally {
    submitting.value = false
  }
}
</script>

<template>
  <div class="min-h-screen box-border bg-page text-bone font-sans pt-[28px] px-[24px] pb-[80px]">
    <header class="max-w-[1160px] mx-auto flex justify-between items-baseline flex-wrap gap-[12px]">
      <AppWordmark />
      <span class="font-mono text-[12px] text-muted">Your games, annotated.</span>
    </header>

    <main class="max-w-[1160px] mx-auto mt-[72px] flex flex-wrap gap-y-[64px] gap-x-[88px] items-center">
      <section class="flex-[1_1_440px] min-w-0">
        <h1 class="m-0 font-display font-[400] text-hero">
          Every lost game has one moment. <em class="block italic text-accent">Find yours.</em>
        </h1>
        <p class="mt-[28px] mb-0 max-w-[34em] text-lead text-muted">
          BlunderTrace reads your recent chess.com games and finds the three mistakes you keep making —
          shown in your own positions, explained in plain English, with sources.
        </p>

        <!-- @submit.prevent = call analyse() and stop the browser's default page reload. -->
        <form class="mt-[44px] max-w-[460px]" novalidate @submit.prevent="analyse">
          <label for="username" class="block font-mono text-label uppercase text-muted">chess.com username</label>
          <!-- v-model = two-way binding: typing updates `username`, and changing `username` updates the box
               (React needs value + onChange for this). -->
          <input
            id="username"
            ref="input"
            v-model="username"
            type="text"
            autocomplete="off"
            spellcheck="false"
            placeholder="e.g. knightowl_42"
            class="block w-full box-border mt-[8px] py-[10px] px-0 bg-transparent border-0 border-b border-solid border-rule-strong text-bone font-display text-input placeholder:text-faint focus:outline-none focus:border-b-accent"
          />

          <div v-if="player" class="flex items-center gap-[14px] mt-[18px]">
            <div
              aria-hidden="true"
              class="w-[40px] h-[40px] flex-none rounded-full border border-solid border-rule-strong flex items-center justify-center font-display text-[18px]"
            >
              {{ player.username.charAt(0).toUpperCase() }}
            </div>
            <div class="min-w-0">
              <div class="text-[15px]">{{ player.username }}</div>
              <div class="font-mono text-[12px] text-muted mt-[3px]">{{ ratingsLine }}</div>
            </div>
          </div>

          <!-- Reka UI's ToggleGroup gives the keyboard + screen-reader behaviour; the look is ours. -->
          <ToggleGroupRoot
            :model-value="timeControl"
            type="single"
            aria-label="Time control"
            class="flex gap-[24px] mt-[22px] flex-wrap"
            @update:model-value="(v) => v && (timeControl = v as TimeControl)"
          >
            <ToggleGroupItem
              v-for="t in timeControls"
              :key="t.value"
              :value="t.value"
              :disabled="t.count === 0"
              class="bg-transparent border-0 border-b border-solid border-b-transparent py-[10px] px-0 min-h-[44px] cursor-pointer font-sans text-[15px] font-[500] text-muted data-[state=on]:text-bone data-[state=on]:border-b-accent data-[disabled]:opacity-35 data-[disabled]:cursor-default focus-ring"
            >
              {{ t.text }}
            </ToggleGroupItem>
          </ToggleGroupRoot>

          <div class="flex items-center gap-[20px] mt-[28px] flex-wrap">
            <BtButton type="submit" :disabled="submitting">Analyse my games</BtButton>
            <span class="font-mono text-[12px] text-muted">
              Last
              <SelectRoot v-model="gameCount">
                <SelectTrigger
                  aria-label="Number of games to analyse"
                  class="bg-transparent border-0 border-b border-dotted border-muted p-0 font-mono text-[12px] leading-[normal] text-bone cursor-pointer focus-ring"
                >
                  <SelectValue />
                </SelectTrigger>
                <!-- A "portal" renders the menu at the end of <body> so nothing can clip it (like React's createPortal). -->
                <SelectPortal>
                  <SelectContent
                    position="popper"
                    side="bottom"
                    align="start"
                    :side-offset="8"
                    class="z-50 min-w-[88px] p-[6px] box-border bg-surface border border-solid border-rule-strong shadow-[0_12px_32px_rgba(0,0,0,0.45)]"
                  >
                    <SelectViewport>
                      <SelectItem
                        v-for="n in GAME_COUNTS"
                        :key="n"
                        :value="n"
                        class="flex items-center min-h-[36px] px-[12px] font-mono text-[13px] text-muted cursor-pointer outline-none data-[highlighted]:bg-surface-hover data-[highlighted]:text-bone data-[state=checked]:text-accent"
                      >
                        <SelectItemText>{{ n }}</SelectItemText>
                      </SelectItem>
                    </SelectViewport>
                  </SelectContent>
                </SelectPortal>
              </SelectRoot>
              games · about {{ minutes }} min · no sign-up
            </span>
          </div>
          <!-- :key changes on every failed submit, so Vue re-creates the element and the shake replays. -->
          <p v-if="message" :key="shakes" role="alert" class="bt-shake mt-[14px] mb-0 text-[15px] text-blunder">
            {{ message }}
          </p>
        </form>
      </section>

      <figure class="flex-[0_1_460px] min-w-0 m-0">
        <div class="w-full max-w-[440px] box-border p-[10px] bg-surface border border-solid border-rule">
          <ChessBoard
            :fen="heroFen"
            :last-move="heroLastMove"
            :arrows="heroArrows"
            :instant="ply === 0"
            label="A chess board replaying a short game that ends in a blunder"
          />
        </div>

        <svg
          viewBox="0 0 520 120"
          width="100%"
          role="img"
          aria-label="Evaluation trace: steady, then a sharp drop after the blunder"
          class="block max-w-[440px] mt-[18px] overflow-visible"
        >
          <line x1="0" y1="60" x2="520" y2="60" stroke="var(--color-selected)" stroke-width="1" stroke-dasharray="3 5" />
          <path :d="trace.full" fill="none" stroke="var(--color-selected)" stroke-width="2" />
          <path
            :d="trace.drawn"
            fill="none"
            stroke="var(--color-bone)"
            stroke-width="2"
            stroke-linejoin="round"
            stroke-linecap="round"
          />
          <circle
            :cx="trace.mx"
            :cy="trace.my"
            r="7"
            fill="none"
            stroke="var(--color-blunder)"
            stroke-width="2"
            :opacity="trace.markerOpacity"
          />
          <text
            :x="trace.mx - 36"
            :y="trace.my + 30"
            fill="var(--color-blunder)"
            font-family="var(--font-mono)"
            font-size="13"
            :opacity="trace.markerOpacity"
          >
            {{ HERO.momentLabel }}
          </text>
        </svg>

        <p class="mt-[14px] mb-0 max-w-[440px] min-h-[40px] font-mono text-[13px] leading-[1.55] text-bone">
          {{ heroNotation(ply) }}
        </p>
        <figcaption class="mt-[8px] max-w-[440px] font-display italic text-[16px] text-muted">
          {{ heroCaption(ply) }}
        </figcaption>
      </figure>
    </main>
  </div>
</template>

<style scoped>
/* Error message shake (DESIGN.md §10): a short side-to-side "no", skipped for reduced motion. */
.bt-shake {
  animation: bt-shake 360ms ease;
}
@keyframes bt-shake {
  0%,
  100% {
    transform: translateX(0);
  }
  20% {
    transform: translateX(-6px);
  }
  40% {
    transform: translateX(6px);
  }
  60% {
    transform: translateX(-4px);
  }
  80% {
    transform: translateX(4px);
  }
}
@media (prefers-reduced-motion: reduce) {
  .bt-shake {
    animation: none;
  }
}
</style>
