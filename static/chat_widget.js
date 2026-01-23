window.ChatWidget = {
  template: '#chat-widget',
  props: {
    messages: {
      type: Array,
      default: () => []
    },
    mode: {
      type: String,
      default: 'public'
    },
    participantId: {
      type: String,
      default: ''
    },
    tipsEnabled: {
      type: Boolean,
      default: false
    },
    maxChars: {
      type: Number,
      default: null
    },
    pendingAmount: {
      type: Number,
      default: 0
    },
    sending: {
      type: Boolean,
      default: false
    },
    showMinimize: {
      type: Boolean,
      default: false
    },
    minimized: {
      type: Boolean,
      default: false
    },
    launcherText: {
      type: String,
      default: 'Chat to us'
    }
  },
  emits: ['send', 'tip', 'toggle-minimize'],
  data: function () {
    return {
      messageInput: ''
    }
  },
  watch: {
    messages: {
      handler() {
        this.$nextTick(() => this.scrollToBottom())
      },
      deep: true
    }
  },
  methods: {
    emitMessage() {
      if (!this.messageInput) return
      this.$emit('send', this.messageInput)
      this.messageInput = ''
    },

    isSent(message) {
      if (this.mode === 'admin') {
        return message.sender_role === 'admin'
      }
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
    }
  }
}
