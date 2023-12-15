<template>
    <div class="favorites-container">
        <h1>我的收藏</h1>

        <!-- 搜索框和搜索按钮 -->
        <div class="search-container">
            <input v-model="searchQuery" @keyup.enter="searchFavorites" placeholder="搜索收藏...">
            <button @click="searchFavorites">搜索</button>
        </div>

        <!-- 收藏列表 -->
        <BookCard v-for="book in books" :key="book.id" :book="book" :to="{ name: 'BookDetail', params: { id: book.id } }" />

        <!-- 返回主界面按钮 -->
        <button @click="goToHome">返回主界面</button>
    </div>
</template>
  
<script>
import axios from 'axios';
import BookCard from '../components/BookCard.vue';

export default {
    name: 'FavoritesPage',
    components: {
        BookCard
    },
    data() {
        return {
            books: [],
            searchQuery: ''
        };
    },
    methods: {
        goToHome() {
            this.$router.push('/home');
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
</style>
  