<template id="page-chat-instance-list">
  <div class="q-gutter-y-md">
    <q-card>
      <q-card-section class="row items-center">
        <div>
          <div class="text-h6">Chats</div>
          <div class="text-caption text-grey" v-if="category">
            <span v-text="category.name"></span>
            <span class="q-ml-xs">·</span>
            <span class="q-ml-xs" v-text="categoriesId"></span>
          </div>
        </div>
        <q-space></q-space>
        <q-btn-toggle
          v-model="viewMode"
          dense
          toggle-color="primary"
          :options="[
            {label: 'LIST', value: 'list'},
            {label: 'GRID', value: 'grid'}
          ]"
        ></q-btn-toggle>
      </q-card-section>
      <q-card-section class="row items-center q-col-gutter-md">
        <div class="col">
          <q-input
            dense
            filled
            v-model.trim="chatsTable.search"
            placeholder="Search"
          >
            <template v-slot:append>
              <q-icon name="search" />
            </template>
          </q-input>
        </div>
      </q-card-section>
    </q-card>

    <div v-if="viewMode === 'list'">
      <q-list bordered separator>
        <q-item
          v-for="chat in chatList"
          :key="chat.id"
          :to="chatLink(chat)"
          clickable
        >
          <q-item-section>
            <q-item-label v-text="chatTitle(chat)"></q-item-label>
            <q-item-label caption v-text="chatSubtitle(chat)"></q-item-label>
          </q-item-section>
          <q-item-section side>
            <div class="row items-center q-gutter-xs">
              <q-badge v-if="chat.unread" color="orange">new</q-badge>
              <q-badge v-if="chat.resolved" color="green">resolved</q-badge>
            </div>
            <div class="text-caption text-grey q-mt-xs">
              <span v-text="dateFromNow(chat.updated_at)"></span>
            </div>
          </q-item-section>
        </q-item>
      </q-list>
    </div>

    <div v-else class="row q-col-gutter-md">
      <div
        v-for="chat in chatList"
        :key="chat.id"
        class="col-12 col-sm-6 col-lg-4"
      >
        <q-card
          class="cursor-pointer"
          :class="chat.unread ? 'bg-orange-2 text-dark' : ''"
          @click="$router.push(chatLink(chat))"
        >
          <q-card-section>
            <div class="text-subtitle1" v-text="chatTitle(chat)"></div>
            <div class="text-caption" v-text="chatSubtitle(chat)"></div>
          </q-card-section>
          <q-card-section class="row items-center justify-between">
            <div class="row items-center q-gutter-xs">
              <q-badge v-if="chat.unread" color="orange">new</q-badge>
              <q-badge v-if="chat.resolved" color="green">resolved</q-badge>
            </div>
            <div class="text-caption text-grey">
              <span v-text="dateFromNow(chat.updated_at)"></span>
            </div>
          </q-card-section>
        </q-card>
      </div>
    </div>

    <div v-if="!chatList.length" class="text-caption text-grey">
      No chats yet.
    </div>

    <div class="row justify-center" v-if="chatPages > 1">
      <q-pagination
        v-model="chatsTable.pagination.page"
        :max="chatPages"
        @update:model-value="getChats"
      ></q-pagination>
    </div>
  </div>
</template>
