<template id="participants-card">
  <q-card>
    <q-card-section>
      <div class="text-subtitle2">Participants</div>
      <div class="text-caption text-grey">
        <span v-text="participants.length"></span> /
        <span v-text="limit"></span>
      </div>
    </q-card-section>
    <q-card-section class="q-pt-none">
      <q-chip
        v-for="participant in participants"
        :key="participant.id"
        :color="participantColor(participant.id)"
        text-color="black"
        class="q-mb-xs"
      >
        <span v-text="participant.name"></span>
      </q-chip>
    </q-card-section>
  </q-card>
</template>
