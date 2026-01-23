<template id="chat-widget">
  <div class="chat-widget">
    <div v-if="showMinimize && minimized" class="chat-embed-launcher-wrap">
      <q-btn
        flat
        dense
        class="chat-embed-launcher"
        icon="chat_bubble"
        :label="launcherText"
        @click="$emit('toggle-minimize')"
      ></q-btn>
    </div>
    <div v-else>
      <div class="chat-container" ref="chatScroll">
        <div class="chat-messages q-pa-md">
          <q-chat-message
            v-for="message in messages"
            :key="message.id"
            :name="message.sender_name"
            :sent="isSent(message)"
            :stamp="dateFromNow(message.created_at)"
            :bg-color="messageColor(message)"
          >
            <div v-if="message.message_type === 'tip'">
              <q-badge color="amber">Tip</q-badge>
              <span class="q-ml-sm" v-text="message.message"></span>
            </div>
            <div v-else v-text="message.message"></div>
          </q-chat-message>
          <div v-if="!messages.length" class="text-caption text-grey">
            Start the conversation.
          </div>
        </div>
      </div>
      <q-separator></q-separator>
      <div class="q-pt-sm q-px-md q-pb-md">
        <q-form @submit="emitMessage" class="row items-center">
          <q-input
            dense
            outlined
            v-model.trim="messageInput"
            class="col"
            placeholder="Type a message..."
            :disable="sending"
            :maxlength="maxChars || null"
          ></q-input>
          <q-btn
            class="q-ml-sm"
            color="primary"
            unelevated
            icon="send"
            type="submit"
            :disable="!messageInput || sending"
          ></q-btn>
          <q-btn
            v-if="tipsEnabled"
            class="q-ml-sm"
            outline
            color="amber"
            icon="paid"
            @click="$emit('tip')"
          >
            <q-tooltip>Send a tip</q-tooltip>
          </q-btn>
          <q-btn
            v-if="showMinimize"
            class="q-ml-sm"
            flat
            dense
            icon="expand_less"
            @click="$emit('toggle-minimize')"
          >
            <q-tooltip>Minimize</q-tooltip>
          </q-btn>
        </q-form>
        <div v-if="pendingAmount" class="text-caption text-grey q-mt-sm">
          Payment required (<span v-text="pendingAmount"></span> sats)
        </div>
      </div>
    </div>
  </div>
</template>
