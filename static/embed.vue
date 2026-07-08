<template id="page-chat-embed">
  <div class="chat-embed">
    <div v-if="isMinimized" class="chat-embed-launcher-wrap">
      <q-btn
        flat
        dense
        class="chat-embed-launcher"
        icon="chat_bubble"
        :label="launcherText"
        @click="toggleMinimize"
      ></q-btn>
      <i class="text-caption q-pl-sm">powered by LNbits</i>
    </div>
    <div v-else class="chat-embed-body">
      <div class="chat-embed-header q-pa-sm">
        <div v-if="!chatData.messages.length" class="text-caption text-grey">
          Start the conversation.
        </div>
        <div class="chat-embed-actions">
          <q-btn
            v-if="chatId"
            flat
            dense
            icon="add_comment"
            @click="startNewChat"
          >
            <q-tooltip>Start a new chat</q-tooltip>
          </q-btn>
          <q-btn
            v-if="chatId"
            flat
            dense
            icon="open_in_new"
            :href="publicChatLink"
            target="_blank"
          >
            <q-tooltip>Open public chat</q-tooltip>
          </q-btn>
          <q-btn flat dense icon="expand_less" @click="toggleMinimize">
            <q-tooltip>Minimize</q-tooltip>
          </q-btn>
        </div>
      </div>
      <q-banner
        v-if="publicPageData.public_note"
        class="q-mx-md q-mb-sm bg-grey-2 text-grey-8"
        rounded
        dense
      >
        <span v-text="publicPageData.public_note"></span>
      </q-banner>
      <div class="chat-container" ref="chatScroll">
        <div class="chat-messages q-pa-md">
          <q-chat-message
            v-for="message in chatData.messages"
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
        </div>
      </div>
      <q-separator></q-separator>
      <div class="chat-input q-pt-sm q-px-md q-pb-md">
        <q-banner
          v-if="isAfterHours && !authUser"
          class="q-mb-sm bg-grey-2 text-grey-8"
          rounded
          dense
        >
          <div
            class="text-subtitle2"
            v-text="$t('chat.outside_working_hours')"
          ></div>
          <div
            class="text-caption"
            v-text="$t('chat.outside_working_hours_hint')"
          ></div>
        </q-banner>
        <q-form @submit="sendMessage" class="row q-col-gutter-sm items-start">
          <q-input
            v-if="isAfterHours && !authUser"
            dense
            outlined
            type="email"
            v-model.trim="notificationForm.email"
            class="col-12"
            :label="$t('chat.email')"
            :hint="$t('chat.email_required')"
            :disable="sending"
          ></q-input>
          <q-input
            dense
            outlined
            v-model.trim="messageInput"
            class="col-12 col-sm"
            :placeholder="$t('chat.type_message')"
            :disable="sending"
            :maxlength="publicPageData.chars || null"
          ></q-input>
          <div class="col-12 col-sm-auto row items-center q-gutter-x-sm">
            <q-btn
              color="primary"
              unelevated
              icon="send"
              type="submit"
              :disable="!canSendMessage"
            ></q-btn>
            <q-btn
              v-if="publicPageData.tips"
              outline
              color="amber"
              icon="paid"
              @click="showTipDialog = true"
            >
              <q-tooltip>Send a tip</q-tooltip>
            </q-btn>
            <q-btn
              v-if="publicPageData.paid && publicPageData.lnurlp"
              outline
              color="primary"
              icon="account_balance_wallet"
              @click="openLnurlDialog"
            >
              <q-tooltip>Fund balance</q-tooltip>
            </q-btn>
          </div>
        </q-form>
        <div v-if="pendingAmount" class="text-caption text-grey q-mt-sm">
          Payment required (<span v-text="pendingAmount"></span> sats)
        </div>
        <div
          v-if="publicPageData.paid && publicPageData.lnurlp"
          class="text-caption text-grey q-mt-xs"
        >
          Balance: <span v-text="chatData.balance"></span> sats
        </div>
        <q-expansion-item
          v-if="
            !authUser &&
            notificationsEnabled &&
            (notifyEmailAvailable || notifyNostrAvailable)
          "
          dense
          icon="notifications"
          label="Get notified when we reply"
          class="q-mt-sm"
        >
          <div class="q-gutter-sm q-mt-sm">
            <q-input
              v-if="notifyEmailAvailable"
              dense
              outlined
              v-model.trim="notificationForm.email"
              label="Email"
            ></q-input>
            <q-input
              v-if="notifyNostrAvailable"
              dense
              outlined
              v-model.trim="notificationForm.nostr"
              label="Nostr identifier"
            ></q-input>
            <q-btn
              unelevated
              color="primary"
              label="Save"
              :loading="notificationForm.saving"
              @click="saveNotifications"
            ></q-btn>
          </div>
        </q-expansion-item>
      </div>
    </div>

    <q-dialog v-model="paymentDialog.show" persistent>
      <q-card class="q-pa-lg" style="width: 360px">
        <q-card-section>
          <div class="text-h6">
            Payment required
            <span class="text-subtitle2 text-grey q-ml-xs">
              (<span v-text="paymentDialog.amount"></span> sats)
            </span>
          </div>
          <div class="text-caption text-grey">Pay to send your message.</div>
        </q-card-section>
        <q-card-section class="q-pa-none q-mb-md">
          <lnbits-qrcode
            :show-buttons="false"
            :href="'lightning:' + paymentDialog.invoice"
            :value="'lightning:' + paymentDialog.invoice"
          ></lnbits-qrcode>
        </q-card-section>
        <q-card-section class="row items-center">
          <q-btn
            flat
            color="grey"
            label="Close"
            @click="closePaymentDialog"
          ></q-btn>
        </q-card-section>
      </q-card>
    </q-dialog>

    <q-dialog v-model="showTipDialog" position="top">
      <q-card class="q-pa-lg" style="width: 360px">
        <q-card-section>
          <div class="text-h6">Send a tip</div>
          <div class="text-caption text-grey">
            Choose an amount to tip the operator.
          </div>
        </q-card-section>
        <q-card-section>
          <q-input
            filled
            dense
            type="number"
            v-model.number="tipAmount"
            label="Amount (sats)"
          ></q-input>
        </q-card-section>
        <q-card-section class="row items-center">
          <q-btn
            unelevated
            color="amber"
            label="Create invoice"
            @click="sendTip"
            :disable="!tipAmount"
          ></q-btn>
          <q-space></q-space>
          <q-btn v-close-popup flat color="grey" label="Cancel"></q-btn>
        </q-card-section>
      </q-card>
    </q-dialog>

    <q-dialog v-model="lnurlDialog" position="top">
      <q-card class="q-pa-lg" style="width: 360px">
        <q-card-section>
          <div class="text-h6">Fund chat balance</div>
          <div class="text-caption text-grey">
            Scan with an LNURL compatible wallet.
          </div>
        </q-card-section>
        <q-card-section class="q-pa-none q-mb-md">
          <div class="chat-lnurl-no-buttons">
            <lnbits-qrcode-lnurl
              :url="lnurlPay"
              :nfc="true"
            ></lnbits-qrcode-lnurl>
          </div>
        </q-card-section>
        <q-card-section class="row items-center">
          <q-btn
            flat
            color="grey"
            label="Close"
            @click="lnurlDialog = false"
          ></q-btn>
        </q-card-section>
      </q-card>
    </q-dialog>
  </div>
</template>

<style>
html,
body {
  overflow: hidden;
}

.q-header {
  display: none !important;
}

.q-page-container {
  padding-top: 0 !important;
}

.q-page {
  padding-top: 0 !important;
}

.chat-embed {
  height: 100vh;
  overflow: hidden;
}

.chat-embed-body {
  display: flex;
  flex-direction: column;
  height: 100%;
}

.chat-embed-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}

.chat-embed-actions {
  display: flex;
  gap: 8px;
}

.chat-container {
  flex: 1 1 auto;
  overflow-y: auto;
  min-height: 0;
}

.chat-input {
  flex: 0 0 auto;
  position: sticky;
  bottom: 0;
  background: var(--q-dark, #1d1f23);
}

.chat-embed-launcher-wrap {
  display: flex;
  justify-content: center;
  align-items: center;
  height: 56px;
  padding: 0;
}

.chat-embed-launcher {
  justify-content: center;
  background: rgba(0, 0, 0, 0.65);
  border-radius: 16px;
  padding: 6px 14px;
  color: white;
}

.chat-lnurl-no-buttons .qrcode__buttons {
  display: none;
}
</style>
