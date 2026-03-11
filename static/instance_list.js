window.PageChatInstanceList = {
  template: '#page-chat-instance-list',
  delimiters: ['${', '}'],
  data: function () {
    return {
      categoriesId: '',
      category: null,
      viewMode: 'grid',
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
      chatList: []
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
    'chatsTable.search': {
      handler() {
        this.getChats()
      }
    }
  },
  methods: {
    async fetchCategory() {
      try {
        const {data} = await LNbits.api.request(
          'GET',
          `/chat/api/v1/categories/${this.categoriesId}`,
          null
        )
        this.category = data
      } catch (error) {
        LNbits.utils.notifyApiError(error)
      }
    },

    async getChats(props) {
      try {
        this.chatsTable.loading = true
        const params = LNbits.utils.prepareFilterQuery(this.chatsTable, props)
        const {data} = await LNbits.api.request(
          'GET',
          `/chat/api/v1/chats/${this.categoriesId}/paginated?${params}`,
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

    chatTitle(chat) {
      const name = this.category?.name || 'Chat'
      return `${name} · ${chat.id.slice(0, 6)}`
    },

    chatSubtitle(chat) {
      const participants = chat.participants?.length || 0
      const last = chat.last_message_at
      const lastLabel = last ? this.dateFromNow(last) : 'just now'
      return `${participants} participants · ${lastLabel}`
    },

    chatLink(chat) {
      return `/chat/${this.categoriesId}/${chat.id}`
    },

    dateFromNow(date) {
      return moment(date).fromNow()
    }
  },
  created: async function () {
    this.categoriesId = this.$route.params.id
    await this.fetchCategory()
    await this.getChats()
  }
}
