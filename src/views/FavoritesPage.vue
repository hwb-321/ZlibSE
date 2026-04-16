<template>
    <v-container>
        <v-row>
            <v-col cols="6" class="text-center">
                <h1>我的收藏</h1>
            </v-col>
            <v-col cols="6" class="text-center">
                <v-btn color="primary" @click="goToPersonalCenter">返回个人中心</v-btn>
            </v-col>
        </v-row>

        <!-- 搜索框 -->
        <v-row justify="center">
            <v-col cols="12" md="8">
                <v-text-field v-model="searchQuery" @keyup.enter="searchFavorites" placeholder="搜索收藏..."
                    append-icon="mdi-magnify" @click:append="searchFavorites" solo></v-text-field>
            </v-col>
        </v-row>

        <!-- 收藏列表 -->
        <v-row>
            <v-col cols="12" sm="6" md="4" v-for="book in filteredBooks" :key="book.id">
                <BookCard :book="book" />
            </v-col>
        </v-row>

        <v-row justify="center" class="mt-4">
            <v-col cols="12" class="text-center">
                <v-btn class="mr-2" :disabled="currentPage <= 1" @click="changePage(currentPage - 1)">
                    上一页
                </v-btn>
                <span>第 {{ currentPage }} 页</span>
                <v-btn class="ml-2" :disabled="!hasNextPage" @click="changePage(currentPage + 1)">
                    下一页
                </v-btn>
            </v-col>
        </v-row>
    </v-container>
</template>
  
  
  
<script>
import axios from 'axios';
import appConfig from '@/config/appConfig.json';
import BookCard from '../components/BookCard.vue';

export default {
    name: 'FavoritesPage',
    components: {
        BookCard
    },
    mounted() {
        this.$nextTick(() => {
            document.title = '收藏夹';
        });
    },
    data() {
        const paginationConfig = appConfig.pagination?.favorites || {};
        return {
            books: [],
            allBooks: [],
            searchQuery: '',
            currentPage: paginationConfig.defaultPage || 1,
            pageSize: paginationConfig.pageSize || 12,
            hasNextPage: false,
        };
    },
    computed: {
        filteredBooks() {
            const searchLower = this.searchQuery.toLowerCase();
            return this.books.filter(book => {
                return Object.values(book).some(value =>
                    String(value).toLowerCase().includes(searchLower)
                );
            });
        }
    },
    methods: {
        goToPersonalCenter() {
            this.$router.push('/personal-center');
        },
        async fetchFavorites() {
            try {
                const response = await axios.get(`${appConfig.backendUrl}/api/users/me/favorites`, {
                    params: {
                        page: this.currentPage,
                        pageSize: this.pageSize,
                    },
                });
                this.books = response.data.favorites;
                this.allBooks = response.data.favorites;
                this.hasNextPage = Array.isArray(response.data.favorites) && response.data.favorites.length === this.pageSize;
            } catch (error) {
                console.error('Error fetching favorites:', error);
            }
        },
        async changePage(page) {
            if (page < 1 || page === this.currentPage) {
                return;
            }
            this.currentPage = page;
            await this.fetchFavorites();
        },
        searchFavorites() {
            const query = this.searchQuery.trim().toLowerCase();
            if (!query) {
                this.books = this.allBooks;
                return;
            }
            this.books = this.allBooks.filter((book) => {
                return [
                    book.title,
                    book.author,
                    book.language,
                    book.file_type,
                ].some((value) => String(value || '').toLowerCase().includes(query));
            });
        },
    },
    created() {
        this.fetchFavorites();
    }
};
</script>

<style scoped>
.favorites-container {
    margin: 20px;
}

.search-container {
    margin-bottom: 20px;
}

.text-center {
    text-align: center;
}
</style>
