<script setup lang="ts">
// Buttons from DESIGN.md §8. Renders a router link when `to` is given, otherwise a <button>.
// <slot /> in the template is where the button's text goes (like React's `children`).
import type { RouteLocationRaw } from 'vue-router'

withDefaults(
  defineProps<{
    variant?: 'primary' | 'secondary'
    size?: 'md' | 'sm'
    to?: RouteLocationRaw
    type?: 'button' | 'submit'
    disabled?: boolean
  }>(),
  { variant: 'primary', size: 'md', to: undefined, type: 'button', disabled: false },
)
</script>

<template>
  <RouterLink v-if="to" :to="to" class="bt-btn" :class="[variant, size]"><slot /></RouterLink>
  <button v-else :type="type" :disabled="disabled" class="bt-btn" :class="[variant, size]"><slot /></button>
</template>

<style scoped>
/* "scoped" = these rules only apply to this component (like CSS modules). */
.bt-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border-radius: 2px;
  font-family: var(--font-sans);
  text-decoration: none;
  cursor: pointer;
}
.bt-btn:focus-visible {
  outline: 2px solid var(--color-accent);
  outline-offset: 3px;
}
.bt-btn:disabled {
  cursor: default;
}
.primary {
  background: var(--color-bone);
  color: var(--color-on-bone);
  border: 0;
  font-weight: 600;
}
.primary:hover {
  color: var(--color-on-bone);
}
.secondary {
  background: none;
  color: var(--color-bone);
  border: 1px solid var(--color-rule-strong);
  font-weight: 500;
}
.secondary:hover {
  color: var(--color-bone);
}
.md {
  min-height: 48px;
  padding: 0 28px;
  font-size: 15px;
}
.sm {
  min-height: 44px;
  padding: 0 18px;
  font-size: 14px;
}
</style>
