<!--/////////////////////////////////////////////////-->
<!--////////////////USER FACING PAGE/////////////////-->
<!--/////////////////////////////////////////////////-->

<template id="page-chat-public">
  <div class="row q-col-gutter-md" style="height: calc(100vh - 64px)">
    <div class="col-12 col-lg-8 column" style="height: 100%">
      <q-card class="column no-wrap" style="height: 100%">
        <q-card-section class="q-pa-md row items-center">
          <div>
            <div class="text-h6" v-text="publicPageData.name || 'Chat'"></div>
            <div class="text-caption text-grey">
              <span v-text="chatData.id"></span>
            </div>
          </div>
          <q-space></q-space>
          <q-badge v-if="chatData.resolved" color="green">resolved</q-badge>
          <q-btn
            v-if="authUser"
            flat
            dense
            icon="done"
            :color="chatData.resolved ? 'grey' : 'green'"
            @click="toggleResolved"
          >
            <q-tooltip>
              <span v-if="chatData.resolved">Reopen</span>
              <span v-else>Resolve</span>
            </q-tooltip>
          </q-btn>
        </q-card-section>

        <q-card-section
          class="col q-pa-md"
          style="min-height: 0; overflow-y: auto"
          ref="chatScroll"
          @scroll="onChatScroll"
        >
          <div class="column justify-end" style="min-height: 100%">
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
          <div v-if="!chatData.messages.length" class="text-caption text-grey">
            Start the conversation.
          </div>
        </q-card-section>

        <q-card-actions class="q-pa-md" align="stretch">
          <div class="col">
            <q-form @submit="sendMessage" class="row no-wrap items-center">
              <q-input
                dense
                outlined
                v-model.trim="messageInput"
                class="col"
                placeholder="Type a message..."
                :disable="sending"
                :maxlength="publicPageData.chars || null"
              />
              <div class="col-auto row no-wrap items-center q-gutter-x-sm">
                <q-btn
                  color="primary"
                  unelevated
                  icon="send"
                  type="submit"
                  :disable="!messageInput || sending"
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
              </div>
            </q-form>

            <div v-if="pendingAmount" class="text-caption text-grey q-mt-sm">
              Payment required (<span v-text="pendingAmount"></span> sats)
            </div>
          </div>
        </q-card-actions>
      </q-card>
    </div>

    <div class="col-12 col-lg-4 q-gutter-y-md">
      <q-card>
        <q-card-section>
          <div class="text-subtitle2">Participants</div>
          <div class="text-caption text-grey">
            <span v-text="chatData.participants.length"></span> /
            <span>5</span>
          </div>
        </q-card-section>
        <q-card-section class="q-pt-none">
          <q-chip
            v-for="participant in chatData.participants"
            :key="participant.id"
            :color="participantColor(participant.id)"
            text-color="black"
            class="q-mb-xs"
          >
            <span v-text="participant.name"></span>
          </q-chip>
        </q-card-section>
        <q-card-section v-if="authUser" class="q-pt-none">
          <div
            v-if="chatData.claimed_by_id"
            class="text-caption text-grey q-mb-xs"
          >
            Claimed by <span v-text="chatData.claimed_by_name"></span>
          </div>
          <q-btn
            outline
            color="primary"
            :label="
              isClaimedByMe
                ? 'Release'
                : chatData.claimed_by_name
                  ? 'Steal'
                  : 'Claim'
            "
            @click="toggleClaim"
          ></q-btn>
        </q-card-section>
        <q-card-section
          v-if="publicPageData.paid && publicPageData.lnurlp"
          class="q-pt-none"
        >
          <div class="text-caption text-grey">Balance</div>
          <div class="row items-center q-gutter-sm">
            <div class="text-subtitle2">
              <span v-text="chatData.balance"></span> sats
            </div>
            <div v-if="claimSplit > 0" class="text-caption text-grey">
              Claimer split: <span v-text="claimSplit"></span>%
            </div>
          </div>
        </q-card-section>
      </q-card>

      <q-card v-if="publicPageData.paid && publicPageData.lnurlp">
        <q-card-section>
          <div class="text-subtitle2">Fund chat balance</div>
          <div class="text-caption text-grey">
            Scan with an LNURL compatible wallet.
          </div>
        </q-card-section>
        <q-card-section class="q-pa-none q-mb-md">
          <lnbits-qrcode-lnurl
            v-if="lnurlPay"
            :url="lnurlPay"
            :nfc="true"
          ></lnbits-qrcode-lnurl>
          <div v-else class="text-caption text-grey q-pa-md">
            Loading LNURL...
          </div>
        </q-card-section>
      </q-card>
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
  </div>
</template>
