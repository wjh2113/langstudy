<template>
  <svg :width="size" :height="size" viewBox="0 0 24 24" fill="none" stroke="currentColor" :stroke-width="stroke"
    stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" class="icon">
    <template v-if="name === 'mic'"><rect x="9" y="3" width="6" height="11" rx="3" /><path d="M5 11a7 7 0 0 0 14 0M12 18v3" /></template>
    <rect v-else-if="name === 'stop'" x="6" y="6" width="12" height="12" rx="2" fill="currentColor" stroke="none" />
    <path v-else-if="name === 'play'" d="M7.5 5v14l11-7z" fill="currentColor" stroke="none" />
    <path v-else-if="name === 'play-outline'" d="M7.5 5v14l11-7z" />
    <path v-else-if="name === 'pause'" d="M8.5 5.5v13M15.5 5.5v13" stroke-width="3" />
    <template v-else-if="name === 'eye'"><path d="M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7S2 12 2 12z" /><circle cx="12" cy="12" r="3" /></template>
    <template v-else-if="name === 'eye-off'"><path d="M3 3l18 18M10.6 5.1A10.4 10.4 0 0 1 12 5c6.5 0 10 7 10 7a17.6 17.6 0 0 1-3.2 4.2M6.6 6.6A17.4 17.4 0 0 0 2 12s3.5 7 10 7a9.8 9.8 0 0 0 5.4-1.6" /><path d="M9.9 9.9a3 3 0 0 0 4.2 4.2" /></template>
    <path v-else-if="name === 'repeat' || name === 'refresh'" d="M4 12a8 8 0 0 1 13.7-5.7L20 8.5M20 4v4.5h-4.5M20 12a8 8 0 0 1-13.7 5.7L4 15.5M4 20v-4.5h4.5" />
    <path v-else-if="name === 'rotate'" d="M3.5 12a8.5 8.5 0 1 0 2.6-6.1L3.5 8.5M3.5 4v4.5H8" />
    <template v-else-if="name === 'home'"><path d="M3.5 10.5 12 4l8.5 6.5" /><path d="M5.5 9.5V20h13V9.5" /><path d="M10 20v-5h4v5" /></template>
    <template v-else-if="name === 'book'"><path d="M12 6.5C10 5 7 4.5 3.5 5v13c3.5-.5 6.5 0 8.5 1.5 2-1.5 5-2 8.5-1.5V5C17 4.5 14 5 12 6.5z" /><path d="M12 6.5v13" /></template>
    <template v-else-if="name === 'logo'"><path d="M12 6.2C9.8 4.6 6.6 4 3 4.6v14c3.6-.6 6.8 0 9 1.6 2.2-1.6 5.4-2.2 9-1.6v-14C17.4 4 14.2 4.6 12 6.2z" fill="currentColor" stroke="none" /><path d="M12 6.4v13.8" stroke="var(--bg)" stroke-width="1.6" /></template>
    <template v-else-if="name === 'clock' || name === 'history'"><circle cx="12" cy="12" r="8.5" /><path d="M12 7.5V12l3 2" /></template>
    <path v-else-if="name === 'star'" d="M12 3.5l2.6 5.4 5.9.8-4.3 4.1 1 5.8-5.2-2.8-5.2 2.8 1-5.8-4.3-4.1 5.9-.8z" />
    <path v-else-if="name === 'star-fill'" d="M12 3.5l2.6 5.4 5.9.8-4.3 4.1 1 5.8-5.2-2.8-5.2 2.8 1-5.8-4.3-4.1 5.9-.8z" fill="currentColor" />
    <template v-else-if="name === 'settings'"><circle cx="12" cy="12" r="3" /><path d="M19.4 15a1.7 1.7 0 0 0 .3 1.8l.1.1a2 2 0 1 1-2.8 2.8l-.1-.1a1.7 1.7 0 0 0-1.8-.3 1.7 1.7 0 0 0-1 1.5V21a2 2 0 1 1-4 0v-.1a1.7 1.7 0 0 0-1.1-1.5 1.7 1.7 0 0 0-1.8.3l-.1.1a2 2 0 1 1-2.8-2.8l.1-.1a1.7 1.7 0 0 0 .3-1.8 1.7 1.7 0 0 0-1.5-1H3a2 2 0 1 1 0-4h.1a1.7 1.7 0 0 0 1.5-1.1 1.7 1.7 0 0 0-.3-1.8l-.1-.1a2 2 0 1 1 2.8-2.8l.1.1a1.7 1.7 0 0 0 1.8.3H9a1.7 1.7 0 0 0 1-1.5V3a2 2 0 1 1 4 0v.1a1.7 1.7 0 0 0 1 1.5 1.7 1.7 0 0 0 1.8-.3l.1-.1a2 2 0 1 1 2.8 2.8l-.1.1a1.7 1.7 0 0 0-.3 1.8V9a1.7 1.7 0 0 0 1.5 1H21a2 2 0 1 1 0 4h-.1a1.7 1.7 0 0 0-1.5 1z" /></template>
    <path v-else-if="name === 'bars'" d="M5 20v-6M10 20V9M15 20v-9M20 20V4" />
    <template v-else-if="name === 'globe'"><circle cx="12" cy="12" r="8.5" /><path d="M3.5 12h17M12 3.5c2.4 2.4 3.6 5.2 3.6 8.5s-1.2 6.1-3.6 8.5c-2.4-2.4-3.6-5.2-3.6-8.5s1.2-6.1 3.6-8.5z" /></template>
    <template v-else-if="name === 'headphones'"><path d="M4 15v-3a8 8 0 0 1 16 0v3" /><rect x="3.5" y="14" width="4" height="6" rx="1.5" /><rect x="16.5" y="14" width="4" height="6" rx="1.5" /></template>
    <template v-else-if="name === 'list'"><path d="M9 6h11M9 12h11M9 18h11" /><path d="M4 6h.01M4 12h.01M4 18h.01" stroke-width="3" /></template>
    <template v-else-if="name === 'list-num'"><path d="M10 6h10M10 12h10M10 18h10" /><path d="M4 5l1.5-1V9M3.5 13.5a1.5 1.5 0 1 1 2.5 1.2L3.5 17H6M3.5 20h2.5" stroke-width="1.6" /></template>
    <template v-else-if="name === 'chat'"><path d="M20 12a7.5 7.5 0 0 1-11 6.6L4 20l1.4-4.3A7.5 7.5 0 1 1 20 12z" /></template>
    <template v-else-if="name === 'chats'"><path d="M15.5 9.5a6 6 0 0 1-8.7 5.4L3 16l1-3.4A6 6 0 1 1 15.5 9.5z" /><path d="M9.6 17.3A6 6 0 0 0 17.2 19L21 20l-1-3.4a6 6 0 0 0-3.6-8.4" /></template>
    <template v-else-if="name === 'chat-dots'"><path d="M20 12a7.5 7.5 0 0 1-11 6.6L4 20l1.4-4.3A7.5 7.5 0 1 1 20 12z" /><path d="M8.5 12h.01M12 12h.01M15.5 12h.01" stroke-width="2.6" /></template>
    <template v-else-if="name === 'doc'"><path d="M14 3.5H7a2 2 0 0 0-2 2v13a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8.5z" /><path d="M14 3.5v5h5M9 13h6M9 16.5h6" /></template>
    <template v-else-if="name === 'note'"><rect x="4.5" y="3.5" width="15" height="17" rx="2" /><path d="M8.5 8h7M8.5 12h7M8.5 16h4" /></template>
    <template v-else-if="name === 'search'"><circle cx="11" cy="11" r="6.5" /><path d="m16 16 4.5 4.5" /></template>
    <path v-else-if="name === 'arrow-right'" d="M5 12h14M13 6l6 6-6 6" />
    <path v-else-if="name === 'arrow-left'" d="M19 12H5M11 6l-6 6 6 6" />
    <path v-else-if="name === 'check'" d="m5 12.5 4.5 4.5L19 7.5" />
    <path v-else-if="name === 'chevron-down'" d="m6 9 6 6 6-6" />
    <path v-else-if="name === 'chevron-up'" d="m6 15 6-6 6 6" />
    <path v-else-if="name === 'chevron-right'" d="m9 6 6 6-6 6" />
    <path v-else-if="name === 'x'" d="M6 6l12 12M18 6 6 18" />
    <path v-else-if="name === 'plus'" d="M12 5v14M5 12h14" />
    <path v-else-if="name === 'sparkle'" d="M12 3c.6 4.4 2.6 6.4 7 7-4.4.6-6.4 2.6-7 7-.6-4.4-2.6-6.4-7-7 4.4-.6 6.4-2.6 7-7zM19 16c.3 1.6 1 2.3 2.5 2.5-1.6.3-2.3 1-2.5 2.5-.3-1.6-1-2.3-2.5-2.5 1.6-.3 2.3-1 2.5-2.5z" fill="currentColor" stroke="none" />
    <template v-else-if="name === 'pen'"><path d="M4 20h4L19 9a2.8 2.8 0 0 0-4-4L4 16z" /><path d="m13.5 6.5 4 4" /></template>
    <template v-else-if="name === 'flag'"><path d="M5 21V4M5 4h11l-2 4 2 4H5" /></template>
    <template v-else-if="name === 'sun'"><circle cx="12" cy="12" r="4" /><path d="M12 2.5v2M12 19.5v2M4.6 4.6l1.4 1.4M18 18l1.4 1.4M2.5 12h2M19.5 12h2M4.6 19.4 6 18M18 6l1.4-1.4" /></template>
    <path v-else-if="name === 'moon'" d="M20 14.5A8 8 0 0 1 9.5 4 8 8 0 1 0 20 14.5z" />
    <template v-else-if="name === 'monitor'"><rect x="3" y="4.5" width="18" height="12" rx="2" /><path d="M8.5 20h7M12 16.5V20" /></template>
    <template v-else-if="name === 'user'"><circle cx="12" cy="8.5" r="4" /><path d="M4.5 20.5a7.5 7.5 0 0 1 15 0" /></template>
    <template v-else-if="name === 'users'"><circle cx="9" cy="8.5" r="3.5" /><path d="M2.5 20a6.5 6.5 0 0 1 13 0" /><path d="M16 5.2a3.5 3.5 0 0 1 0 6.6M18.5 14.3A6.5 6.5 0 0 1 21.5 20" /></template>
    <template v-else-if="name === 'logout'"><path d="M14 4.5h4a2 2 0 0 1 2 2v11a2 2 0 0 1-2 2h-4" /><path d="M10 16.5 5.5 12 10 7.5M5.5 12H15" /></template>
    <template v-else-if="name === 'ticket'"><path d="M3.5 8a2 2 0 0 0 0 4 2 2 0 0 1 0 4V18a1.5 1.5 0 0 0 1.5 1.5h14A1.5 1.5 0 0 0 20.5 18v-2a2 2 0 0 1 0-4 2 2 0 0 0 0-4V6A1.5 1.5 0 0 0 19 4.5H5A1.5 1.5 0 0 0 3.5 6z" /><path d="M14 5v14" stroke-dasharray="2 2.5" /></template>
    <template v-else-if="name === 'link'"><path d="M10 14a4.5 4.5 0 0 0 6.4 0l3-3a4.5 4.5 0 0 0-6.4-6.4l-1 1" /><path d="M14 10a4.5 4.5 0 0 0-6.4 0l-3 3a4.5 4.5 0 0 0 6.4 6.4l1-1" /></template>
    <template v-else-if="name === 'copy'"><rect x="8.5" y="8.5" width="11.5" height="11.5" rx="2" /><path d="M15.5 8.5V6a2 2 0 0 0-2-2H6a2 2 0 0 0-2 2v7.5a2 2 0 0 0 2 2h2.5" /></template>
    <template v-else-if="name === 'trash'"><path d="M4.5 7h15M9.5 7V4.5h5V7M6.5 7l1 13h9l1-13" /></template>
    <template v-else-if="name === 'translate'"><path d="M4 5.5h9M8.5 3.5v2M6 5.5c.7 3.3 2.9 6 6 7.5M11 5.5c-.8 3.8-3.4 7-7 8.5" /><path d="m12.5 20.5 4-9 4 9M14 17.5h5" /></template>
    <template v-else-if="name === 'gauge'"><path d="M4.2 17a8.5 8.5 0 1 1 15.6 0" /><path d="m12 13 4-4.5" /><circle cx="12" cy="13.5" r="1.2" fill="currentColor" /></template>
    <path v-else-if="name === 'wave'" d="M3 12h1.5M7 8v8M10.5 5v14M14 9v6M17.5 7v10M21 12h-1" />
    <template v-else-if="name === 'alert'"><circle cx="12" cy="12" r="9" /><path d="M12 7.5v5.5M12 16.5h.01" stroke-width="2.4" /></template>
    <template v-else-if="name === 'info'"><circle cx="12" cy="12" r="9" /><path d="M12 11v5.5M12 7.5h.01" stroke-width="2.4" /></template>
    <template v-else-if="name === 'check-circle'"><circle cx="12" cy="12" r="9" /><path d="m8 12.5 3 3 5-6" /></template>
    <template v-else-if="name === 'share'"><circle cx="17.5" cy="5.5" r="2.5" /><circle cx="6.5" cy="12" r="2.5" /><circle cx="17.5" cy="18.5" r="2.5" /><path d="m8.7 10.8 6.6-4M8.7 13.2l6.6 4" /></template>
    <template v-else-if="name === 'bulb'"><path d="M9 18h6M10 21h4M12 3a6 6 0 0 0-3.5 10.9c.6.5 1 1.2 1 2.1h5c0-.9.4-1.6 1-2.1A6 6 0 0 0 12 3z" /></template>
    <template v-else-if="name === 'layers'"><path d="m12 3.5 8.5 4.5-8.5 4.5L3.5 8z" /><path d="m3.5 12 8.5 4.5 8.5-4.5M3.5 16l8.5 4.5 8.5-4.5" /></template>
    <template v-else-if="name === 'trend'"><path d="M3.5 17 9 11.5l4 4 7.5-8" /><path d="M15 7.5h5.5V13" /></template>
    <template v-else-if="name === 'cards'"><rect x="3.5" y="6.5" width="13" height="13" rx="2" /><path d="M7.5 3.5h11a2 2 0 0 1 2 2v11" /></template>
    <template v-else-if="name === 'ear'"><path d="M7 9a5 5 0 0 1 10 0c0 3-3 4-3 7a3 3 0 0 1-5.5 1.6" /><path d="M10 9.5a2 2 0 0 1 4 0c0 1.2-1.5 1.6-1.5 3" /></template>
    <template v-else-if="name === 'speaker'"><path d="M4 9.5h3.5L12 5.5v13l-4.5-4H4z" fill="currentColor" stroke-linejoin="round" /><path d="M15.5 9a4 4 0 0 1 0 6M18 6.5a7.5 7.5 0 0 1 0 11" /></template>
    <template v-else-if="name === 'bell'"><path d="M6 16.5V11a6 6 0 0 1 12 0v5.5l1.5 2h-15z" /><path d="M10 21h4" /></template>
    <template v-else-if="name === 'lock'"><rect x="5" y="10.5" width="14" height="10" rx="2" /><path d="M8 10.5V7.5a4 4 0 0 1 8 0v3" /></template>
    <template v-else-if="name === 'calendar'"><rect x="3.5" y="5" width="17" height="15.5" rx="2" /><path d="M3.5 9.5h17M8 3v4M16 3v4" /></template>
    <circle v-else cx="12" cy="12" r="8" />
  </svg>
</template>

<script lang="ts">
import { defineComponent } from 'vue'

/** Line icons in one 24×24 grid, drawn with currentColor. */
export default defineComponent({
  name: 'AppIcon',
  props: {
    name: { type: String, required: true },
    size: { type: Number, default: 18 },
    stroke: { type: Number, default: 1.8 },
  },
})
</script>
