<script setup lang="ts">
// A Vue "single-file component" (.vue) has up to three parts:
//   <script setup>  – the logic (like the body of a React function component)
//   <template>      – the markup (like the JSX you return)
//   <style>         – optional CSS (we use Tailwind classes instead)
//
// defineProps declares the inputs (like React props). withDefaults gives default values.
import { RouterLink } from 'vue-router'

withDefaults(defineProps<{ size?: 'md' | 'sm'; link?: boolean }>(), { size: 'md', link: false })
</script>

<template>
  <!-- <component :is> renders a different element depending on a value:
       a link to Home when `link` is true, otherwise a plain <span>.
       A ":" before an attribute means "this is a JavaScript expression" (like {...} in JSX). -->
  <component
    :is="link ? RouterLink : 'span'"
    :to="link ? '/' : undefined"
    class="font-display text-bone no-underline focus-ring"
    :class="size === 'md' ? 'text-wordmark' : 'text-wordmark-sm'"
  >Blunder<em class="italic text-accent">Trace</em></component>
</template>
