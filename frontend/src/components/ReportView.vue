<script setup lang="ts">
// Report (DESIGN.md §9.3) — matches docs/design/reference/report.dc.html.
import { CollapsibleContent, CollapsibleRoot, CollapsibleTrigger } from 'reka-ui'
import { computed, reactive } from 'vue'

import type { GameResult, Report, ReportGame, Weakness } from '@/api/types'
import AppWordmark from '@/components/AppWordmark.vue'
import ExampleFigure from '@/components/ExampleFigure.vue'
import RichText from '@/components/RichText.vue'
import { chapterTitle, ROMAN } from '@/content/themes'

const props = defineProps<{ report: Report }>()

const gamesById = computed(() => new Map(props.report.games.map((g) => [g.id, g])))
const totalGames = computed(() => props.report.summary?.games ?? props.report.games.length)

const OUTCOME: Record<GameResult, string> = { win: 'you won', loss: 'you lost', draw: 'drawn' }
const outcomeOf = (gameId: string) => {
  const r = gamesById.value.get(gameId)?.result
  return r ? OUTCOME[r] : ''
}

// reactive() = a reactive object (like useState holding an object you can mutate directly).
// UI state per chapter: is it open, is its example shown, are the extra examples shown.
const ui = reactive<Record<string, { open: boolean; example: boolean; more: boolean }>>({})
function stateOf(theme: string) {
  if (!ui[theme]) ui[theme] = { open: false, example: false, more: false }
  return ui[theme]
}

const weaknesses = computed(() => props.report.weaknesses ?? [])
const first = computed<Weakness | undefined>(() => weaknesses.value[0])
const rest = computed(() => weaknesses.value.slice(1))

const summaryLine = computed(() => {
  const s = props.report.summary
  if (!s) return ''
  const tc = props.report.time_control
  const games = `${s.games} ${tc === 'both' ? '' : tc + ' '}games`
  const n = (k: number, one: string, many: string) => `${k} ${k === 1 ? one : many}`
  return `${games} · ${n(s.wins, 'win', 'wins')}, ${n(s.draws, 'draw', 'draws')}, ${n(s.losses, 'loss', 'losses')} · ${n(s.blunders_per_game, 'blunder', 'blunders')} a game`
})

const RESULT_WORD: Record<GameResult, string> = { win: 'Won', loss: 'Lost', draw: 'Draw' }
function formatDate(iso?: string) {
  if (!iso) return ''
  return new Date(`${iso}T00:00:00`).toLocaleDateString('en-US', { month: 'short', day: 'numeric' })
}
function errorMarks(g: ReportGame) {
  const e = g.errors
  if (!e) return []
  return [
    { text: `?? ${e.blunder}`, cls: 'text-blunder', n: e.blunder },
    { text: `? ${e.mistake + e.miss}`, cls: 'text-mistake', n: e.mistake + e.miss },
    { text: `?! ${e.inaccuracy}`, cls: 'text-inaccuracy', n: e.inaccuracy },
  ].filter((m) => m.n > 0)
}
const finishedGames = computed(() => props.report.games.filter((g) => g.status === 'done'))

const colorWord = (c?: string) => (c === 'black' ? 'Black' : 'White')

/** "Glossary of chess — Wikipedia" → link "Glossary of chess", then " — Wikipedia" (as in the reference). */
function splitSource(title: string) {
  const at = title.lastIndexOf(' — ')
  return at < 0 ? { name: title, site: '' } : { name: title.slice(0, at), site: title.slice(at) }
}

const HEADINGS = ['', 'The habit that costs you games', 'Two habits that cost you games', 'Three habits that cost you games']
const heading = computed(() => HEADINGS[Math.min(weaknesses.value.length, 3)])
</script>

