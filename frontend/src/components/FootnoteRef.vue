<script setup lang="ts">
// A footnote marker (¹ ²) whose preview shows the retrieved passage behind the advice (DESIGN.md §8).
// Opens on hover, keyboard focus or tap; closes on leave, blur or a click elsewhere.
// Reka UI's Popover handles positioning (stays on screen) and accessibility; the look is ours.
import { PopoverAnchor, PopoverContent, PopoverPortal, PopoverRoot } from 'reka-ui'
import { ref } from 'vue'

import type { Source } from '@/api/types'

defineProps<{ n: number; source: Source }>()
const open = ref(false)
</script>

<template>
  <PopoverRoot :open="open" @update:open="(value) => (open = value)">
    <!-- as-child = don't add an extra element; make our <button> the anchor the preview attaches to. -->
    <PopoverAnchor as-child>
      <button
        type="button"
        :aria-label="`Footnote ${n}: show the source passage`"
        :aria-expanded="open"
        class="bg-transparent border-0 py-0 px-[3px] font-sans text-[12px] leading-none align-super text-accent cursor-pointer focus-ring"
        @mouseenter="open = true"
        @mouseleave="open = false"
        @focus="open = true"
        @blur="open = false"
        @click="open = true"
      >
        {{ n }}
      </button>
    </PopoverAnchor>
    <PopoverPortal>
      <PopoverContent
        side="bottom"
        align="start"
        :side-offset="10"
        :align-offset="-16"
        class="z-50 w-[340px] box-border px-[18px] py-[16px] bg-surface border border-solid border-rule-strong shadow-[0_12px_32px_rgba(0,0,0,0.45)] text-left leading-[1.5] font-sans"
        @open-auto-focus.prevent
        @close-auto-focus.prevent
      >
        <span class="block font-mono text-micro uppercase text-muted">Retrieved passage · used for this advice</span>
        <span class="block mt-[10px] font-display italic text-[16px] text-bone">“{{ source.passage }}”</span>
        <span class="block mt-[10px] text-[13px] text-muted">{{ source.title }}</span>
      </PopoverContent>
    </PopoverPortal>
  </PopoverRoot>
</template>
