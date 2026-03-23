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
        return {
            books: [],
            allBooks: [],
            searchQuery: ''
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
                const response = await axios.get(`${appConfig.backendUrl}/user/favorites`);
                this.books = response.data.favorites;
                this.allBooks = response.data.favorites;
            } catch (error) {
                console.error('Error fetching favorites:', error);
            }
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
                    book.isbn,
                    book.category,
                    book.year,
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
