<script setup lang="ts">
// One example from the user's games, shown as a book plate (DESIGN.md §8 "Chapter"):
// the position after the opponent's reply, with the threat arrows, and a caption.
import { computed } from 'vue'

import type { Example } from '@/api/types'
import ChessBoard from '@/components/ChessBoard.vue'
import { type BoardArrow, moveLabel, replay } from '@/lib/chess'
import { gradeColorClass, gradeGlyph } from '@/lib/grades'

const props = defineProps<{
  example: Example
  reportId: string
  outcome: string // "you lost", "you won", "drawn"
  moreCount?: number // how many further examples exist (0 = hide the button)
}>()
// defineEmits = the events this component can send to its parent (like an onMore callback prop in React).
const emit = defineEmits<{ more: [] }>()

const position = computed(() => {
  const ex = props.example
  const moves = replay([ex.played, ...ex.punishing_line.slice(0, 1)], ex.fen_before)
  const reply = moves[moves.length - 1]
  return { fen: reply.fen, lastMove: [reply.from, reply.to] as [string, string], reply }
})
const arrows = computed<BoardArrow[]>(() => props.example.arrows.map(([from, to]) => ({ from, to, kind: 'refute' })))
const boardLabel = computed(
  () => `Position after ${moveLabel(props.example.ply + 1, position.value.reply.san)}: ${props.example.note}`,
)
</script>

<template>
  <figure class="min-w-0 m-0">
    <div class="w-full max-w-[320px] box-border p-[8px] bg-surface border border-solid border-rule">
      <ChessBoard
        :fen="position.fen"
        :last-move="position.lastMove"
        :arrows="arrows"
        :label="boardLabel"
        :orientation="example.color"
      />
    </div>
    <figcaption class="mt-[14px] text-[15px] leading-[1.6]">
      <div class="font-mono text-[12px] text-muted">
        vs {{ example.opponent }} · move {{ example.move_number }} · {{ outcome }}
      </div>
      <div class="mt-[6px] font-mono">
        You played {{ moveLabel(example.ply, example.played)
        }}<span :class="gradeColorClass(example.grade)">{{ gradeGlyph(example.grade) }}</span> · better
        {{ moveLabel(example.ply, example.better) }}
      </div>
      <div class="mt-[6px] font-display italic text-muted">{{ example.note }}</div>
      <div class="mt-[12px] flex gap-[20px] flex-wrap">
        <RouterLink
          :to="{ name: 'game', params: { id: reportId, gameId: example.game_id }, query: { ply: example.ply } }"
          class="text-[14px] focus-ring"
        >
          Open in game view →
        </RouterLink>
        <button
          v-if="moreCount"
          type="button"
          class="bg-transparent border-0 p-0 font-sans text-[14px] text-muted cursor-pointer hover:text-bone focus-ring"
          @click="emit('more')"
        >
          {{ moreCount }} more {{ moreCount === 1 ? 'example' : 'examples' }}
        </button>
      </div>
    </figcaption>
  </figure>
</template>
