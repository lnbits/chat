<template id="page-chat">
  <div class="row q-col-gutter-md">
    <div class="col-12 col-md-8 q-gutter-y-md">
      <q-card>
        <q-card-section class="row items-center">
          <div class="text-h6">Categories</div>
          <q-space></q-space>
          <q-btn
            @click="showNewCategoriesForm()"
            unelevated
            color="primary"
            icon="add"
            label="New"
          ></q-btn>
        </q-card-section>
        <q-separator></q-separator>
        <q-card-section class="q-pt-sm">
          <q-table
            dense
            flat
            :rows="categoriesList"
            row-key="id"
            :columns="categoriesTable.columns"
            v-model:pagination="categoriesTable.pagination"
            :loading="categoriesTable.loading"
            @request="getCategories"
          >
            <template v-slot:body="props">
              <q-tr :props="props">
                <q-td auto-width>
                  <q-btn
                    flat
                    dense
                    size="xs"
                    icon="launch"
                    color="primary"
                    type="a"
                    :href="'/chat/' + props.row.id"
                    target="_blank"
                    class="q-mr-sm"
                    ><q-tooltip>Open public page</q-tooltip></q-btn
                  >
                  <q-btn
                    flat
                    dense
                    size="xs"
                    icon="forum"
                    color="primary"
                    type="a"
                    :href="'/chat/chats/' + props.row.id"
                    target="_blank"
                    class="q-mr-sm"
                  >
                    <q-tooltip>Open chats list</q-tooltip>
                  </q-btn>
                  <q-btn
                    flat
                    dense
                    size="xs"
                    icon="content_copy"
                    color="grey"
                    class="q-mr-sm"
                    @click.stop="copyPublicCategoryUrl(props.row)"
                  >
                    <q-tooltip>Copy public URL</q-tooltip>
                  </q-btn>
                  <q-btn
                    flat
                    dense
                    size="xs"
                    icon="code"
                    color="grey"
                    class="q-mr-sm"
                    @click="showEmbedDialog(props.row)"
                  >
                    <q-tooltip>Embed widget</q-tooltip>
                  </q-btn>
                  <q-btn
                    flat
                    dense
                    size="xs"
                    @click="showEditCategoriesForm(props.row)"
                    icon="edit"
                    color="light-blue"
                    class="q-mr-sm"
                  >
                    <q-tooltip> Edit </q-tooltip>
                  </q-btn>
                  <q-btn
                    flat
                    dense
                    size="xs"
                    @click="deleteCategories(props.row.id)"
                    icon="cancel"
                    color="pink"
                    class="q-mr-sm"
                  >
                    <q-tooltip> Delete </q-tooltip>
                  </q-btn>
                </q-td>
                <q-td v-for="col in props.cols" :key="col.name" :props="props">
                  <div v-if="col.field == 'updated_at'">
                    <span v-text="dateFromNow(col.value)"> </span>
                  </div>
                  <div v-else>${ col.value }</div>
                </q-td>
              </q-tr>
            </template>
          </q-table>
        </q-card-section>
      </q-card>

      <q-card>
        <q-card-section class="row items-center">
          <div class="text-h6">Chats</div>
          <q-space></q-space>
          <q-btn-toggle
            v-model="chatViewMode"
            dense
            toggle-color="primary"
            :options="[
              {label: 'List', value: 'list'},
              {label: 'Grid', value: 'grid'}
            ]"
          ></q-btn-toggle>
        </q-card-section>
        <q-card-section class="q-pt-none">
          <div class="row q-col-gutter-sm items-center">
            <div class="col">
              <q-input dense filled label="Search" v-model="chatsTable.search">
                <template v-slot:append>
                  <q-icon name="search"></q-icon>
                </template>
              </q-input>
            </div>
            <div class="col-auto">
              <q-select
                dense
                filled
                v-model="chatFilters.categories"
                :options="[
                  {label: 'All Categories', value: ''},
                  ...categoriesList.map(x => ({
                    label: x.name || x.id,
                    value: x.id
                  }))
                ]"
                label="Category"
              ></q-select>
            </div>
          </div>
        </q-card-section>
        <q-separator></q-separator>
        <q-card-section class="q-pt-none">
          <div v-if="chatViewMode === 'list'">
            <q-list separator>
              <q-item
                v-for="chat in chatList"
                :key="chat.id"
                clickable
                @click="selectChat(chat)"
                :active="selectedChat && selectedChat.id === chat.id"
                active-class="bg-grey-2"
              >
                <q-item-section>
                  <q-item-label class="ellipsis">
                    <span v-text="chatTitle(chat)"></span>
                  </q-item-label>
                  <q-item-label caption>
                    <span v-text="chatSubtitle(chat)"></span>
                  </q-item-label>
                </q-item-section>
                <q-item-section side>
                  <q-badge
                    v-if="chat.unread"
                    color="orange"
                    label="new"
                  ></q-badge>
                  <q-badge
                    v-if="chat.resolved"
                    color="green"
                    label="resolved"
                    class="q-mt-xs"
                  ></q-badge>
                </q-item-section>
              </q-item>
            </q-list>
          </div>
          <div v-else class="row q-col-gutter-sm">
            <div
              class="col-12 col-sm-6"
              v-for="chat in chatList"
              :key="chat.id"
            >
              <q-card
                class="cursor-pointer"
                :class="chat.unread ? 'bg-orange-2 text-dark' : ''"
                @click="selectChat(chat)"
              >
                <q-card-section>
                  <div class="text-subtitle1" v-text="chatTitle(chat)"></div>
                  <div
                    class="text-caption"
                    :class="chat.unread ? 'text-grey-8' : ''"
                    v-text="chatSubtitle(chat)"
                  ></div>
                </q-card-section>
                <q-card-section class="row items-center q-pt-none">
                  <q-badge v-if="chat.unread" color="orange">new</q-badge>
                  <q-badge v-if="chat.resolved" color="green" class="q-ml-sm"
                    >resolved</q-badge
                  >
                  <q-space></q-space>
                  <span
                    class="text-caption"
                    v-text="dateFromNow(chat.updated_at)"
                  ></span>
                </q-card-section>
              </q-card>
            </div>
          </div>
          <div class="row justify-center q-mt-sm">
            <q-pagination
              v-model="chatsTable.pagination.page"
              :max="chatPages"
              :max-pages="5"
              size="sm"
              @update:model-value="getChats"
            ></q-pagination>
          </div>
        </q-card-section>
      </q-card>
    </div>

    <div
      class="col-12 col-md-4 q-gutter-y-md column"
      style="height: calc(100vh - 64px)"
    >
      <q-card v-if="selectedChat" class="column no-wrap" style="height: 100%">
        <q-card-section class="row items-center">
          <div>
            <div class="text-h6" v-text="chatTitle(selectedChat)"></div>
            <div class="text-caption">
              <span v-text="selectedChat.id"></span>
            </div>
          </div>
          <q-space></q-space>
          <q-badge v-if="selectedChat.resolved" color="green">resolved</q-badge>
          <q-btn
            flat
            dense
            icon="done"
            :color="selectedChat.resolved ? 'grey' : 'green'"
            @click="toggleResolved()"
          >
            <q-tooltip>
              <span v-if="selectedChat.resolved">Reopen</span>
              <span v-else>Resolve</span>
            </q-tooltip>
          </q-btn>
          <q-btn
            flat
            dense
            icon="open_in_new"
            color="primary"
            :href="publicChatLink(selectedChat)"
            target="_blank"
          >
            <q-tooltip>Open public chat</q-tooltip>
          </q-btn>
        </q-card-section>
        <q-separator></q-separator>
        <q-card-section
          class="col q-pa-md"
          style="min-height: 0; overflow-y: auto"
          ref="adminChatScroll"
          @scroll="onChatScroll"
        >
          <div class="column justify-end" style="min-height: 100%">
            <q-chat-message
              v-for="message in selectedChat.messages"
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
              <div v-else>
                <span v-text="message.message"></span>
                <q-icon
                  v-if="publicHasSeenMessage(message)"
                  name="done_all"
                  color="primary"
                  size="16px"
                  class="q-ml-xs"
                >
                  <q-tooltip>Seen by public user</q-tooltip>
                </q-icon>
              </div>
            </q-chat-message>
          </div>
          <div
            v-if="!selectedChat.messages.length"
            class="text-caption text-grey"
          >
            Start the conversation.
          </div>
        </q-card-section>
        <q-separator></q-separator>
        <q-card-actions class="q-pa-md" align="stretch">
          <div class="col">
            <q-form @submit="sendMessage" class="row items-center">
              <q-input
                dense
                outlined
                v-model.trim="messageInput"
                class="col"
                placeholder="Type a reply..."
                :disable="sending"
              ></q-input>
              <q-btn
                class="q-ml-sm"
                color="primary"
                unelevated
                icon="send"
                type="submit"
                :disable="!messageInput || sending"
              ></q-btn>
            </q-form>
          </div>
        </q-card-actions>
      </q-card>

      <q-card v-else>
        <q-card-section>
          <div class="text-h6">Select a chat</div>
          <div class="text-caption text-grey">
            Choose a chat from the list to start responding.
          </div>
        </q-card-section>
      </q-card>
    </div>

    <q-dialog v-model="categoriesFormDialog.show" position="top">
      <q-card
        v-if="categoriesFormDialog.show"
        class="q-pa-lg q-pt-md lnbits__dialog-card q-col-gutter-md"
      >
        <span class="text-h5">Categories</span>

        <q-input
          filled
          dense
          v-model.trim="categoriesFormDialog.data.name"
          label="Name"
          hint=" "
        ></q-input>

        <q-select
          filled
          dense
          emit-value
          v-model="categoriesFormDialog.data.wallet"
          :options="g.user.walletOptions"
          label="Wallet"
          hint="Wallet to receive payments"
        ></q-select>

        <div class="row items-center q-col-gutter-md q-mt-xs">
          <q-checkbox
            class="col-auto"
            v-model="categoriesFormDialog.data.paid"
            label="Paid"
            hint=" (optional)"
          ></q-checkbox>
          <q-checkbox
            class="col-auto"
            v-model="categoriesFormDialog.data.tips"
            label="Allow tips"
            hint=" (optional)"
          ></q-checkbox>
        </div>

        <q-expansion-item
          v-if="categoriesFormDialog.data.paid"
          icon="settings"
          label="Advanced paid options"
          dense
          class="q-mt-xs"
        >
          <div class="row items-center q-col-gutter-md q-mt-sm">
            <q-checkbox
              class="col-auto"
              v-model="categoriesFormDialog.data.lnurlp"
              label="LNURLP"
            >
              <q-tooltip anchor="bottom middle" self="top middle">
                (instead as payg, create an lnurlp users can fund)
              </q-tooltip>
            </q-checkbox>
            <q-input
              class="col"
              filled
              dense
              type="number"
              v-model.number="categoriesFormDialog.data.claim_split"
              label="% split with claimer"
              min="0"
              max="90"
              step="0.1"
            ></q-input>
          </div>
        </q-expansion-item>

        <q-input
          filled
          dense
          v-model.trim="categoriesFormDialog.data.chars"
          label="Character count max"
          hint="Max amount of characters allowed in messages"
          type="number"
        ></q-input>

        <q-input
          filled
          dense
          v-model.trim="categoriesFormDialog.data.price_chars"
          label="Price per character"
          hint="Sat fractions allowed"
          type="number"
        ></q-input>

        <q-select
          filled
          dense
          v-model="categoriesFormDialog.data.denomination"
          label="Denomination"
          hint="(optional)"
          :options="currencyOptions"
        ></q-select>

        <q-input
          filled
          dense
          type="textarea"
          autogrow
          v-model.trim="categoriesFormDialog.data.public_note"
          label="Opening note"
          hint="Shown when the chat opens (optional)"
        ></q-input>

        <q-expansion-item
          icon="schedule"
          :label="$t('chat.working_hours')"
          dense
          class="q-mt-sm"
        >
          <q-toggle
            v-model="categoriesFormDialog.data.schedule_enabled"
            color="primary"
            :label="$t('chat.enable_working_hours')"
          ></q-toggle>
          <q-select
            filled
            dense
            use-input
            hide-selected
            fill-input
            input-debounce="0"
            emit-value
            map-options
            v-model="categoriesFormDialog.data.schedule_timezone"
            :options="filteredTimezoneOptions"
            :label="$t('chat.timezone')"
            :hint="$t('chat.timezone_hint')"
            @filter="filterTimezones"
          ></q-select>
          <q-select
            filled
            dense
            multiple
            emit-value
            map-options
            v-model="categoriesFormDialog.data.schedule_days"
            :options="scheduleDayOptions"
            :label="$t('chat.working_days')"
          ></q-select>
          <div class="row q-col-gutter-md">
            <q-input
              class="col"
              filled
              dense
              type="time"
              v-model="categoriesFormDialog.data.schedule_start"
              :label="$t('chat.start_time')"
            ></q-input>
            <q-input
              class="col"
              filled
              dense
              type="time"
              v-model="categoriesFormDialog.data.schedule_end"
              :label="$t('chat.end_time')"
            ></q-input>
          </div>
        </q-expansion-item>

        <q-toggle
          v-model="categoriesFormDialog.data.guest_notifications"
          label="Allow guest reply notifications (a user will be notified when you reply)"
          color="primary"
        ></q-toggle>

        <q-expansion-item
          icon="notifications"
          label="Get notified on new chats"
          dense
          class="q-mt-sm"
        >
          <q-input
            filled
            dense
            v-model.trim="categoriesFormDialog.data.notify_telegram"
            label="Telegram Chat ID"
            hint="Optional notification target"
          ></q-input>

          <q-input
            filled
            dense
            v-model.trim="categoriesFormDialog.data.notify_nostr"
            label="Nostr identifier (npub or nip05)"
            hint="Optional notification target"
          ></q-input>

          <q-input
            filled
            dense
            v-model.trim="categoriesFormDialog.data.notify_email"
            label="Email address (comma separated)"
            hint="Optional notification target"
          ></q-input>
        </q-expansion-item>

        <q-expansion-item
          icon="mail"
          :label="$t('chat.email_templates')"
          dense
          class="q-mt-sm"
        >
          <div
            class="text-caption text-grey q-mt-sm"
            v-text="$t('chat.placeholders')"
          ></div>
          <q-input
            filled
            dense
            v-model.trim="categoriesFormDialog.data.admin_after_hours_subject"
            :label="
              $t('chat.admin_after_hours_email') + ' - ' + $t('chat.subject')
            "
          ></q-input>
          <q-input
            filled
            dense
            type="textarea"
            autogrow
            v-model="categoriesFormDialog.data.admin_after_hours_body"
            :label="
              $t('chat.admin_after_hours_email') + ' - ' + $t('chat.message')
            "
          ></q-input>
          <q-input
            filled
            dense
            v-model.trim="categoriesFormDialog.data.user_new_message_subject"
            :label="
              $t('chat.user_new_message_email') + ' - ' + $t('chat.subject')
            "
          ></q-input>
          <q-input
            filled
            dense
            type="textarea"
            autogrow
            v-model="categoriesFormDialog.data.user_new_message_body"
            :label="
              $t('chat.user_new_message_email') + ' - ' + $t('chat.message')
            "
          ></q-input>
        </q-expansion-item>

        <div class="row q-mt-lg">
          <q-btn @click="saveCategories" unelevated color="primary">
            <span v-if="categoriesFormDialog.data.id">Update</span>
            <span v-else>Create</span>
          </q-btn>
          <q-btn v-close-popup flat color="grey" class="q-ml-auto"
            >Cancel</q-btn
          >
        </div>
      </q-card>
    </q-dialog>

    <q-dialog v-model="embedDialog.show" position="top">
      <q-card class="q-pa-lg" style="width: 520px">
        <q-card-section>
          <div class="text-h6">Embed chat widget</div>
          <div class="text-caption text-grey">
            Paste this iframe into your site.
          </div>
        </q-card-section>
        <q-card-section>
          <q-input
            filled
            type="textarea"
            rows="4"
            v-model.trim="embedDialog.iframe"
            label="Iframe snippet"
          ></q-input>
        </q-card-section>
        <q-card-section class="row items-center">
          <q-btn
            unelevated
            color="primary"
            icon="content_copy"
            @click="copyEmbed"
            >Copy</q-btn
          >
          <q-space></q-space>
          <q-btn v-close-popup flat color="grey">Close</q-btn>
        </q-card-section>
      </q-card>
    </q-dialog>
  </div>
</template>
