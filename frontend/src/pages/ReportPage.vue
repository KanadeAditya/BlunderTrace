<script setup lang="ts">
// /report/:id — one URL for the whole journey (docs/PLAN.md stage 2):
//   still analysing          → Analysing screen ("Contents"), refreshed every second
//   finished while watching  → "Your report is ready." + Open your report →
//   already finished         → the Report straight away
import { onBeforeUnmount, ref, watch } from 'vue'

import { api, ApiRequestError } from '@/api/client'
import type { Report } from '@/api/types'
import AnalysingView from '@/components/AnalysingView.vue'
import PageMessage from '@/components/PageMessage.vue'
import ReportView from '@/components/ReportView.vue'

// Route params arrive as props because the route has `props: true` (router.ts).
const props = defineProps<{ id: string }>()

const POLL_MS = 1000
const report = ref<Report | null>(null)
const loadError = ref<'not_found' | 'failed' | null>(null)
const watchedProgress = ref(false) // did the user see the analysis running on this visit?
const showReport = ref(false)
let timer: ReturnType<typeof setTimeout> | undefined

async function load() {
  try {
    const r = await api.getReport(props.id)
    report.value = r
    if (r.status === 'queued' || r.status === 'running') {
      watchedProgress.value = true
      timer = setTimeout(load, POLL_MS)
    } else if (r.status === 'done' && !watchedProgress.value) {
      showReport.value = true
    }
  } catch (e) {
    loadError.value = e instanceof ApiRequestError && e.status === 404 ? 'not_found' : 'failed'
  }
}

function openReport() {
  showReport.value = true
  window.scrollTo(0, 0)
}

// immediate: true → also run once right away (on first load), and again if the id in the URL changes.
watch(
  () => props.id,
  () => {
    clearTimeout(timer)
    report.value = null
    loadError.value = null
    watchedProgress.value = false
    showReport.value = false
    load()
  },
  { immediate: true },
)
onBeforeUnmount(() => clearTimeout(timer))
</script>

<template>
  <PageMessage
    v-if="loadError === 'not_found'"
    eyebrow="Report"
    title="This report doesn’t exist."
    detail="It may have expired, or the link is incomplete. Start a new analysis — it takes about three minutes."
    action="New analysis"
  />
  <PageMessage
    v-else-if="loadError === 'failed'"
    eyebrow="Report"
    title="We couldn’t load this report."
    detail="Check your connection and refresh the page. If it keeps happening, start a new analysis."
    action="New analysis"
  />
  <PageMessage
    v-else-if="report?.status === 'failed'"
    eyebrow="Analysis failed"
    title="Something went wrong."
    :detail="report.detail ?? 'The analysis could not be completed.'"
    action="Try again"
  />
  <ReportView v-else-if="report && showReport" :report="report" />
  <AnalysingView v-else-if="report" :report="report" @open="openReport" />
  <div v-else class="min-h-screen bg-page" aria-busy="true"></div>
</template>
