window.PageChatPublic = {
  template: '#page-chat-public',
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
        resolved: false
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
      chatSocket: null
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
  methods: {
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
      } catch (_) {
        // ignore if not logged in
      }

      if (!this.participantName) {
        this.participantName = this.participantId
      }
    },

    async ensureChat() {
      const chatId = this.$route.params.chat
      if (chatId) {
        this.chatId = chatId
        await this.fetchChat()
        return
      }
      const payload = {
        participant_id: this.participantId,
        participant_name: this.participantName
      }
      const {data} = await LNbits.api.request(
        'POST',
        `/chat/api/v1/chats/${this.categoriesId}/public`,
        null,
        payload
      )
      this.chatId = data.id
      this.chatData = data
    },

    updateChatUrl() {
      if (this.$route?.params?.chat) return
      const target = `/chat/${this.categoriesId}/${this.chatId}`
      window.history.replaceState({}, '', target)
    },

    async fetchChat() {
      const {data} = await LNbits.api.request(
        'GET',
        `/chat/api/v1/chats/${this.categoriesId}/${this.chatId}/public`
      )
      this.chatData = data
    },

    async onSendMessage(messageText) {
      if (!messageText || this.sending) return
      this.sending = true
      try {
        const payload = {
          sender_id: this.participantId,
          sender_name: this.participantName,
          sender_role: 'public',
          message: messageText
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

    participantColor(value) {
      const palette = [
        'blue-2',
        'teal-2',
        'orange-2',
        'purple-2',
        'cyan-2',
        'lime-2'
      ]
      const hash = this.hashString(value)
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
            }
          }
          if (payload.type === 'resolved') {
            this.chatData.resolved = payload.resolved
          }
        } catch (err) {
          console.warn('Chat websocket message failed', err)
        }
      })
      this.chatSocket = ws
    }
  },
  created: async function () {
    this.categoriesId = this.$route.params.id
    await this.fetchPublicData()
    await this.ensureParticipant()
    await this.ensureChat()
    this.connectChatWebsocket()
  },
  beforeUnmount() {
    if (this.chatSocket) {
      this.chatSocket.close()
    }
  }
}

window.PageChatPublicChat = window.PageChatPublic
