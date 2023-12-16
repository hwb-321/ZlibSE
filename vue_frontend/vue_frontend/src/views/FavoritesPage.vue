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
                const response = await axios.get(`${process.env.VUE_APP_BACKEND_URL}/user/favorites`, {
                    withCredentials: true
                });
                console.log(response.data);
                this.books = response.data.favorites;
            } catch (error) {
                console.error('Error fetching favorites:', error);
            }
        },
        async searchFavorites() {
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
                this.fetchFavorites();
            }
        }
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
