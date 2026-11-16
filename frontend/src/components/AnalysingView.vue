<script setup lang="ts">
// Analysing (DESIGN.md §9.2) — matches docs/design/reference/analysing.dc.html:
// a book's "Contents" page that fills in as each game is read.
import { computed } from 'vue'

import type { Report, ReportGame } from '@/api/types'
import AppWordmark from '@/components/AppWordmark.vue'
import BtButton from '@/components/BtButton.vue'
import { winPercent } from '@/lib/chess'

const props = defineProps<{ report: Report }>()
const emit = defineEmits<{ open: [] }>()

const finished = computed(() => props.report.status === 'done')
const done = computed(() => props.report.progress.done)
const total = computed(() => props.report.progress.total)

const gamesWord = computed(() => {
  const tc = props.report.time_control
  return tc === 'both' ? 'games' : `${tc} games`
})

const RESULT_TEXT = { win: 'won', loss: 'lost', draw: 'draw' } as const
const RESULT_CLASS = { win: 'text-bone', loss: 'text-blunder', draw: 'text-muted' } as const

/** The small 120 × 24 trace for one row, drawn at the game's final scale (so it grows left to right). */
function rowPath(game: ReportGame): string {
  const trace = game.trace ?? []
  if (trace.length < 2) return ''
  const plies = Math.max(game.plies ?? trace.length - 1, 1)
  return (
    'M' +
    trace
      .map((cp, i) => `${((i / plies) * 120).toFixed(1)} ${(2 + ((100 - winPercent(cp)) / 100) * 20).toFixed(1)}`)
      .join(' L')
  )
}

/** Error counts in grade colours, e.g. "??2 ?1" — at most two, or "clean". */
function errorMarks(game: ReportGame): { text: string; cls: string }[] {
  const e = game.errors
  if (!e) return []
  const marks: { text: string; cls: string }[] = []
  if (e.blunder) marks.push({ text: `??${e.blunder}`, cls: 'text-blunder' })
  if (e.mistake + e.miss) marks.push({ text: `?${e.mistake + e.miss}`, cls: 'text-mistake' })
  if (e.inaccuracy && marks.length < 2) marks.push({ text: `?!${e.inaccuracy}`, cls: 'text-inaccuracy' })
  if (!marks.length) marks.push({ text: 'clean', cls: 'text-muted' })
  return marks.slice(0, 2)
}

const rows = computed(() =>
  props.report.games.map((g, k) => ({
    key: g.id,
    num: `${k + 1}.`,
    opponent: g.opponent,
    result: g.status === 'done' && g.result ? RESULT_TEXT[g.result] : '',
    resultClass: g.result ? RESULT_CLASS[g.result] : '',
    path: rowPath(g),
    stroke: g.status === 'running' ? 'var(--color-accent)' : 'var(--color-muted)',
    reading: g.status === 'running',
    marks: g.status === 'done' ? errorMarks(g) : [],
    queued: g.status === 'queued',
  })),
)
</script>

<template>
  <div class="min-h-screen box-border bg-page text-bone font-sans pt-[28px] px-[24px] pb-[88px]">
    <header class="max-w-[1160px] mx-auto flex justify-between items-baseline flex-wrap gap-[12px]">
      <AppWordmark link />
      <span class="font-mono text-[12px] text-muted">Report {{ report.id }}</span>
    </header>

    <main class="max-w-[760px] mx-auto mt-[64px]">
      <p class="m-0 font-mono text-label uppercase text-muted">
        {{ finished ? 'Analysis complete' : 'Analysing' }}
      </p>
      <h1 class="mt-[10px] mb-0 font-display font-[400] text-title-contents">
        {{ finished ? 'Your report is ready.' : 'Reading your games…' }}
      </h1>
      <p class="mt-[16px] mb-0 max-w-[36em] text-lead-sm text-muted">
        {{ report.username }} · {{ total }} {{ gamesWord }}. You can close this tab — this page's link keeps working, and the
        report will be waiting.
      </p>

      <div class="mt-[36px] flex items-center gap-[18px]">
        <div
          role="progressbar"
          aria-label="Games analysed"
          aria-valuemin="0"
          :aria-valuemax="total"
          :aria-valuenow="done"
          class="flex-[1_1_auto] h-[2px] bg-rule relative"
        >
          <div
            class="absolute left-0 top-0 bottom-0 bg-bone transition-[width] duration-300 ease-in-out"
            :style="{ width: `${(done / Math.max(total, 1)) * 100}%` }"
          ></div>
        </div>
        <span class="font-mono text-[14px] min-w-[64px] text-right">{{ done }} / {{ total }}</span>
      </div>

      <div v-if="finished" class="mt-[28px]">
        <BtButton @click="emit('open')">Open your report →</BtButton>
      </div>

      <h2 class="mt-[56px] mb-0 font-display font-[400] italic text-contents">Contents</h2>
      <ol class="list-none mt-[16px] mb-0 p-0 border-0 border-t border-solid border-rule">
        <li
          v-for="row in rows"
          :key="row.key"
          class="flex items-center gap-[14px] min-h-[46px] border-0 border-b border-solid border-rule-faint transition-opacity duration-300"
          :class="row.queued ? 'opacity-40' : 'opacity-100'"
        >
          <span class="flex-[0_0_34px] font-mono text-[13px] text-faint">{{ row.num }}</span>
          <span class="flex-[0_1_auto] min-w-0 text-[15px] whitespace-nowrap overflow-hidden text-ellipsis">
            vs {{ row.opponent }} <span class="font-display italic" :class="row.resultClass">{{ row.result }}</span>
          </span>
          <span aria-hidden="true" class="flex-[1_1_24px] border-0 border-b border-dotted border-leader -translate-y-[4px]"></span>
          <svg viewBox="0 0 120 24" width="120" height="24" aria-hidden="true" class="flex-none overflow-visible">
            <line x1="0" y1="12" x2="120" y2="12" stroke="var(--color-rule-subtle)" stroke-width="1" />
            <path :d="row.path" fill="none" :stroke="row.stroke" stroke-width="1.5" stroke-linejoin="round" stroke-linecap="round" />
          </svg>
          <span class="flex-[0_0_104px] text-right font-mono text-[13px] whitespace-nowrap">
            <span v-if="row.reading" class="text-muted">reading…</span>
            <span v-for="m in row.marks" :key="m.text" class="ml-[10px]" :class="m.cls">{{ m.text }}</span>
          </span>
        </li>
      </ol>
    </main>
  </div>
</template>
