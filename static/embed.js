window.PageChatEmbed = {
  template: '#page-chat-embed',
  data: function () {
    return {
      categoriesId: '',
      chatId: '',
      participantId: '',
      participantName: '',
      messageInput: '',
      chatData: {
        id: '',
        participants: [],
        messages: [],
        resolved: false,
        balance: 0,
        claimed_by_id: null,
        claimed_by_name: null
      },
      publicPageData: {},
      sending: false,
      paymentDialog: {
        show: false,
        invoice: '',
        hash: '',
        amount: 0
      },
      pendingAmount: 0,
      showTipDialog: false,
      tipAmount: null,
      chatSocket: null,
      balanceSocket: null,
      isMinimized: false,
      launcherText: 'Chat to us',
      lnurlPay: '',
      lnurlDialog: false,
      authUser: null,
      notificationForm: {
        email: '',
        nostr: '',
        saving: false
      }
    }
  },
  watch: {
    'chatData.messages': {
      handler() {
        this.$nextTick(() => this.scrollToBottom())
      },
      deep: true
    }
  },
  computed: {
    publicChatLink() {
      if (!this.categoriesId || !this.chatId) return ''
      return `${window.location.origin}/chat/${this.categoriesId}/${this.chatId}`
    },
    isClaimedByMe() {
      if (!this.authUser?.username) return false
      return this.chatData.claimed_by_name === this.authUser.username
    },
    notificationsEnabled() {
      return !!this.publicPageData?.guest_notifications
    },
    notifyEmailAvailable() {
      return (
        this.notificationsEnabled &&
        !!this.publicPageData?.notify_email_available
      )
    },
    notifyNostrAvailable() {
      return (
        this.notificationsEnabled &&
        !!this.publicPageData?.notify_nostr_available
      )
    },
    isAfterHours() {
      return (
        !!this.publicPageData?.schedule_enabled &&
        !this.publicPageData?.schedule_available
      )
    },
    canSendMessage() {
      if (!this.messageInput || this.sending) return false
      if (this.isAfterHours && !this.authUser && !this.notificationForm.email)
        return false
      return true
    }
  },
  methods: {
    toggleMinimize() {
      this.isMinimized = !this.isMinimized
      this.notifyParent()
      if (!this.isMinimized) {
        this.markPublicSeen()
      }
    },

    notifyParent() {
      if (window.parent && window.parent !== window) {
        window.parent.postMessage(
          {
            source: 'lnbits-chat-embed',
            open: !this.isMinimized,
            url: window.location.href
          },
          '*'
        )
      }
    },

    async fetchPublicData() {
      try {
        const {data} = await LNbits.api.request(
          'GET',
          `/chat/api/v1/categories/${this.categoriesId}/public`
        )
        this.publicPageData = data || {}
      } catch (error) {
        console.warn(error)
        LNbits.utils.notifyApiError(error)
      }
    },

    async ensureParticipant() {
      const storageKey = `lnbits.chat.participant.${this.categoriesId}`
      const existing = this.$q.localStorage.getItem(storageKey)
      if (existing) {
        this.participantId = existing
      } else {
        this.participantId = `guest-${Math.random().toString(36).slice(2, 10)}`
        this.$q.localStorage.set(storageKey, this.participantId)
      }

      try {
        const res = await LNbits.api.getAuthUser()
        const user = res.data
        if (user?.username) {
          this.participantName = user.username
        } else if (user) {
          this.participantName = 'anon'
        }
        if (user?.id) {
          this.authUser = user
          if (user.username) {
            this.participantId = `user-${user.username}`
          }
        }
      } catch (_) {
        // ignore if not logged in
      }

      if (!this.participantName) {
        this.participantName = this.participantId
      }
    },

    async ensureChat() {
      const chatId =
        this.$route.params.chat ||
        this.$q.localStorage.getItem(this.chatStorageKey())
      if (chatId) {
        this.chatId = chatId
        try {
          await this.fetchChat()
          this.storeChatId()
          this.updateChatUrl()
          this.loadNotificationForm()
          return
        } catch (error) {
          this.clearStoredChat()
          console.warn(error)
        }
      }
      await this.createChat()
    },

    chatStorageKey() {
      return `lnbits.chat.embed.${this.categoriesId}.chat`
    },

    storeChatId() {
      if (this.chatId) {
        this.$q.localStorage.set(this.chatStorageKey(), this.chatId)
      }
    },

    clearStoredChat() {
      this.$q.localStorage.remove(this.chatStorageKey())
    },

    async createChat() {
      const {data} = await LNbits.api.request(
        'POST',
        `/chat/api/v1/chats/${this.categoriesId}/public`,
        null,
        {
          participant_id: this.participantId,
          participant_name: this.participantName
        }
      )
      this.chatId = data.id
      this.chatData = data
      this.storeChatId()
      this.updateChatUrl()
      this.loadNotificationForm()
    },

    async startNewChat() {
      this.clearStoredChat()
      this.chatId = ''
      this.messageInput = ''
      this.pendingAmount = 0
      this.closePaymentDialog()
      if (this.chatSocket) {
        this.chatSocket.close()
        this.chatSocket = null
      }
      if (this.balanceSocket) {
        this.balanceSocket.close()
        this.balanceSocket = null
      }
      await this.createChat()
      await this.fetchLnurl()
      this.connectChatWebsocket()
      this.connectBalanceWebsocket()
    },

    notificationStorageKey() {
      if (!this.chatId) return ''
      return `lnbits.chat.notifications.${this.chatId}`
    },

    loadNotificationForm() {
      const key = this.notificationStorageKey()
      if (!key) return
      const existing = this.$q.localStorage.getItem(key)
      if (existing && typeof existing === 'object') {
        this.notificationForm.email = existing.email || ''
        this.notificationForm.nostr = existing.nostr || ''
      }
    },

    async saveNotifications() {
      if (!this.chatId || !this.notificationsEnabled) return
      const payload = {}
      if (this.notifyEmailAvailable) {
        payload.email = this.notificationForm.email || ''
      }
      if (this.notifyNostrAvailable) {
        payload.nostr = this.notificationForm.nostr || ''
      }
      if (!Object.keys(payload).length) return

      this.notificationForm.saving = true
      try {
        await LNbits.api.request(
          'POST',
          `/chat/api/v1/chats/${this.categoriesId}/${this.chatId}/public/notifications`,
          null,
          payload
        )
        const key = this.notificationStorageKey()
        if (key) {
          this.$q.localStorage.set(key, {
            email: this.notificationForm.email || '',
            nostr: this.notificationForm.nostr || ''
          })
        }
        Quasar.Notify.create({
          type: 'positive',
          message: 'Notification preferences saved'
        })
      } catch (error) {
        LNbits.utils.notifyApiError(error)
      } finally {
        this.notificationForm.saving = false
      }
    },

    updateChatUrl() {
      this.storeChatId()
      const query = window.location.search || ''
      const target = `/chat/embed/${this.categoriesId}/${this.chatId}${query}`
      window.history.replaceState({}, '', target)
    },

    async fetchChat() {
      const {data} = await LNbits.api.request(
        'GET',
        `/chat/api/v1/chats/${this.categoriesId}/${this.chatId}/public`
      )
      this.chatData = data
      await this.markPublicSeen()
    },

    async markPublicSeen() {
      if (!this.chatId || document.hidden || this.isMinimized) return
      try {
        const {data} = await LNbits.api.request(
          'POST',
          `/chat/api/v1/chats/${this.categoriesId}/${this.chatId}/public/seen`,
          null
        )
        if (data?.public_last_seen_message_id) {
          this.chatData.public_last_seen_message_id =
            data.public_last_seen_message_id
        }
      } catch (error) {
        console.warn(error)
      }
    },

    async toggleClaim() {
      if (!this.authUser) return
      try {
        const {data} = await LNbits.api.request(
          'POST',
          `/chat/api/v1/chats/${this.categoriesId}/${this.chatId}/public/claim`,
          null
        )
        this.chatData = data
      } catch (error) {
        LNbits.utils.notifyApiError(error)
      }
    },

    async fetchLnurl() {
      if (!this.publicPageData?.paid || !this.publicPageData?.lnurlp) return
      try {
        const {data} = await LNbits.api.request(
          'GET',
          `/chat/api/v1/chats/${this.categoriesId}/${this.chatId}/lnurl`
        )
        this.lnurlPay = data.url || data.lnurl
      } catch (error) {
        console.warn(error)
      }
    },

    async refreshBalance() {
      if (!this.chatId) return
      try {
        const {data} = await LNbits.api.request(
          'GET',
          `/chat/api/v1/chats/${this.categoriesId}/${this.chatId}/public`
        )
        if (data && typeof data.balance !== 'undefined') {
          this.applyBalanceUpdate(data.balance)
        }
      } catch (error) {
        console.warn(error)
      }
    },

    applyBalanceUpdate(nextBalance) {
      const next = nextBalance || 0
      const prev = this.chatData.balance || 0
      this.chatData.balance = next
      if (this.lnurlDialog && next > prev) {
        this.lnurlDialog = false
        Quasar.Notify.create({
          type: 'positive',
          message: 'Balance funded'
        })
      }
    },

    async openLnurlDialog() {
      if (!this.lnurlPay) {
        await this.fetchLnurl()
      }
      if (!this.lnurlPay) {
        Quasar.Notify.create({
          type: 'negative',
          message: 'Unable to load LNURL.'
        })
        return
      }
      this.lnurlDialog = true
    },

    async onSendMessage(messageText) {
      if (!messageText || this.sending) return
      this.sending = true
      try {
        const payload = {
          sender_id: this.participantId,
          sender_name: this.participantName,
          sender_role: this.authUser ? 'admin' : 'public',
          message: messageText,
          notify_email:
            this.isAfterHours && !this.authUser
              ? this.notificationForm.email || ''
              : undefined
        }
        const {data} = await LNbits.api.request(
          'POST',
          `/chat/api/v1/chats/${this.categoriesId}/${this.chatId}/public/messages`,
          null,
          payload
        )
        this.updateChatUrl()
        if (data.pending && data.payment_request) {
          this.pendingAmount = data.amount || 0
          this.paymentDialog = {
            show: true,
            invoice: data.payment_request,
            hash: data.payment_hash,
            amount: data.amount || 0
          }
          await this.waitForPayment(data.payment_hash)
        }
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
      return message.sender_id === this.participantId
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
      const container = this.$refs.chatScroll
      if (!container) return
      container.scrollTop = container.scrollHeight
    },

    dateFromNow(date) {
      return moment(date).fromNow()
    },

    async sendTip() {
      if (!this.tipAmount) return
      try {
        const payload = {
          amount: this.tipAmount,
          sender_id: this.participantId,
          sender_name: this.participantName
        }
        const {data} = await LNbits.api.request(
          'POST',
          `/chat/api/v1/chats/${this.categoriesId}/${this.chatId}/public/tip`,
          null,
          payload
        )
        this.showTipDialog = false
        this.tipAmount = null
        if (data.payment_request) {
          this.paymentDialog = {
            show: true,
            invoice: data.payment_request,
            hash: data.payment_hash,
            amount: data.amount || 0
          }
          await this.waitForPayment(data.payment_hash)
        }
      } catch (error) {
        LNbits.utils.notifyApiError(error)
      }
    },

    async waitForPayment(paymentHash) {
      try {
        const url = new URL(window.location)
        url.protocol = url.protocol === 'https:' ? 'wss:' : 'ws:'
        url.pathname = `/api/v1/ws/${paymentHash}`
        const ws = new WebSocket(url)
        ws.addEventListener('message', async ({data}) => {
          const payment = JSON.parse(data)
          if (payment.pending === false) {
            this.pendingAmount = 0
            this.closePaymentDialog()
            Quasar.Notify.create({
              type: 'positive',
              message: 'Payment received'
            })
            ws.close()
          }
        })
      } catch (err) {
        console.warn(err)
        Quasar.Notify.create({
          type: 'negative',
          message: 'Error waiting for payment.'
        })
      }
    },

    closePaymentDialog() {
      this.paymentDialog.show = false
      this.paymentDialog.invoice = ''
      this.paymentDialog.hash = ''
      this.paymentDialog.amount = 0
    },

    connectChatWebsocket() {
      if (!this.chatId) return
      if (this.chatSocket) {
        this.chatSocket.close()
      }
      const url = new URL(window.location)
      url.protocol = url.protocol === 'https:' ? 'wss:' : 'ws:'
      url.pathname = `/api/v1/ws/chat:${this.chatId}`
      const ws = new WebSocket(url)
      ws.addEventListener('message', ({data}) => {
        try {
          const payload = JSON.parse(data)
          if (payload.type === 'message' && payload.message) {
            const message = payload.message
            const exists = this.chatData.messages.some(m => m.id === message.id)
            if (!exists) {
              this.chatData.messages.push(message)
              const participantExists = this.chatData.participants.some(
                p => p.id === message.sender_id
              )
              if (!participantExists) {
                this.chatData.participants.push({
                  id: message.sender_id,
                  name: message.sender_name,
                  role: message.sender_role
                })
              }
              if (message.sender_role === 'admin') {
                this.markPublicSeen()
              }
            }
          }
          if (payload.type === 'resolved') {
            this.chatData.resolved = payload.resolved
          }
          if (payload.type === 'balance') {
            this.applyBalanceUpdate(payload.balance)
          }
          if (payload.type === 'claim') {
            this.chatData.claimed_by_name = payload.claimed_by_name
          }
        } catch (err) {
          console.warn('Chat websocket message failed', err)
        }
      })
      this.chatSocket = ws
    },

    connectBalanceWebsocket() {
      if (!this.chatId) return
      if (this.balanceSocket) {
        this.balanceSocket.close()
      }
      const url = new URL(window.location)
      url.protocol = url.protocol === 'https:' ? 'wss:' : 'ws:'
      url.pathname = `/api/v1/ws/chatbalance:${this.chatId}`
      const ws = new WebSocket(url)
      ws.addEventListener('open', () => {
        this.refreshBalance()
      })
      ws.addEventListener('message', ({data}) => {
        try {
          const payload = JSON.parse(data)
          if (payload.type === 'balance') {
            this.applyBalanceUpdate(payload.balance)
          }
        } catch (err) {
          console.warn('Balance websocket message failed', err)
        }
      })
      this.balanceSocket = ws
    }
  },
  created: async function () {
    this.categoriesId = this.$route.params.id
    const params = new URLSearchParams(window.location.search)
    this.launcherText = params.get('label') || 'Chat to us'
    this.isMinimized = params.get('min') === '1'
    await this.fetchPublicData()
    await this.ensureParticipant()
    await this.ensureChat()
    await this.fetchLnurl()
    this.connectChatWebsocket()
    this.connectBalanceWebsocket()
    this.notifyParent()
  },
  mounted() {
    window.addEventListener('focus', this.markPublicSeen)
    document.addEventListener('visibilitychange', this.markPublicSeen)
  },
  beforeUnmount() {
    window.removeEventListener('focus', this.markPublicSeen)
    document.removeEventListener('visibilitychange', this.markPublicSeen)
    if (this.chatSocket) {
      this.chatSocket.close()
    }
    if (this.balanceSocket) {
      this.balanceSocket.close()
    }
  }
}

window.PageChatEmbedChat = window.PageChatEmbed
