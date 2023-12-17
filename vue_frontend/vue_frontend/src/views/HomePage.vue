<template>
  <v-app>
    <div class="home-container">
      <v-container>
        <v-row justify="center">
          <v-col cols="12" md="8">
            <v-text-field v-model="searchQuery" @keyup.enter="searchBooks" placeholder="搜索书籍..." append-icon="mdi-magnify"
              @click:append="searchBooks" solo></v-text-field>
          </v-col>
        </v-row>

        <!-- 书籍列表 -->
        <v-row>
          <v-col cols="12" sm="6" md="4" v-for="book in books" :key="book.id">
            <BookCard :book="book" />
          </v-col>
        </v-row>
      </v-container>
    </div>
  </v-app>
</template>

<script>
import axios from 'axios';
import BookCard from '../components/BookCard.vue';

export default {
  name: 'HomePage',
  components: {
    BookCard
  },
  mounted() {
    this.$nextTick(() => {
      document.title = 'ZlibSE';
    });
  },
  data() {
    return {
      bookCount: 0,
      books: [],
      searchQuery: '' // 搜索查询字符串
    };
  },
  methods: {
    async logout() {
      try {
        const response = await axios.post(`${process.env.VUE_APP_BACKEND_URL}/user/logout_user`, {}, { withCredentials: true });
        if (response.data.success) {
          this.$router.push('/');
        } else {
          console.error('Logout failed:', response.data.error);
        }
      } catch (error) {
        console.error('Logout error:', error);
      }
    },
    async fetchBookCount() {
      try {
        const response = await axios.get(`${process.env.VUE_APP_BACKEND_URL}/book/count`, {
          withCredentials: true
        });
        this.bookCount = response.data.count;
      } catch (error) {
        console.error('Error fetching book count:', error);
      }
    },
    async fetchBooks() {
      try {
        const response = await axios.get(`${process.env.VUE_APP_BACKEND_URL}/book/list`, {
          withCredentials: true
        });
        this.books = response.data.books;
      } catch (error) {
        console.error('Error fetching books:', error);
      }
    },
    async searchBooks() {
      if (this.searchQuery.trim()) {
        try {
          const response = await axios.get(`${process.env.VUE_APP_BACKEND_URL}/book/search`, {
            params: { query: this.searchQuery },
            withCredentials: true
          });
          this.books = response.data.books;
        } catch (error) {
          console.error('Error searching books:', error);
        }
      } else {
        this.fetchBooks();
      }
    }
  },
  created() {
    this.fetchBookCount();
    this.fetchBooks();
  }
};
</script>

<style scoped>
.home-container {
  margin: 20px;
}

.personal-center-link {
  position: absolute;
  right: 20px;
  top: 20px;
}

.search-container {
  margin-bottom: 20px;
}
</style>