<template>
  <div class="min-h-screen box-border bg-page text-bone font-sans pt-[28px] px-[24px] pb-[96px]">
    <header class="max-w-[1080px] mx-auto flex justify-between items-baseline flex-wrap gap-[12px]">
      <AppWordmark link />
      <RouterLink to="/" class="text-[14px] focus-ring">New analysis</RouterLink>
    </header>

    <main class="max-w-[1080px] mx-auto mt-[64px]">
      <p class="m-0 font-mono text-label uppercase text-muted">Report</p>
      <h1 class="mt-[10px] mb-0 font-display font-[400] text-title">{{ report.username }}</h1>
      <p class="mt-[14px] mb-0 text-[17px] text-muted">{{ summaryLine }}</p>
      <p v-for="note in report.notes ?? []" :key="note" class="mt-[8px] mb-0 font-display italic text-[16px] text-muted">
        {{ note }}
      </p>

      <h2 v-if="heading" class="mt-[72px] mb-0 font-display font-[400] text-section">{{ heading }}</h2>
      <p v-else class="mt-[72px] mb-0 font-display italic text-[19px] text-muted">
        No mistake came up often enough to call it a habit — the games below show every error.
      </p>

      <!-- Chapter I: always open -->
      <article v-if="first" class="mt-[28px] border-0 border-t border-solid border-rule pt-[32px]">
        <div class="flex items-baseline gap-[20px] flex-wrap">
          <span class="font-display text-numeral text-faint">I.</span>
          <h3 class="m-0 flex-[1_1_320px] font-display font-[400] text-chapter">{{ chapterTitle(first.theme, first.name) }}</h3>
          <span class="font-mono text-[15px] text-muted"
            ><span class="text-[30px] text-bone">{{ first.count }}</span> of {{ totalGames }} games</span
          >
        </div>

        <div class="flex flex-wrap gap-y-[40px] gap-x-[64px] mt-[28px]">
          <div class="flex-[1_1_380px] min-w-0">
            <p class="m-0 font-mono text-label uppercase text-muted">Why it happens</p>
            <p class="mt-[10px] mb-0 text-body"><RichText :text="first.why" :sources="first.sources" /></p>
            <p class="mt-[28px] mb-0 font-mono text-label uppercase text-muted">How to avoid it</p>
            <p class="mt-[10px] mb-0 text-body"><RichText :text="first.how_to_avoid" :sources="first.sources" /></p>
            <div
              v-if="first.sources.length"
              class="mt-[40px] pt-[14px] border-0 border-t border-solid border-rule-subtle text-[13px] leading-[1.8] text-muted"
            >
              <div v-for="(src, i) in first.sources" :key="src.url + i">
                <sup class="text-accent">{{ i + 1 }}</sup> <a :href="src.url" target="_blank" rel="noopener" class="focus-ring">{{
                  splitSource(src.title).name
                }}</a>{{ splitSource(src.title).site }}
              </div>
            </div>
          </div>

          <div v-if="first.examples.length" class="flex-[0_1_320px] min-w-0 flex flex-col gap-[40px]">
            <ExampleFigure
              v-for="(ex, i) in stateOf(first.theme).more ? first.examples : first.examples.slice(0, 1)"
              :key="ex.game_id + ex.ply"
              :example="ex"
              :report-id="report.id"
              :outcome="outcomeOf(ex.game_id)"
              :more-count="i === 0 && !stateOf(first.theme).more ? first.examples.length - 1 : 0"
              @more="stateOf(first.theme).more = true"
            />
          </div>
        </div>
      </article>

      <!-- Chapters II and III: collapsed; text + "Show example" (DESIGN.md §8 "Collapsed chapter") -->
      <article v-for="(w, k) in rest" :key="w.theme" class="mt-[28px] border-0 border-t border-solid border-rule">
        <CollapsibleRoot v-model:open="stateOf(w.theme).open">
          <CollapsibleTrigger
            class="w-full flex items-baseline gap-[20px] flex-wrap pt-[28px] pb-[8px] px-0 bg-transparent border-0 text-bone text-left cursor-pointer focus-ring"
          >
            <span class="font-display text-numeral text-faint">{{ ROMAN[k + 1] }}</span>
            <span class="flex-[1_1_320px] font-display text-chapter-sm">{{ chapterTitle(w.theme, w.name) }}</span>
            <span class="font-mono text-[15px] text-muted"
              ><span class="text-[24px] text-bone">{{ w.count }}</span> of {{ totalGames }} games</span
            >
            <span aria-hidden="true" class="font-mono text-[15px] text-muted">{{ stateOf(w.theme).open ? '−' : '+' }}</span>
          </CollapsibleTrigger>
          <CollapsibleContent>
            <div class="max-w-[640px] pt-[8px] pb-[12px] pl-[56px] pr-0">
              <p class="m-0 text-body"><RichText :text="w.why" :sources="w.sources" /></p>
              <p class="mt-[14px] mb-0 text-body text-muted"><RichText :text="w.how_to_avoid" :sources="w.sources" /></p>
              <div
                v-if="w.sources.length"
                class="mt-[20px] pt-[12px] border-0 border-t border-solid border-rule-subtle text-[13px] leading-[1.8] text-muted"
              >
                <div v-for="(src, i) in w.sources" :key="src.url + i">
                  <sup class="text-accent">{{ i + 1 }}</sup> <a :href="src.url" target="_blank" rel="noopener" class="focus-ring">{{
                    splitSource(src.title).name
                  }}</a>{{ splitSource(src.title).site }}
                </div>
              </div>
              <button
                v-if="w.examples.length"
                type="button"
                class="mt-[16px] bg-transparent border-0 p-0 font-sans text-[14px] text-accent cursor-pointer hover:text-accent-hover focus-ring"
                :aria-expanded="stateOf(w.theme).example"
                @click="stateOf(w.theme).example = !stateOf(w.theme).example"
              >
                {{ stateOf(w.theme).example ? 'Hide example' : 'Show example' }}
              </button>
              <div v-if="stateOf(w.theme).example" class="mt-[24px] max-w-[320px] flex flex-col gap-[40px]">
                <ExampleFigure
                  v-for="(ex, i) in stateOf(w.theme).more ? w.examples : w.examples.slice(0, 1)"
                  :key="ex.game_id + ex.ply"
                  :example="ex"
                  :report-id="report.id"
                  :outcome="outcomeOf(ex.game_id)"
                  :more-count="i === 0 && !stateOf(w.theme).more ? w.examples.length - 1 : 0"
                  @more="stateOf(w.theme).more = true"
                />
              </div>
            </div>
          </CollapsibleContent>
        </CollapsibleRoot>
      </article>

      <section class="mt-[80px] flex flex-wrap gap-y-[48px] gap-x-[64px]">
        <div class="flex-[1_1_300px] min-w-0">
          <h2 class="m-0 font-display font-[400] text-subsection">Tactics you missed</h2>
          <p class="mt-[8px] mb-0 text-[14px] text-muted">Winning chances you had and didn't take.</p>
          <div class="mt-[20px] flex flex-col gap-[10px] text-[16px]">
            <div
              v-for="m in report.missed_tactics ?? []"
              :key="m.theme"
              class="flex justify-between border-0 border-b border-dotted border-rule pb-[8px]"
            >
              <span>{{ m.name }}</span><span class="font-mono">{{ m.count }}</span>
            </div>
          </div>
        </div>
        <div class="flex-[1.4_1_380px] min-w-0">
          <h2 class="m-0 font-display font-[400] text-subsection">Openings</h2>
          <p class="mt-[8px] mb-0 text-[14px] text-muted">Your score in each opening you played at least 4 times.</p>
          <div class="mt-[20px] flex flex-col gap-[14px]">
            <div v-for="o in report.openings ?? []" :key="o.name + o.color" class="flex items-center gap-[16px] flex-wrap">
              <span class="flex-[1_1_200px] text-[16px]"
                >{{ o.name }} <span class="text-muted text-[14px]">· {{ colorWord(o.color) }} · {{ o.games }} games</span></span
              >
              <span aria-hidden="true" class="flex-[0_0_120px] h-[4px] bg-rule-subtle relative">
                <span
                  class="absolute left-0 top-0 bottom-0"
                  :class="o.score < 0.4 ? 'bg-blunder' : 'bg-bone'"
                  :style="{ width: `${Math.round(o.score * 100)}%` }"
                ></span>
              </span>
              <span class="font-mono text-[15px] w-[44px] text-right">{{ Math.round(o.score * 100) }}%</span>
            </div>
          </div>
        </div>
      </section>

      <section class="mt-[80px]">
        <h2 class="m-0 font-display font-[400] text-subsection">Your games</h2>
        <div class="mt-[20px] overflow-x-auto">
          <table class="w-full min-w-[640px] border-collapse text-[15px]">
            <thead>
              <tr class="text-left font-mono text-[12px] tracking-[0.06em] uppercase text-muted">
                <th class="pt-[10px] pb-[10px] pr-[12px] pl-0 font-[400]">Date</th>
                <th class="py-[10px] px-[12px] font-[400]">Opponent</th>
                <th class="py-[10px] px-[12px] font-[400]">Result</th>
                <th class="py-[10px] px-[12px] font-[400]">Opening</th>
                <th class="pt-[10px] pb-[10px] pr-0 pl-[12px] font-[400] text-right">Errors</th>
              </tr>
            </thead>
            <tbody>
              <tr
                v-for="g in finishedGames"
                :key="g.id"
                class="border-0 border-t border-solid border-rule-subtle hover:bg-surface"
              >
                <td class="pt-[14px] pb-[14px] pr-[12px] pl-0 font-mono text-[13px] text-muted whitespace-nowrap">
                  {{ formatDate(g.date) }}
                </td>
                <td class="py-[14px] px-[12px]">
                  <RouterLink :to="{ name: 'game', params: { id: report.id, gameId: g.id } }" class="text-bone focus-ring">{{
                    g.opponent
                  }}</RouterLink>
                  <span class="text-muted text-[13px]"> as {{ colorWord(g.color) }}</span>
                </td>
                <td class="py-[14px] px-[12px]">{{ g.result ? RESULT_WORD[g.result] : '' }}</td>
                <td class="py-[14px] px-[12px] text-muted">{{ g.opening }}</td>
                <td class="pt-[14px] pb-[14px] pr-0 pl-[12px] text-right font-mono whitespace-nowrap">
                  <span v-for="m in errorMarks(g)" :key="m.text" class="ml-[12px]" :class="m.cls">{{ m.text }}</span>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>
    </main>
  </div>
</template>
