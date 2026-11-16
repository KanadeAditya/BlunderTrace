<script setup lang="ts">
// Renders card text from the API: `*…*` → emphasis in Fraunces italic, `[n]` → footnote marker.
// No wrapper element: it drops straight into the parent <p> (a "fragment" in React terms).
import { computed } from 'vue'

import type { Source } from '@/api/types'
import FootnoteRef from '@/components/FootnoteRef.vue'
import { parseMarked } from '@/lib/richText'

const props = defineProps<{ text: string; sources: Source[] }>()
const segments = computed(() => parseMarked(props.text, props.sources.length))
</script>

<template>
  <!-- <template v-for> repeats its content without adding an element around it. -->
  <template v-for="(seg, i) in segments" :key="i">
    <template v-if="seg.kind === 'text'">{{ seg.text }}</template>
    <em v-else-if="seg.kind === 'em'" class="font-display text-[19px]">{{ seg.text }}</em>
    <FootnoteRef v-else :n="seg.n" :source="sources[seg.n - 1]" />
  </template>
</template>
