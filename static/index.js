window.PageChat = {
  template: '#page-chat',
  delimiters: ['${', '}'],
  data: function () {
    return {
      currencyOptions: ['sat'],
      categoriesFormDialog: {
        show: false,
        data: {
          name: null,
          wallet: null,
          paid: false,
          lnurlp: false,
          tips: false,
          chars: null,
          price_chars: null,
          denomination: 'sat',
          claim_split: 0,
          notify_telegram: null,
          notify_nostr: null,
          notify_email: null
        }
      },
      categoriesList: [],
      categoriesTable: {
        search: '',
        loading: false,
        columns: [
          {
            name: 'name',
            align: 'left',
            label: 'Name',
            field: 'name',
            sortable: true
          },
          {
            name: 'paid',
            align: 'left',
            label: 'Paid',
            field: 'paid',
            sortable: true
          },
          {
            name: 'tips',
            align: 'left',
            label: 'Tips',
            field: 'tips',
            sortable: true
          },
          {
            name: 'wallet',
            align: 'left',
            label: 'Wallet',
            field: 'wallet',
            sortable: true
          },
          {
            name: 'updated_at',
            align: 'left',
            label: 'Updated At',
            field: 'updated_at',
            sortable: true
          },
          {name: 'id', align: 'left', label: 'ID', field: 'id', sortable: true}
        ],
        pagination: {
          sortBy: 'updated_at',
          rowsPerPage: 10,
          page: 1,
          descending: true,
          rowsNumber: 10
        }
      },
      chatViewMode: 'list',
      chatFilters: {
        categories: {label: 'All Categories', value: ''}
      },
      chatsTable: {
        search: '',
        loading: false,
        pagination: {
          sortBy: 'updated_at',
          rowsPerPage: 12,
          page: 1,
          descending: true,
          rowsNumber: 0
        }
      },
      chatList: [],
      selectedChat: null,
      chatSocket: null,
      messageInput: '',
      sending: false,
      adminParticipantId: '',
      poller: null,
      autoScroll: true,
      embedDialog: {
        show: false,
        iframe: ''
      }
    }
  },
  computed: {
    chatPages() {
      const rows = this.chatsTable.pagination.rowsNumber || 0
      const perPage = this.chatsTable.pagination.rowsPerPage || 1
      return Math.max(1, Math.ceil(rows / perPage))
    }
  },
  watch: {
    'categoriesTable.search': {
      handler() {
        this.getCategories()
      }
    },
    'categoriesFormDialog.data.paid': {
      handler(paid) {
        if (!paid && this.categoriesFormDialog.data.lnurlp) {
          this.categoriesFormDialog.data.lnurlp = false
        }
        if (!paid && this.categoriesFormDialog.data.claim_split) {
          this.categoriesFormDialog.data.claim_split = 0
        }
      }
    },
    'chatsTable.search': {
      handler() {
        this.getChats()
      }
    },
    'chatFilters.categories.value': {
      handler() {
        this.getChats()
      }
    },
    'selectedChat.messages': {
      async handler() {
        if (!this.autoScroll) return
        await this.scrollToBottomSmooth()
      },
      deep: true
    }
  },
  methods: {
    getChatScrollEl() {
      const ref = this.$refs.adminChatScroll
      if (!ref) return null
      return ref.$el ? ref.$el : ref
    },

    onChatScroll() {
      const el = this.getChatScrollEl()
      if (!el) return
      if (el.scrollHeight <= el.clientHeight + 8) {
        this.autoScroll = true
        return
      }
      this.autoScroll =
        el.scrollTop + el.clientHeight >= el.scrollHeight - 8
    },

    async scrollToBottomSmooth() {
      const el = this.getChatScrollEl()
      if (!el) return
      await this.$nextTick()
      requestAnimationFrame(() => {
        const el2 = this.getChatScrollEl()
        if (!el2) return
        el2.scrollTop = el2.scrollHeight
      })
      requestAnimationFrame(() => {
        const el3 = this.getChatScrollEl()
        if (!el3) return
        el3.scrollTop = el3.scrollHeight
      })
    },

    async showNewCategoriesForm() {
      this.categoriesFormDialog.data = {
        name: null,
        wallet: this.g.user.wallets[0]?.id || null,
        paid: false,
        lnurlp: false,
        tips: false,
        chars: null,
        price_chars: null,
        denomination: 'sat',
        claim_split: 0,
        notify_telegram: null,
        notify_nostr: null,
        notify_email: null
      }
      this.categoriesFormDialog.show = true
    },
    async showEditCategoriesForm(data) {
      this.categoriesFormDialog.data = {...data}
      this.categoriesFormDialog.show = true
    },
    async saveCategories() {
      try {
        const data = {extra: {}, ...this.categoriesFormDialog.data}
        if (!data.paid) {
          data.lnurlp = false
          data.claim_split = 0
        }
        const method = data.id ? 'PUT' : 'POST'
        const entry = data.id ? `/${data.id}` : ''
        await LNbits.api.request(
          method,
          '/chat/api/v1/categories' + entry,
          null,
          data
        )
        this.getCategories()
        this.categoriesFormDialog.show = false
      } catch (error) {
        LNbits.utils.notifyApiError(error)
      }
    },

    async getCategories(props) {
      try {
        this.categoriesTable.loading = true
        const params = LNbits.utils.prepareFilterQuery(
          this.categoriesTable,
          props
        )
        const {data} = await LNbits.api.request(
          'GET',
          `/chat/api/v1/categories/paginated?${params}`,
          null
        )
        this.categoriesList = data.data
        this.categoriesTable.pagination.rowsNumber = data.total
      } catch (error) {
        LNbits.utils.notifyApiError(error)
      } finally {
        this.categoriesTable.loading = false
      }
    },
    async deleteCategories(categoriesId) {
      await LNbits.utils
        .confirmDialog('Are you sure you want to delete this category?')
        .onOk(async () => {
          try {
            await LNbits.api.request(
              'DELETE',
              '/chat/api/v1/categories/' + categoriesId,
              null
            )
            await this.getCategories()
          } catch (error) {
            LNbits.utils.notifyApiError(error)
          }
        })
    },

    async getChats(props) {
      try {
        this.chatsTable.loading = true
        let params = LNbits.utils.prepareFilterQuery(this.chatsTable, props)
        const categoriesId = this.chatFilters.categories.value
        if (categoriesId) {
          params += `&categories_id=${categoriesId}`
        }
        const {data} = await LNbits.api.request(
          'GET',
          `/chat/api/v1/chats/paginated?${params}`,
          null
        )
        this.chatList = data.data
        this.chatsTable.pagination.rowsNumber = data.total
      } catch (error) {
        LNbits.utils.notifyApiError(error)
      } finally {
        this.chatsTable.loading = false
      }
    },

    async selectChat(chat) {
      try {
        const {data} = await LNbits.api.request(
          'GET',
          `/chat/api/v1/chats/${chat.id}`,
          null
        )
        this.selectedChat = data
        this.autoScroll = true
        await this.markChatSeen(chat.id)
        this.connectChatWebsocket(chat.id)
      } catch (error) {
        LNbits.utils.notifyApiError(error)
      }
    },

    async onSendMessage(messageText) {
      if (!messageText || !this.selectedChat || this.sending) return
      this.sending = true
      try {
        const payload = {
          sender_id: `admin-${this.g.user.id}`,
          sender_name: this.g.user.username || 'support',
          sender_role: 'admin',
          message: messageText
        }
        await LNbits.api.request(
          'POST',
          `/chat/api/v1/chats/${this.selectedChat.id}/messages`,
          null,
          payload
        )
      } catch (error) {
        LNbits.utils.notifyApiError(error)
      } finally {
        this.sending = false
      }
    },

    async sendMessage() {
      const messageText = this.messageInput.trim()
      if (!messageText) return
      this.messageInput = ''
      await this.onSendMessage(messageText)
    },

    isSent(message) {
      return message.sender_role === 'admin'
    },

    messageColor(message) {
      const palette = [
        'blue-1',
        'teal-1',
        'orange-1',
        'purple-1',
        'cyan-1',
        'lime-1'
      ]
      const hash = this.hashString(message.sender_id || message.sender_name)
      return palette[hash % palette.length]
    },

    hashString(value) {
      let hash = 0
      const str = value || ''
      for (let i = 0; i < str.length; i++) {
        hash = (hash << 5) - hash + str.charCodeAt(i)
        hash |= 0
      }
      return Math.abs(hash)
    },

    scrollToBottom() {
      const el = this.getChatScrollEl()
      if (!el) return
      el.scrollTop = el.scrollHeight
    },

    async toggleResolved() {
      if (!this.selectedChat) return
      try {
        const {data} = await LNbits.api.request(
          'POST',
          `/chat/api/v1/chats/${this.selectedChat.id}/resolve`,
          null,
          {resolved: !this.selectedChat.resolved}
        )
        this.selectedChat = data
        this.updateChatListEntry(data)
      } catch (error) {
        LNbits.utils.notifyApiError(error)
      }
    },

    async markChatSeen(chatId) {
      try {
        const {data} = await LNbits.api.request(
          'POST',
          `/chat/api/v1/chats/${chatId}/seen`,
          null
        )
        this.updateChatListEntry(data)
      } catch (error) {
        LNbits.utils.notifyApiError(error)
      }
    },

    connectChatWebsocket(chatId) {
      if (this.chatSocket) {
        this.chatSocket.close()
      }
      const url = new URL(window.location)
      url.protocol = url.protocol === 'https:' ? 'wss:' : 'ws:'
      url.pathname = `/api/v1/ws/chat:${chatId}`
      const ws = new WebSocket(url)
      ws.addEventListener('message', ({data}) => {
        try {
          const payload = JSON.parse(data)
          if (payload.type === 'message' && payload.message) {
            const message = payload.message
            if (!this.selectedChat || this.selectedChat.id !== chatId) {
              this.getChats()
              return
            }
            const exists = this.selectedChat.messages.some(
              m => m.id === message.id
            )
            if (!exists) {
              this.selectedChat.messages.push(message)
              this.updateChatListEntry(this.selectedChat)
              this.markChatSeen(chatId)
            }
          }
          if (payload.type === 'resolved' && this.selectedChat) {
            this.selectedChat.resolved = payload.resolved
            this.updateChatListEntry(this.selectedChat)
          }
        } catch (err) {
          console.warn('Chat websocket message failed', err)
        }
      })
      this.chatSocket = ws
    },

    updateChatListEntry(chat) {
      const index = this.chatList.findIndex(item => item.id === chat.id)
      if (index >= 0) {
        this.chatList.splice(index, 1, chat)
      }
    },

    chatTitle(chat) {
      const name = this.categoryName(chat.categories_id)
      return name ? `${name} · ${chat.id.slice(0, 6)}` : chat.id
    },

    chatSubtitle(chat) {
      const participants = chat.participants?.length || 0
      const last = chat.last_message_at
        ? this.dateFromNow(chat.last_message_at)
        : 'No messages yet'
      return `${participants} participants · ${last}`
    },

    categoryName(categoryId) {
      const category = this.categoriesList.find(item => item.id === categoryId)
      return category ? category.name : ''
    },

    publicChatLink(chat) {
      return `${window.location.origin}/chat/${chat.categories_id}/${chat.id}`
    },

    showEmbedDialog(category) {
      const src = `${window.location.origin}/chat/embed/${category.id}?min=1&label=${encodeURIComponent('Chat to us')}`
      this.embedDialog.iframe = `<div id="lnbits-chat-embed-root">
  <iframe id="lnbits-chat-embed-iframe" src="${src}" style="position:fixed;right:24px;bottom:24px;width:360px;height:56px;border:0;border-radius:12px;box-shadow:0 16px 40px rgba(0,0,0,.35);z-index:9999;transition:height .2s ease;overflow:hidden;"></iframe>
</div>
<script>
  (function() {
    var iframe = document.getElementById('lnbits-chat-embed-iframe');
    if (!iframe) return;
    var minHeight = 56;
    var maxHeight = 520;
    window.addEventListener('message', function(event) {
      if (!event.data || event.data.source !== 'lnbits-chat-embed') return;
      iframe.style.height = event.data.open ? maxHeight + 'px' : minHeight + 'px';
    });
  })();
</script>`
      this.embedDialog.show = true
    },

    copyEmbed() {
      this.copyText(this.embedDialog.iframe)
      this.$q.notify({type: 'positive', message: 'Embed code copied'})
    },

    copyPublicCategoryUrl(category) {
      const url = `${window.location.origin}/chat/${category.id}`
      this.copyText(url)
      this.$q.notify({type: 'positive', message: 'Public URL copied'})
    },

    dateFromNow(date) {
      return moment(date).fromNow()
    },
    async fetchCurrencies() {
      try {
        const response = await LNbits.api.request('GET', '/api/v1/currencies')
        this.currencyOptions = ['sat', ...response.data]
      } catch (error) {
        LNbits.utils.notifyApiError(error)
      }
    },

    startPolling() {
      if (this.poller) {
        clearInterval(this.poller)
      }
      this.poller = setInterval(() => {
        this.getChats()
      }, 8000)
    }
  },
  async created() {
    this.adminParticipantId = `admin-${this.g.user.id}`
    await this.fetchCurrencies()
    await this.getCategories()
    await this.getChats()
    this.startPolling()
  },
  beforeUnmount() {
    if (this.chatSocket) {
      this.chatSocket.close()
    }
    if (this.poller) {
      clearInterval(this.poller)
    }
  }
}
