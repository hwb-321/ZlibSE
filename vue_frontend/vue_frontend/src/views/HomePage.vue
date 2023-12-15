<template>
  <div class="home-container">
    <div class="personal-center-link">
      <router-link to="/personal-center">个人中心</router-link>
    </div>
    <h1>书籍总数: {{ bookCount }}</h1>

    <!-- 搜索框和搜索按钮 -->
    <div class="search-container">
      <input v-model="searchQuery" @keyup.enter="searchBooks" placeholder="搜索书籍...">
      <button @click="searchBooks">搜索</button>
    </div>

    <!-- 书籍列表 -->
    <BookCard v-for="book in books" :key="book.id" :book="book" :to="{ name: 'BookDetail', params: { id: book.id } }" />

    <!-- 退出登录按钮 -->
    <button @click="logout">退出登录</button>
  </div>
</template>

<script>
import axios from 'axios';
import BookCard from '../components/BookCard.vue';

export default {
  name: 'HomePage',
  components: {
    BookCard
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
        const response = await axios.post(`${process.env.VUE_APP_BACKEND_URL}/user/logout_user/`, {}, { withCredentials: true });
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
