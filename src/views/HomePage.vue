<template>
  <v-container>
    <div class="home-container">
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

      <!-- 分页组件 -->
      <v-row v-if="showPagination" justify="center">
        <v-col cols="10">
          <v-pagination v-model="currentPage" :length="totalPages">
            <template v-slot:item="{ page, props }">
              <v-btn v-bind="props" @click="handlePageChange(page)">
                {{ page }}
              </v-btn>
            </template>
          </v-pagination>
        </v-col>
      </v-row>
    </div>
  </v-container>
</template>


<script>
import axios from 'axios';
import appConfig from '@/config/appConfig.json';
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
    const paginationConfig = appConfig.pagination?.home || {};
    return {
      books: [],
      searchQuery: '',
      currentPage: paginationConfig.defaultPage || 1,
      totalPages: 0,
      pageSize: paginationConfig.pageSize || 12,
      showPagination: true,
    };
  },
  methods: {
    async fetchBooksCount() {
      try {
        const response = await axios.get(`${appConfig.backendUrl}/api/books/count`);
        const count = response.data.count;
        this.totalPages = Math.ceil(count / this.pageSize); // 计算总页数
      } catch (error) {
        console.error('Error fetching books count:', error);
      }
    },
    async fetchBooks() {
      await this.fetchBooksCount();
      try {
        const response = await axios.get(`${appConfig.backendUrl}/api/books`, {
          params: {
            page: this.currentPage,
            pageSize: this.pageSize,
          },
        });
        this.books = response.data.books;
      } catch (error) {
        console.error('Error fetching books:', error);
      }
    },
    async searchBooks() {
      if (this.searchQuery.trim()) {
        this.showPagination = false;
        try {
          const response = await axios.get(`${appConfig.backendUrl}/api/books/search`, {
            params: {
              query: this.searchQuery,
              page: 1,
              pageSize: this.pageSize,
            },
          });
          this.books = response.data.books;
        } catch (error) {
          console.error('Error searching books:', error);
        }
      } else {
        this.showPagination = true;
        this.currentPage = 1;
        this.fetchBooks();
      }
    },
    handlePageChange(page) {
      this.currentPage = parseInt(page, 10); // 转换为数字
      this.fetchBooks();
    },
  },
  created() {
    this.fetchBooks();
  },
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
