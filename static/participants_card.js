window.ChatParticipantsCard = {
  template: '#participants-card',
  props: {
    participants: {
      type: Array,
      default: () => []
    },
    limit: {
      type: Number,
      default: 5
    }
  },
  methods: {
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
    }
  }
}
