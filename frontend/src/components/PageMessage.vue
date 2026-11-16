<script setup lang="ts">
// A full-page message in the Analysing layout: unknown report, failed analysis, failed load.
import AppWordmark from '@/components/AppWordmark.vue'
import BtButton from '@/components/BtButton.vue'

defineProps<{ eyebrow: string; title: string; detail: string; action: string }>()
</script>

<template>
  <div class="min-h-screen box-border bg-page text-bone font-sans pt-[28px] px-[24px] pb-[88px]">
    <header class="max-w-[1160px] mx-auto flex justify-between items-baseline flex-wrap gap-[12px]">
      <AppWordmark link />
    </header>
    <main class="max-w-[760px] mx-auto mt-[64px]">
      <p class="m-0 font-mono text-label uppercase text-muted">{{ eyebrow }}</p>
      <h1 class="mt-[10px] mb-0 font-display font-[400] text-title-contents">{{ title }}</h1>
      <p class="mt-[16px] mb-0 max-w-[36em] text-lead-sm text-muted">{{ detail }}</p>
      <div class="mt-[28px]">
        <BtButton to="/">{{ action }}</BtButton>
      </div>
    </main>
  </div>
</template>
